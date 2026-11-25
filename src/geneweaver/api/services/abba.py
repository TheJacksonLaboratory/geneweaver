"""ABBA, legacy's gene-centred search, run on AsyncTask like every other tool.

ABBA is a SQL pipeline over the whole gene-set corpus (`geneweaver.tools.abba.search`), not
a computation over input the API hands it. Where AsyncTask is configured it still goes there,
as the signed-in user, through the same `GeneWeaverToolWorkflow`: the tool worker searches
the database from inside the activity, so the run shows in Temporal and is polled by run id
like the others. The API's part is what needs the caller:

- the gate on seed gene sets, which are then expanded to their genes here, so the worker is
  never asked to read a gene set on anyone's behalf;
- the caller's identity, signed (`geneweaver.tools.abba.identity`), so the worker searches
  their private gene sets and a run submitted to AsyncTask directly cannot claim someone
  else's.

Where AsyncTask is not configured, the same search runs here on a pooled connection, for as
long as it takes -- 20 to 60 seconds on dev. At most `ABBA_MAX_CONCURRENT` run at once per
process, so they cannot take the pool from every other request; the next is refused with
`ABBABusy` (503) rather than queued. Each has `ABBA_REQUEST_TIMEOUT_SECONDS` in all, from
before its connection is leased to its last statement, so it answers before the ingress gives
up; past that it stops and answers `ABBATimedOut` (504).
"""

import hashlib
import hmac
import threading
import time
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any

from geneweaver.db.abba import (
    ABBADeadlineExceeded,
    bound_next_statement,
    deadline_cancellation,
    execute_within,
)
from geneweaver.db.query import abba as abba_queries
from geneweaver.db.query.membership import Thresholds
from geneweaver.tools.abba import TOOL_NAME, ABBAInput
from geneweaver.tools.abba.identity import sign
from geneweaver.tools.abba.schema import clean_genes
from geneweaver.tools.abba.search import search
from psycopg import Cursor
from psycopg.rows import tuple_row
from pydantic import ValidationError

from geneweaver.api.core.config import settings
from geneweaver.api.schemas.auth import User
from geneweaver.api.schemas.tools import ABBARequest
from geneweaver.api.services.asynctask import AsyncTaskClient
from geneweaver.api.services.geneset import determine_user_id
from geneweaver.api.services.run_record import RunRecord
from geneweaver.api.services.tools import (
    ToolRequestError,
    _check_size,
    _gate_geneset_access,
    _require_user,
    _run_on_asynctask,
    asynctask_client_for,
)

_running = threading.BoundedSemaphore(settings.ABBA_MAX_CONCURRENT)


class ABBABusy(Exception):
    """Too many in-process searches are running; the caller should retry (503)."""


class ABBATimedOut(Exception):
    """An in-process search ran out of `ABBA_REQUEST_TIMEOUT_SECONDS` (504)."""


#: Envelope key for the seed gene sets a run was gated on (see `seed_provenance`).
SEED_GENESETS_KEY = "seed_genesets"
_SEED_LABEL = b"geneweaver-abba-seed-genesets-v1"


#: The most seed genes a search takes once seed gene sets are expanded. The largest gene set
#: on dev holds 17,370 genes, so one still fits; more is a request to search much of the
#: corpus, which ABBA cannot answer usefully, and it nears AsyncTask's payload limit.
MAX_SEED_GENES = 20_000


@dataclass
class PreparedABBA:
    """A search with the caller's database reads done: gate, seed expansion, identity."""

    shaped: dict[str, Any]
    tool_input: ABBAInput
    user_id: int
    asynctask: AsyncTaskClient | None
    #: The seed gene sets the caller was gated on, before they were expanded to genes.
    seed_geneset_ids: list[int]


