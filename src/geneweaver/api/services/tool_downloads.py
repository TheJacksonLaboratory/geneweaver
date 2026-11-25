"""A tool run's result as a file to download (G3-801).

What legacy offered, per tool, and what v3 offers instead:

- **Figures** (Venn grids, dendrograms, UpSet plots, graphs) were PDF/PNG/SVG, rendered in
  the browser or from SVG the browser posted back (``/downloadResult``). v3 draws its charts
  in the browser too, and the Analyze page downloads them as SVG (`chart-utils.ts`), so the
  API serves the data behind them, not images.
- **Tables** legacy exported -- Similar gene sets' list, PhenomeMap's node CSV, Boolean
  Algebra's result table -- are CSV here, as is every other tool's natural table.
- **Combine** wrote its gene x gene-set matrix as ``<run>.odemat`` (TSV); the same layout
  is served here as ``format=odemat``.
- **JSON**, the tool's own output, for every tool.

v3 runs produce data, not files: nothing is written to a results directory, and the legacy
``/api/tool/get/{file,link,status}`` routes stay the legacy app's (see the tools controller).
Pure functions over the stored result; the caller has already checked access to it.
"""

import csv
import io
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

#: Format -> (media type, file extension).
FORMATS: dict[str, tuple[str, str]] = {
    "json": ("application/json", "json"),
    "csv": ("text/csv", "csv"),
    "tsv": ("text/tab-separated-values", "tsv"),
    "odemat": ("text/tab-separated-values", "odemat"),
    "newick": ("text/plain", "nwk"),
}

Table = tuple[list[str], list[list[Any]]]


class DownloadError(ValueError):
    """The result cannot be given in that format or table (422)."""


@dataclass(frozen=True)
class Download:
    """A file: its bytes, media type and name."""

    content: bytes
    media_type: str
    filename: str


def _label(ids: list[Any], index: Any) -> Any:
    """A pair's position in the run's gene sets, as that gene set's id."""
    if isinstance(index, int) and 0 <= index < len(ids):
        return ids[index]
    return index


def _joined(values: Any) -> str:
    return ";".join(str(value) for value in values) if isinstance(values, list) else ""


def _upset(result: dict) -> dict[str, Table]:
    rows = [[_joined(i.get("genesets")), i.get("size")] for i in result.get("intersections", [])]
    return {"intersections": (["genesets", "size"], rows)}


def _pairs(result: dict, columns: list[str]) -> list[list[Any]]:
    ids = result.get("geneset_ids", [])
    return [
        [_label(ids, row.get("i")), _label(ids, row.get("j"))] + [row.get(c) for c in columns]
        for row in result.get("results", [])
    ]


def _jaccard_similarity(result: dict) -> dict[str, Table]:
    columns = ["jaccard", "p_value", "intersection", "only_i", "only_j"]
    header = ["geneset_a", "geneset_b", "jaccard", "p_value", "intersection", "only_a", "only_b"]
    return {"pairs": (header, _pairs(result, columns))}


def _hypergeometric(result: dict) -> dict[str, Table]:
    columns = ["odds_ratio", "upper_tail", "lower_tail", "two_tailed", "hypergeometric"]
    return {"pairs": (["geneset_a", "geneset_b", *columns], _pairs(result, columns))}


def _combine_rows(result: dict) -> tuple[list[int], list[list[Any]]]:
    """Combine's matrix as (gene sets, [gene id, identifier, 0/1 per gene set])."""
    geneset_ids = [int(gs) for gs in result.get("geneset_ids", [])]
    rows = []
    for gene_id, row in (result.get("matrix") or {}).items():
        row = {str(key): value for key, value in row.items()}
        rows.append(
            [gene_id, row.get("0", "")] + [1 if row.get(str(gs)) else 0 for gs in geneset_ids]
        )
    return geneset_ids, rows


def _combine(result: dict) -> dict[str, Table]:
    geneset_ids, rows = _combine_rows(result)
    header = ["gene_id", "gene", *[f"GS{gs}" for gs in geneset_ids]]
    return {"matrix": (header, rows)}


