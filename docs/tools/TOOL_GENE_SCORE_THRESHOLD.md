# GeneWeaver Tools — Gene Set Thresholds in Analysis Runs

> Question: Which GeneWeaver analysis tools should take a user-set gene score threshold per run
> (legacy offers none on any tool by default), and should all of them?
> Researched: 2026-10-14. Confidence: high on what the code and data do; medium on the
> recommendation, which is a product decision for curation.
>
> **Status (2026-10-16):** the team decided to let a run turn thresholds **off**, as a single
> run-wide option for every tool. It shipped in PR #39 as `use_threshold`, **on by default**, so
> runs that do not set it behave as before (see [Implementation](#implementation-pr-39)).
> Findings 1 and 3 below describe the code as it was before that change.

## Findings

### 1. In GeneWeaver the gene score threshold belongs to the gene set, not to a tool run
**What:** Each gene set's threshold is set at upload or edit time and stored. "The second column
is a score that can later be used to threshold genes of interest … The user is prompted to provide
a threshold for the scores." The tools' own threshold options are graph and tool statistics:
"Most tools have options for the inclusion of homologous genes and for setting thresholds and
analysis parameters." Table 1 lists those settings as degree and connectivity thresholds, not gene
score cutoffs. The stored threshold is turned into `extsrc.geneset_value.gsv_in_threshold` by
`process_thresholds` (p/q `<` cutoff, correlation/effect in `[low, high]`, binary all in).
**Source:** Baker et al., *GeneWeaver: a web-based system for integrative functional genomics*,
NAR 2012, PMC3245070 (full text via Europe PMC); `packages/db/src/geneweaver/db/query/threshold.py:47-90`
**Confidence:** high
**Action:** A per-run threshold would be a new capability, not parity with legacy.

### 2. Curation's requirement is that tools use the stored threshold, and v3 already does
**What:** GWC-21: "Geneset analysis tools need to use the thresholded genesets, not whole genesets
(if applicable)." Every v3 tool input goes through `resolve_memberships`
(`src/geneweaver/api/services/tools.py:364-370`). That reads `gene_symbols_by_geneset` or
`homologous_gene_symbols_by_geneset`, which filter on `gsv_in_threshold AND gdb_id = 7 AND ode_pref`
(`packages/db/src/geneweaver/db/tool_input.py:63,158`). ABBA does the same
(`packages/db/src/geneweaver/db/query/abba.py:44,123,160,307,325`), and so do BooleanAlgebra
(`tool_input.py:428,433`) and Combine (`tool_input.py:235,259-261`).
**Source:** Jira GWC-21 (reporter: curation), GWC-31; the code above
**Confidence:** high
**Action:** Nothing to add to meet the requirement.

### 3. Before PR #39, no tool, in legacy or v3, had a per-run gene score cutoff
**What:** No tool code path compares `gsv_value`. The only `gsv_value` comparisons are in the code
that persistently sets a gene set's threshold: legacy `/setthreshold/<gs_id>`
(`legacy/src/geneweaverdb.py:1808-1870, 2507-2522`) and v3 `PUT /genesets/{id}/threshold`
(`src/geneweaver/api/controller/genesets.py:300`). These rewrite the gene set for every tool and
every user, and only the owner, a curator or an admin can call them. Every threshold-like option
on a tool form acts on a tool statistic:
- JaccardSimilarity / PhenomeMap `p_value_threshold`: the Jaccard p-value, or the biclique link score;
- ABBA min genes / min gene sets: match counts;
- BooleanAlgebra `at_least`: a number of gene sets;
- GS Graph min degree;
- Triclique: a minimum Jaccard coefficient.

**Source:** the code paths named above; `legacy/src/templates/tool/*_options.html`; `ui/src/app/pages/analyze/tool-options.ts`
**Confidence:** high
**Action:** Informational.

### 4. Legacy was not uniform: a few paths read all genes, and v3 diverges there
**What:** Legacy tools mostly use the in-threshold matrix (`legacy/tools-worker/tools/toolbase.py:33-41`),
except:
- **UpSet** counted **all** genes (`UpSet.py:86-101`, unfiltered `geneset_value`). v3 counts
  in-threshold genes only. Results differ for gene sets with below-threshold genes.
- **HyperGeometric's** "neither set" count (`f00`) started from `COUNT(DISTINCT ode_gene_id)` over
  the pair, with no threshold filter (`toolbase.py:52`, used at `:258`). v3's universe is the
  in-threshold union of the whole request (`src/geneweaver/api/services/tool_inputs.py:143-157`),
  although its docstring says this matches legacy.
- The **MSET** background was every gene in the Tier I–III curated sets
  (`TOOLBOX/mset/backgroundFiles/createBackgrounds.py:57-70`). v3 uses the full species gene space
  (G3-784).
- **Jaccard's** null-distribution population (`TOOLBOX/distribution_generator/fileGenerator.cpp:85`)
  and Triclique's candidate genes (`legacy/src/edgelist.py:52-65`) also ignored thresholds.

v3's uniform in-threshold rule is what GWC-21 asked for. Two of these are still undocumented
behaviour changes that curation has not been asked about: UpSet, and HyperGeometric's docstring.
**Source:** code above (UpSet and `TOOLSET_SQL[4]` checked directly)
**Confidence:** high
**Action:** Record the UpSet change in the migration notes, and fix the HyperGeometric docstring
(or the universe) as its own ticket.

### 5. On dev, the option changes results for about 2% of gene sets (17% of scored ones)
**What:** Non-deprecated gene sets on dev, by score type, with the number that hold any
out-of-threshold gene:

| Score type | Gene sets | With out-of-threshold genes |
| --- | --- | --- |
| binary | 172,363 | 0 |
| p-value | 16,734 | 2,068 (12.4%) |
| q-value | 1,850 | 908 (49.1%) |
| correlation | 1,262 | 215 (17.0%) |
| effect | 2,836 | 576 (20.3%) |

That is 3,767 of 195,045 gene sets, or 3,767 of the 22,682 scored ones. Binary sets have no
score to cut. (The `gene_symbols_by_geneset` docstring says 5.7%; that figure was not
reproduced here.) The four scored types use different rules (`<` for p/q, a
`[low, high]` range for correlation/effect), so one number such as "p < 0.01" means nothing for a
correlation or effect gene set. A per-run setting would need a value per score type, as GWC-49
proposes for search.
**Source:** query against dev's `production.geneset` and `extsrc.geneset_value`, 2026-10-14
**Confidence:** high
**Action:** Any design has to be per score type and has to leave binary sets alone.

### 6. Hard cutoffs make enrichment results depend on an arbitrary choice
**What:** "The input list of genes … is usually obtained using an arbitrary threshold (e.g. …
p-values < 0.05). With this method, marginally less significant genes (e.g. … p-value = 0.051) are
missed, resulting in information loss." Changing the cutoff can change which categories come out
enriched. This is the main published reason to let users vary or sweep the cutoff (e.g. PEBBA,
FDR-FET), and it applies most to over-representation tests: GeneWeaver's HyperGeometric and MSET.
For the set-algebra tools (Boolean, Combine, UpSet, Jaccard), a threshold only changes membership.
**Source:** Khatri, Sirota & Butte, *Ten Years of Pathway Analysis*, PLoS Comput Biol 2012,
PMC3285573; PEBBA, https://github.com/csbl-br/pebba
**Confidence:** medium (well established for ORA in general; not specific to GeneWeaver)
**Action:** If an override is built, enrichment tools gain the most from it.

## Implementation (PR #39)

The run-wide option the summary below describes as the right place, not a per-tool one:

- **Option:** `use_threshold`, default `true`. Off, each gene set contributes every gene it
  holds; on, only its in-threshold genes (GWC-21's rule).
- **Where it applies:** every resolver that loads a tool's genes:
  - `gene_symbols_by_geneset` and `homologous_gene_symbols_by_geneset`;
  - Combine's `membership_rows` and `homology_pairs`;
  - BooleanAlgebra's `homolog_annotations`;
  - ABBA's seed, matching gene sets, result genes, and the per-tier and per-species counts.

  Each filters on `(gsv_in_threshold OR NOT %(use_threshold)s)`, bound as a parameter, and every
  resolver in one run gets the same value.
- **API:**
  - `POST /tools/{tool}` takes `parameters.use_threshold`, parsed strictly like the other flags.
  - `POST /tools/upset` and `POST /tools/abba` take it at the top level.
  - Every response reports it, including a pending 202.
  - ABBA carries it to the worker in `ABBAInput`.
- **UI:** a "Use gene set thresholds" checkbox on `/next/analyze`, checked by default, shared by
  every tool. A result run without thresholds says so.
- **Not done:** the per-score-type values and the "tighten only" rule discussed below. The
  option is all-or-nothing, and any signed-in user can turn it off.

Checked against dev's database (public mouse p-value gene sets):

| | Thresholds on | Thresholds off |
| --- | --- | --- |
| Genes in 821 / 827 / 800 | 34 / 65 / 243 | 163 / 280 / 500 |
| ABBA seeded from 821 | 36 seed genes | 201 seed genes, different top genes |

## Summary (as researched, before the decision)

No tool should get a gene score threshold *parameter* for correctness or legacy parity. In
GeneWeaver the threshold is a property of each gene set, chosen when the data is curated. Every
legacy tool form lacks one, and curation's requirement (GWC-21) was for tools to honour the stored
threshold, which every v3 tool already does at one shared input layer. Adding it to *all* tools is
therefore not recommended.

If a per-run override is wanted for exploration, two things follow from the code:
- It belongs at the request level, in `resolve_memberships` and the ABBA input queries, applied to
  every gene set in the run. A per-tool option is the wrong place, because v3 selects genes once,
  before any tool runs.
- It is most valuable for the enrichment tools, HyperGeometric and MSET, with ABBA's seed next.

Either way, it needs:
- one value per score type;
- to leave binary sets alone;
- and a decision on whether users may *loosen* a curated threshold or only tighten it.

## Open Questions

- **Should curation sign off on the option?** PR #39 lets any signed-in user turn thresholds
  off, which reintroduces genes the curator excluded. GWC-21 (Tessa) asked for thresholds on;
  GWC-49 asks for the same choice in gene search.
- **Should the option go further?** A cutoff per score type, or tightening only, was not built.
- **UpSet:** should v3 keep in-threshold counts, which differ from legacy's all-genes counts? This
  needs curation's sign-off; it fits GWC-21, but it changes published results.
- **HyperGeometric:** which background is intended? Legacy's per-pair all-genes count and v3's
  request-wide in-threshold union differ, and the v3 docstring claims parity.
- **Calculate_jaccard:** the source of the stored procedure behind Find Similar Genesets is not in
  the repository, so its filter could not be checked directly.