def seed_genes(cursor: Cursor, request: ABBARequest, deadline: float | None = None) -> list[str]:
    """The typed seed genes, then the genes of the seed gene sets, without repeats.

    The gene sets must already have been gated. Read on a tuple-row cursor because the
    query is the pipeline's own, which reads by position. A seed gene set contributes its
    genes -- one preferred symbol each -- as the run's threshold choice keeps them, as the
    search itself counts. Repeats are dropped as `ABBAInput` drops them (`clean_genes`), so
    the cap counts the genes the search gets: a typed gene that is also in a seed gene set,
    or a symbol in two spellings, counts once.

    :param deadline: A ``time.monotonic()`` instant the expansion query must finish by.
    :raises ToolRequestError: If the seed comes to more than `MAX_SEED_GENES` genes.
    :raises ABBADeadlineExceeded: If the expansion would run past ``deadline``.
    """
    genes = list(request.genes)
    if request.geneset_ids:
        with cursor.connection.cursor(row_factory=tuple_row) as rows:
            execute_within(
                rows,
                abba_queries.ref_ids_for_genesets(
                    request.geneset_ids, Thresholds(**request.membership_kwargs())
                ),
                deadline,
                settings.ABBA_STATEMENT_TIMEOUT_SECONDS,
            )
            genes.extend(str(row[0]) for row in rows.fetchall())
    genes = clean_genes(genes)
    if len(genes) > MAX_SEED_GENES:
        raise ToolRequestError(
            f"The seed comes to {len(genes):,} genes with its gene sets; ABBA takes at most "
            f"{MAX_SEED_GENES:,}. Use fewer or smaller gene sets, or a threshold."
        )
    return genes


def prepare_abba(
    cursor: Cursor, request: ABBARequest, user: User | None, deadline: float | None = None
) -> PreparedABBA:
    """Gate the seed gene sets and build the search's input.

    :param deadline: A ``time.monotonic()`` instant: each of the gate's and the seed
        expansion's queries gets only what is left of it. None (AsyncTask) leaves them as
        any request's.
    :raises SignInRequired: If the caller is anonymous.
    :raises UnauthorizedException: If a seed gene set is not readable by the caller.
    :raises ToolRequestError: If the input is refused, e.g. too large to submit.
    :raises ABBADeadlineExceeded: If preparing would run past ``deadline``.
    """
    _require_user(user)
    if deadline is None:
        _gate_geneset_access(cursor, user, request.geneset_ids)
    else:
        with deadline_cancellation(deadline):
            _gate_geneset_access(
                cursor,
                user,
                request.geneset_ids,
                before_each=lambda: bound_next_statement(
                    cursor, deadline, settings.ABBA_STATEMENT_TIMEOUT_SECONDS
                ),
            )
    try:
        tool_input = ABBAInput(
            genes=seed_genes(cursor, request, deadline),
            **request.model_dump(exclude={"genes", "geneset_ids"}),
        )
    except ValidationError as error:
        raise ToolRequestError(f"Invalid input for abba: {error}") from error
    return PreparedABBA(
        shaped={
            "tool": TOOL_NAME,
            "geneset_ids": request.geneset_ids,
            # ABBA's seed is genes, not gene sets compared, so there are no per-set counts.
            "gene_counts": {},
            "caveat": None,
            "thresholds": tool_input.threshold_choice(),
        },
        tool_input=tool_input,
        user_id=determine_user_id(user),
        asynctask=asynctask_client_for(user),
        seed_geneset_ids=sorted(set(request.geneset_ids)),
    )


def _secret() -> str:
    """`ABBA_IDENTITY_SECRET` where set, else the database password, as the worker reads them."""
    return settings.ABBA_IDENTITY_SECRET or settings.DB_PASSWORD


def _seed_signature(identity_signature: str, geneset_ids: list[int], secret: str) -> str:
    key = hmac.new(secret.encode(), _SEED_LABEL, hashlib.sha256).digest()
    message = f"{identity_signature}|{','.join(str(gs) for gs in geneset_ids)}".encode()
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def seed_provenance(identity: dict[str, Any], geneset_ids: list[int], secret: str) -> dict:
    """The seed gene sets a run was gated on, signed, for its envelope.

    The seed gene sets are expanded to genes before submission, so the input no longer shows
    them, yet reading the result later must re-check them (G3-736): the seed genes came from
    them. The run's *description* names them too, but its owner can edit that (AsyncTask's
    ``PATCH /inputs/{id}``), and clearing it would drop the check. The envelope cannot be
    edited after submission; and the signature, bound to the identity's -- itself bound to
    this user, this input and an expiry -- stops a copy of the envelope from being submitted
    to AsyncTask directly with the gene sets left out.
    """
    ids = sorted(set(geneset_ids))
    return {"geneset_ids": ids, "signature": _seed_signature(identity["signature"], ids, secret)}


