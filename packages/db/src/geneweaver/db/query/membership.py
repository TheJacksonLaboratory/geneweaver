"""Which of a gene set's genes take part in an analysis: the run's threshold choice.

Decided by curation (Tessa, Heidi; 2026-10-16): a gene set is not inherently thresholded.
It is its full list of genes and scores, and whoever runs an analysis may threshold it for
that run. So a run chooses one of:

- ``none`` (the default): every gene in each gene set;
- ``uploader``: each gene set's own stored cutoff (``gs_threshold``), the one-click choice;
- ``custom``: the run's own cutoffs, one per score type.

Cutoffs read as curation set them: a p- or q-value **at most** its cutoff (``<=``); a
correlation or effect **inside** its range, both ends included. A binary gene set has no
score to cut, so every gene counts under every choice.

The stored ``gsv_in_threshold`` flag is not the rule any more. It was computed with ``<``
for p/q values (``production.process_thresholds``), so ``uploader`` re-reads the stored
cutoff with ``<=`` instead; on dev that adds 14,431 genes sitting exactly on a cutoff, in
590 gene sets. The flag is still the fallback for what ``<=`` cannot read: a cutoff that is
not a number (two on dev: ``'Nan'``, ``'-0.75,0,75'``) and the legacy score types 6-8.

Every query is one filter over a ``geneset_value`` alias and a ``geneset`` alias, with the
cutoffs bound as parameters, so all resolvers of a run read one rule.
"""

from dataclasses import dataclass

from psycopg.sql import SQL, Composed

#: A number as ``numeric`` accepts it; guards each cast so a bad cutoff cannot fail a run.
_NUMBER = r"^\s*[-+]?([0-9]+\.?[0-9]*|\.[0-9]+)([eE][-+]?[0-9]+)?\s*$"

MODES = ("none", "uploader", "custom")


@dataclass(frozen=True)
class Thresholds:
    """A run's threshold choice; see the module docstring."""

    mode: str = "none"
    p_value: float | None = None
    q_value: float | None = None
    correlation_low: float | None = None
    correlation_high: float | None = None
    effect_low: float | None = None
    effect_high: float | None = None

    def __post_init__(self) -> None:
        """Refuse a mode that is not one of `MODES`."""
        if self.mode not in MODES:
            raise ValueError(f"Threshold mode must be one of {MODES}, not {self.mode!r}.")


#: Every gene, the default.
ALL_GENES = Thresholds()


def membership_filter(
    thresholds: Thresholds = ALL_GENES, gv: str = "gv", gs: str = "gs"
) -> tuple[Composed, dict]:
    """The predicate keeping the genes ``thresholds`` lets into the run.

    :param thresholds: The run's choice.
    :param gv: The query's alias for ``extsrc.geneset_value`` (a literal, never input).
    :param gs: Its alias for ``production.geneset`` joined on ``gs_id``.
    :return: The predicate and its parameters, ``t_``-prefixed so they cannot collide.
    """
    value = SQL(f"{gv}.gsv_value")
    kind = SQL(f"{gs}.gs_threshold_type")
    if thresholds.mode == "none":
        return SQL("TRUE").format(), {}

    if thresholds.mode == "uploader":
        stored = SQL(f"{gs}.gs_threshold")
        low = SQL("split_part({stored}, ',', 1)").format(stored=stored)
        high = SQL("split_part({stored}, ',', 2)").format(stored=stored)
        return (
            SQL(
                "(CASE WHEN {kind} IN (1, 2) AND {stored} ~ %(t_number)s "
                "THEN {value} <= {stored}::numeric "
                "WHEN {kind} IN (4, 5) AND array_length(string_to_array({stored}, ','), 1) = 2 "
                "AND {low} ~ %(t_number)s AND {high} ~ %(t_number)s "
                "THEN {value} BETWEEN {low}::numeric AND {high}::numeric "
                "WHEN {kind} = 3 THEN TRUE "
                "ELSE {flag} END)"
            ).format(
                kind=kind,
                stored=stored,
                value=value,
                low=low,
                high=high,
                flag=SQL(f"{gv}.gsv_in_threshold"),
            ),
            {"t_number": _NUMBER},
        )

    branches: list[Composed] = []
    params: dict = {}
    for type_id, key, cutoff in (
        (1, "t_p_value", thresholds.p_value),
        (2, "t_q_value", thresholds.q_value),
    ):
        if cutoff is not None:
            branches.append(
                SQL("WHEN {kind} = {type_id} THEN {value} <= %({key})s").format(
                    kind=kind, type_id=type_id, value=value, key=SQL(key)
                )
            )
            params[key] = cutoff
    for type_id, name, low, high in (
        (4, "correlation", thresholds.correlation_low, thresholds.correlation_high),
        (5, "effect", thresholds.effect_low, thresholds.effect_high),
    ):
        bounds: list[Composed] = []
        if low is not None:
            bounds.append(
                SQL("{value} >= %({key})s").format(value=value, key=SQL(f"t_{name}_low"))
            )
            params[f"t_{name}_low"] = low
        if high is not None:
            bounds.append(
                SQL("{value} <= %({key})s").format(value=value, key=SQL(f"t_{name}_high"))
            )
            params[f"t_{name}_high"] = high
        if bounds:
            branches.append(
                SQL("WHEN {kind} = {type_id} THEN ").format(kind=kind, type_id=type_id)
                + SQL(" AND ").join(bounds)
            )
    if not branches:
        return SQL("TRUE").format(), {}
    # A type without a cutoff, binary included, keeps every gene.
    return SQL("(CASE ") + SQL(" ").join(branches) + SQL(" ELSE TRUE END)"), params