def _boolean_algebra(result: dict) -> dict[str, Table]:
    """The relation's answer, one row per gene, as the Analyze page lists it.

    A row of ``bool_results`` is ``[gene id, identifier, species id, gene set id]``; union
    answers with every gene, intersection and except with the keys of their own results.
    """
    groups = result.get("bool_results") or {}
    relation = str(result.get("relation", "")).lower()
    # "intersect" is the API's other spelling of intersection (`BOOLEAN_RELATIONS`).
    nested = {
        "intersection": "intersect_results",
        "intersect": "intersect_results",
        "except": "bool_except",
    }.get(relation)
    if nested:
        keys = {
            str(key) for by_species in (result.get(nested) or {}).values() for key in by_species
        }
    else:
        keys = {str(key) for key in groups}
    rows = []
    for key, members in groups.items():
        if str(key) not in keys:
            continue
        identifiers = sorted({str(m[1]) for m in members if len(m) > 3})
        species = sorted({m[2] for m in members if len(m) > 3})
        genesets = sorted({m[3] for m in members if len(m) > 3})
        rows.append([key, ";".join(identifiers), _joined(species), _joined(genesets)])
    rows.sort(key=lambda row: (-len(row[3].split(";")) if row[3] else 0, row[1]))
    return {"genes": (["key", "genes", "species_ids", "geneset_ids"], rows)}


def _dbscan(result: dict) -> dict[str, Table]:
    rows = [
        [number, gene]
        for number, cluster in enumerate(result.get("clusters") or [], start=1)
        for gene in cluster
    ]
    return {"clusters": (["cluster", "gene"], rows)}


def _geneset_graph(result: dict) -> dict[str, Table]:
    genes = [
        [g.get("symbol"), g.get("degree"), _joined(g.get("genesets")), g.get("emphasized")]
        for g in result.get("genes", [])
    ]
    sets = [[s.get("id"), s.get("genes"), s.get("size")] for s in result.get("genesets", [])]
    return {
        "genes": (["gene", "degree", "genesets", "emphasized"], genes),
        "genesets": (["geneset", "genes_drawn", "size"], sets),
    }


def _triclique(result: dict) -> dict[str, Table]:
    return {"shared_genes": (["gene"], [[gene] for gene in result.get("shared_genes", [])])}


def _mset(result: dict) -> dict[str, Table]:
    rows = [[key, value] for key, value in (result.get("mset_data") or {}).items()]
    return {"summary": (["statistic", "value"], rows)}


def _phenome_map(result: dict) -> dict[str, Table]:
    rows = [
        [
            n.get("id"),
            n.get("depth"),
            _joined(n.get("genesets")),
            _joined(n.get("genes")),
            _joined(n.get("parents")),
            n.get("displayed"),
        ]
        for n in result.get("nodes", [])
    ]
    return {"nodes": (["node", "depth", "genesets", "genes", "parents", "displayed"], rows)}


def _abba(result: dict) -> dict[str, Table]:
    sets = [
        [
            g.get("gs_id"),
            g.get("name"),
            g.get("abbreviation"),
            g.get("matches"),
            g.get("tier"),
            g.get("species_id"),
            g.get("attribution"),
            g.get("gene_count"),
        ]
        for g in result.get("genesets", [])
    ]
    genes = [
        [g.get("symbol"), g.get("species"), g.get("occurrences"), _joined(g.get("symbols"))]
        for g in result.get("genes", [])
    ]
    return {
        "genesets": (
            [
                "gs_id",
                "name",
                "abbreviation",
                "matches",
                "tier",
                "species_id",
                "attribution",
                "genes",
            ],
            sets,
        ),
        "genes": (["gene", "species", "occurrences", "symbols"], genes),
    }


def _similar_genesets(result: dict) -> dict[str, Table]:
    """Legacy's "Export GeneSets" columns (gs_id, name, abbreviation, count, jaccard), plus more."""
    rows = [
        [
            g.get("gs_id"),
            g.get("name"),
            g.get("abbreviation"),
            g.get("genes"),
            g.get("shared"),
            g.get("jaccard"),
            g.get("species_id"),
            g.get("tier"),
            g.get("attribution"),
        ]
        for g in result.get("genesets", [])
    ]
    header = ["gs_id", "name", "abbreviation", "genes", "shared", "jaccard", "species_id", "tier"]
    return {"genesets": ([*header, "attribution"], rows)}


#: Each tool's tables, the first its default.
TABLES: dict[str, Callable[[dict], dict[str, Table]]] = {
    "upset": _upset,
    "jaccard_similarity": _jaccard_similarity,
    "hypergeometric": _hypergeometric,
    "combine": _combine,
    "boolean_algebra": _boolean_algebra,
    "dbscan": _dbscan,
    "geneset_graph": _geneset_graph,
    "triclique": _triclique,
    "mset": _mset,
    "phenome_map": _phenome_map,
    "abba": _abba,
    "similar_genesets": _similar_genesets,
}