def verified_seed_genesets(envelope: dict[str, Any]) -> list[int] | None:
    """The seed gene sets an ABBA envelope was gated on, or None if it does not prove them.

    None -- no provenance, a malformed one, or a signature that does not match -- means
    *unknown*, never "no seed gene sets": the caller must then refuse to show the result.
    """
    provenance = envelope.get(SEED_GENESETS_KEY)
    identity = envelope.get("identity")
    if not isinstance(provenance, dict) or not isinstance(identity, dict):
        return None
    ids, signature = provenance.get("geneset_ids"), provenance.get("signature")
    identity_signature = identity.get("signature")
    if (
        not isinstance(ids, list)
        or not all(isinstance(gs, int) and not isinstance(gs, bool) for gs in ids)
        or not isinstance(signature, str)
        or not isinstance(identity_signature, str)
    ):
        return None
    expected = _seed_signature(identity_signature, sorted(set(ids)), _secret())
    if not hmac.compare_digest(signature, expected):
        return None
    return sorted(set(ids))


def envelope_for(prepared: PreparedABBA) -> dict[str, Any]:
    """The AsyncTask request: the input, who the search is for, and its seed gene sets.

    The identity is signed for this input and expires (`geneweaver.tools.abba.identity`); the
    seed gene sets are signed against it (`seed_provenance`). Both are keyed by
    `ABBA_IDENTITY_SECRET` where set, else the database password, as the worker reads them.
    The worker ignores the seed gene sets: they are for the API, when the result is read.
    """
    tool_input = prepared.tool_input.model_dump(mode="json")
    secret = _secret()
    identity = sign(prepared.user_id, secret, tool_input)
    return {
        "tool": TOOL_NAME,
        "input": tool_input,
        "identity": identity,
        SEED_GENESETS_KEY: seed_provenance(identity, prepared.seed_geneset_ids, secret),
    }


def run_abba(
    open_cursor: Callable[[], AbstractContextManager[Cursor]],
    request: ABBARequest,
    user: User | None,
) -> dict[str, Any]:
    """Gate, run and return one ABBA search, in the shape every tool run returns.

    :return: ``{tool, geneset_ids, gene_counts, caveat, executed_by, run_id, result}``.
    :raises SignInRequired: If the caller is anonymous.
    :raises UnauthorizedException: If a seed gene set is not readable by the caller.
    :raises ToolRequestError: If the input is refused.
    :raises ToolRunPending: If the AsyncTask run outlasts the wait; poll it by run id.
    :raises ToolRunFailed: If the AsyncTask run fails.
    :raises ABBABusy: If, in-process, `ABBA_MAX_CONCURRENT` searches are already running.
    :raises ABBATimedOut: If, in-process, the search outlasts `ABBA_REQUEST_TIMEOUT_SECONDS`.
    """
    # Before the cursor: an anonymous request is refused without leasing a connection.
    _require_user(user)
    if asynctask_client_for(user) is not None:
        # The connection goes back to the pool before the wait on AsyncTask.
        with open_cursor() as cursor:
            prepared = prepare_abba(cursor, request, user)
        envelope = envelope_for(prepared)
        _check_size(envelope)
        label = f"{TOOL_NAME}: " + ", ".join(prepared.tool_input.genes[:5])
        return {
            **prepared.shaped,
            "executed_by": "asynctask",
            **_run_on_asynctask(
                prepared.asynctask,
                envelope,
                prepared.shaped,
                label=label,
                record=RunRecord(
                    tool=TOOL_NAME,
                    geneset_ids=list(request.geneset_ids),
                    request=request.model_dump(mode="json"),
                ),
            ),
        }

    if not _running.acquire(blocking=False):
        raise ABBABusy(
            f"{settings.ABBA_MAX_CONCURRENT} ABBA searches are already running; "
            "try again in a minute."
        )
    # One budget for the whole request, started before the connection is leased: the gate,
    # the seed expansion, the name lookups and the pipeline all spend from it.
    deadline = time.monotonic() + settings.ABBA_REQUEST_TIMEOUT_SECONDS
    try:
        with open_cursor() as cursor:
            prepared = prepare_abba(cursor, request, user, deadline)
            output = search(
                cursor.connection,
                prepared.tool_input,
                prepared.user_id,
                statement_timeout_seconds=settings.ABBA_STATEMENT_TIMEOUT_SECONDS,
                deadline=deadline,
            )
    except ABBADeadlineExceeded as error:
        raise ABBATimedOut(
            f"The ABBA search took longer than {settings.ABBA_REQUEST_TIMEOUT_SECONDS} s and "
            "was stopped. Try fewer seed genes, fewer tiers, or a species restriction."
        ) from error
    finally:
        _running.release()
    return {
        **prepared.shaped,
        "executed_by": "in_process",
        "run_id": None,
        "result": output.model_dump(mode="json"),
    }
