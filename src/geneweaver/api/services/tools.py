"""Service functions for running the ported analysis tools.

The flow is the same for every tool and worth keeping that way as more are added:

1. **gate** -- confirm the caller may read every gene set they named;
2. **resolve** -- turn gene set ids into the tool's input (`geneweaver.db.tool_input`);
3. **run** -- hand the input to a `ToolRunner`, which today executes in-process and
   later dispatches to AsyncTask;
4. **shape** -- map the tool's output onto the API schema.

Step 1 is the security-relevant one. The tools themselves know nothing about users, so a
missing gate here means a caller could read gene sets through a tool result that they
could not read directly. `db_geneset.is_readable` is the same check the gene set
endpoints use, with user id 0 standing for anonymous.
"""

from geneweaver.db import geneset as db_geneset
from geneweaver.db import tool_input as db_tool_input
from geneweaver.tools.upset import UpSet, UpSetInput
from psycopg import Cursor

from geneweaver.api.core.exceptions import UnauthorizedException
from geneweaver.api.schemas.auth import User
from geneweaver.api.schemas.tools import UpSetIntersection, UpSetResult
from geneweaver.api.services.geneset import determine_user_id
from geneweaver.api.services.tool_runner import InProcessToolRunner, ToolRunner


def _gate_geneset_access(cursor: Cursor, user: User | None, geneset_ids: list[int]) -> None:
    """Refuse the run unless every named gene set is readable by the caller.

    Anonymous callers resolve to user id 0, which `geneset_is_readable2` treats as the
    public audience -- so an anonymous run sees public gene sets and nothing else.

    :raises UnauthorizedException: if any gene set is not readable.
    """
    user_id = determine_user_id(user)
    unreadable = [
        geneset_id
        for geneset_id in geneset_ids
        if not db_geneset.is_readable(cursor, user_id, geneset_id)
    ]
    if unreadable:
        raise UnauthorizedException(
            detail=(
                "Not authorized to read gene set(s): "
                + ", ".join(str(geneset_id) for geneset_id in unreadable)
            )
        )


def run_upset(
    cursor: Cursor,
    geneset_ids: list[int],
    user: User | None = None,
    include_zeros: bool = False,
    runner: ToolRunner | None = None,
) -> UpSetResult:
    """Run UpSet over the given gene sets and return the exclusive intersection sizes.

    :param cursor: The database cursor.
    :param geneset_ids: The gene sets to intersect.
    :param user: The requesting user, or None for anonymous.
    :param include_zeros: Emit combinations with no genes.
    :param runner: Execution backend; defaults to running in-process.
    :return: The intersection sizes, largest first.
    :raises UnauthorizedException: If any gene set is not readable by the caller.
    """
    _gate_geneset_access(cursor, user, geneset_ids)

    memberships = db_tool_input.gene_symbols_by_geneset(cursor, geneset_ids)

    runner = runner or InProcessToolRunner()
    output = runner.run(
        UpSet(),
        UpSetInput(
            geneset_ids=[str(geneset_id) for geneset_id in geneset_ids],
            gene_memberships=memberships,
            include_zeros=include_zeros,
        ),
    )

    return UpSetResult(
        geneset_ids=geneset_ids,
        gene_counts={key: len(genes) for key, genes in memberships.items()},
        intersections=[
            UpSetIntersection(geneset_ids=item.genesets, size=item.size)
            for item in output.intersections
        ],
    )