def formats_for(tool: str | None) -> list[str]:
    """The formats a tool's result downloads in."""
    formats = ["json"]
    if tool in TABLES:
        formats += ["csv", "tsv"]
    if tool == "combine":
        formats.append("odemat")
    if tool == "jaccard_clustering":
        formats.append("newick")
    return formats


#: What makes a spreadsheet read a cell as a formula, full-width forms included.
_FORMULA_START = frozenset("=+-@\uff1d\uff0b\uff0d\uff20")


def _is_number(text: str) -> bool:
    try:
        float(text)
    except ValueError:
        return False
    return True


def _spreadsheet_safe(value: Any) -> Any:
    """A text cell a spreadsheet will show as text, not run as a formula.

    Gene set names and abbreviations are their uploaders' (ABBA, Similar gene sets, Combine's
    labels), so a name like ``=HYPERLINK(...)`` would otherwise become a live formula in
    whoever opens the download. Such a cell gets a leading ``'``, as OWASP advises, also
    where whitespace or control characters come first, since spreadsheets skip those. Numbers
    are left alone -- including negative and scientific ones, as numbers or as text -- and
    the JSON download keeps every value as it is.
    """
    if not isinstance(value, str) or not value or _is_number(value):
        return value
    head = value.lstrip("".join(chr(c) for c in range(33)))
    if value[0] in "\t\r\n" or (head and head[0] in _FORMULA_START):
        return "'" + value
    return value


def _delimited(table: Table, delimiter: str) -> bytes:
    header, rows = table
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=delimiter, lineterminator="\n")
    writer.writerow(header)
    writer.writerows([_spreadsheet_safe(value) for value in row] for row in rows)
    return buffer.getvalue().encode()


def _odemat(result: dict) -> bytes:
    """Legacy's ``.odemat``: counts, then gene set ids, then labels, then a row per gene.

    As `toolbase.write_combined_file` wrote it, tab-separated: the gene and gene-set counts
    then ``GS<id>`` for each gene set; an empty cell then each gene set's label; then per
    gene its id, its identifier, and 1 or 0 for each gene set.
    """
    geneset_ids, rows = _combine_rows(result)
    labels = result.get("gslabels") or {}
    lines = [
        "\t".join([str(len(rows)), str(len(geneset_ids))] + [f"GS{gs}" for gs in geneset_ids]),
        "\t".join([""] + [str(labels.get(str(gs), labels.get(gs, ""))) for gs in geneset_ids]),
    ]
    lines += ["\t".join(str(value) for value in row) for row in rows]
    return ("\n".join(lines) + "\n").encode()


def _newick(node: dict | None) -> str:
    """A clustering tree in Newick: leaves are gene sets, branch lengths are merge heights."""

    def walk(current: dict, parent_height: float | None) -> str:
        height = current.get("distance") or 0.0
        children = current.get("children") or []
        label = f"GS{current['geneset_id']}" if current.get("geneset_id") else ""
        text = (
            f"({','.join(walk(child, height) for child in children)}){label}"
            if children
            else label
        )
        if parent_height is not None:
            text += f":{max(parent_height - height, 0.0):g}"
        return text

    return (walk(node, None) if node else "") + ";\n"


def render(
    tool: str | None, result: dict[str, Any], fmt: str, table: str | None, run_id: int
) -> Download:
    """The result as a file in ``fmt``; for csv/tsv, ``table`` names which of the tool's tables.

    :raises DownloadError: For a format the tool does not offer, or a table it does not have.
    """
    if fmt not in formats_for(tool):
        raise DownloadError(
            f"{tool or 'This run'}'s result downloads as {', '.join(formats_for(tool))}, not {fmt}."
        )
    media_type, extension = FORMATS[fmt]
    stem = f"{tool or 'run'}-run{run_id}"
    if fmt == "json":
        content = json.dumps(result, indent=2, default=str).encode()
    elif fmt == "odemat":
        content = _odemat(result)
    elif fmt == "newick":
        content = _newick(result.get("tree")).encode()
    else:
        tables = TABLES[tool](result)
        name = table or next(iter(tables))
        if name not in tables:
            raise DownloadError(
                f"{tool} results have the tables {', '.join(tables)}; there is no {name!r}."
            )
        content = _delimited(tables[name], "," if fmt == "csv" else "\t")
        stem = f"{stem}-{name}"
    return Download(content=content, media_type=media_type, filename=f"{stem}.{extension}")
