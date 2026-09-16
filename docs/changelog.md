# Changelog

Releases of the GeneWeaver **web application**, newest first.

The version you are using is shown at the bottom of every page on
[geneweaver.org](https://www.geneweaver.org) as *Application Version*.

!!! info "Version numbering"

    A version containing a letter — `1.6.0a`, `1.6.1a` — is a pre-release that goes no
    further than our internal test environment. Only plain versions such as `1.6.0` and
    `1.6.1` reach geneweaver.org. Pre-releases are folded into the entry for the release
    that carries them, so nothing is described twice.

---

## 1.6.2 — unreleased

### Fixed

* **"Find other GeneSets from this publication" works on large publications.** For a
  publication with thousands of gene sets attached the page never finished loading and
  eventually returned an error — the GeneWeaver record for the Gene Ontology Consortium
  paper has 14,799 gene sets, and the page asked the database a separate question about
  every one of them, twice. It now asks once and shows 100 gene sets at a time, with
  Previous / Next links and a count of how many there are in total. The page went from
  not loading at all to well under a second.
* **A gene set with no publication no longer returns an error.** More than half of all
  gene sets have no publication attached, and for those this page failed outright rather
  than saying there was nothing to show. It now shows the same "no other GeneSets"
  message as a publication with a single gene set.
* **The list now shows only the gene sets you are allowed to see.** Permission was being
  checked and then ignored, so on publications that mix public and restricted gene sets
  the page listed the name, description, size, tier and species of sets the viewer had no
  access to. Gene-level data was never exposed. The count now reflects what you can see,
  too.

All three are long-standing — the page has behaved this way since it was added in 2015 —
and are unrelated to the 1.6.0 and 1.6.1 releases.

---

## 1.6.1 — 16 September 2026

A reliability release. **No changes to gene sets, analyses or the interface** — the
application code is identical to 1.6.0.

### Changed

* **The site now serves several requests at once per server process.** It had been serving
  exactly one, which meant a single slow page could make the whole site unresponsive to
  everyone else. Capacity at the minimum deployment size went from two concurrent requests
  to eight.
* **A request that stalls is now abandoned after 60 seconds** instead of 300, so a stuck
  page releases its worker in a minute rather than five.
* **Health checks were added.** A server that is saturated or wedged is taken out of
  rotation automatically, and one that does not recover is restarted. Readiness now also
  depends on the search service being ready, so a server cannot accept searches before its
  index is available.
* **Every outbound call now has a time limit.** Searches wait at most two seconds for the
  search service, and PubMed and SRA lookups are bounded. An SRA lookup that times out or
  is rate-limited now leaves the publication metadata blank instead of failing the gene set
  page.

---

## 1.6.0 — 15 September 2026

The first release built from the consolidated GeneWeaver repository, replacing **1.5.27**.
It gathers roughly a year of fixes, including work that had been merged but never reached
geneweaver.org, so it is much larger than a normal release. The pre-releases `1.6.0a`,
`1.6.0b` and `1.6.0c` are included here.

### Gene set membership and gene counts changed

!!! warning "Some gene sets are a different size after this release"

    Three long-standing defects meant stored membership did not match the threshold rules
    the interface described. Correcting them changed which genes are in threshold on
    existing, published gene sets — so analysis results on those sets change too. This is
    the correction landing, not new damage. If a set of yours looks different, the
    explanations below are the likely reason.

* **Binary gene sets were unusable and now work.** A binary (membership) set records
  presence with a value of `1`, but the database was testing `value > 1`, so *every* gene in
  such a set was marked out of threshold. The sets existed, looked populated on their own
  page, and returned nothing in every analysis tool. Whole sets went from unusable to
  usable.
* **Correlation and Effect thresholds now use the signed value, not its magnitude.** A
  range such as `6.0 < Effect < 22.5` was also admitting values between −22.5 and −6.0,
  because the comparison discarded the sign. Sets with an asymmetric range get **smaller**
  where negative values were wrongly included — and, where the range is itself negative,
  **larger**, because a magnitude can never fall inside a negative range. Symmetric ranges
  are unaffected.
* **Gene counts in search results and *My GeneSets* are now derived from the genes actually
  stored.** Three separate upload paths recorded a count taken from something other than the
  saved genes — submitted lines including a trailing blank one, staged rows before duplicate
  identifiers were merged, or one row per identifier rather than per gene. Search and the
  gene set page therefore disagreed, always with search over-counting. The count is now
  computed after the genes are saved, which makes it **honest rather than larger**: where
  identifiers failed to resolve, the number shown goes down.

### Fixed — curation and upload

* **Ontology annotations could not be generated at all**, broken since around June 2025.
  Annotation also now offers only the ontologies that are actually supported; the
  non-functional Monarch and "Both" options are hidden.
* **Genes were silently dropped on upload.** An identifier that was an alias or synonym
  rather than a gene's official symbol was discarded with no warning, so an uploaded set was
  quietly smaller than the list submitted.
* **Score values are now validated on upload**, on both single and batch upload, instead of
  out-of-range or invalid values being accepted silently. A gene set's score type can also be
  changed after upload.
* **A batch P-Value or Q-Value threshold could never take effect.** A header such as
  `P-Value < 0.05` was parsed as a whole line where a bare number was expected, so every
  thresholded line fell through and the cutoff was silently replaced with the default `0.05`.
  Malformed variants (`P-Value > 0.01`, `P-Value 0.01`) were treated as a deliberate default
  and also replaced the cutoff with no warning; they are now reported.
* **Changing a score type from Correlation or Effect to P-Value or Q-Value lost the change.**
  The two-sided types hold a `low,high` pair and the one-sided types hold a single number, and
  saving a pair under a one-sided type failed with only *"An unknown error ocurred."* The
  threshold field now reshapes when the score type changes, the previous value is remembered
  per score type so switching back restores it, and where a default has to be substituted you
  are told.
* **Changing a score type now checks the values against it**, warning — not blocking — when
  existing values make no sense under the new type, matching what upload already did.
* **Creating a gene set from a tool result silently dropped genes.** The gene list was
  resolved through the homology table, so any gene absent from Homologene could not survive —
  even when transposing within a single species, where nothing needs transposing. Measured on
  one real set: 6 of 115 genes lost, with no warning anywhere. Unchanged since April 2018.
* **Gene sets created by analysis tools skipped threshold processing entirely**, carrying
  membership from a hardcoded rule that matched no score type and was applied before the score
  type was known. Both creation routes now use the same threshold logic as every other path.
* **Changing a gene set's tier from the admin page had no effect**, and some gene sets
  returned an error when opening the edit view.

### Fixed — search

* **Search results were only as fresh as the last server restart.** The search index was
  built once when a server started and never again, so a new or edited gene set could be
  missing from search for weeks. The index is now refreshed every 15 minutes with a full
  rebuild nightly. Saving an edit also updates the gene set's modification time, which it
  previously did only when the edit page was *opened* — so an edit saved from a
  long-open page could never be picked up.
* **Zero-result and unsorted searches returned an error** instead of an empty result page.
* **Clearing every option in a filter returned nothing at all**, rather than meaning "no
  restriction".
* **Find Similar GeneSets compared a filtered set against unfiltered candidates**, inflating
  similarity scores. On a sample of 300 candidate sets, 67 were affected.
* **Find Similar GeneSets and the Jaccard Similarity tool now agree.** Genes with no
  homology entry were dropped by one and kept by the other.

### Fixed — analysis tools

* **Boolean Algebra's Symmetric Difference returned an error.** A diagram failure also no
  longer blanks the whole visualisation when comparing three or more sets.
* **MSET reported "list not a subset of its background"** for valid input, after a gene
  data reload left the backgrounds stale.
* **MSET gave a cryptic server error for Tier IV gene sets.** Such a set can contain real
  genes that fall outside the curated background, which MSET correctly cannot use. You now
  get a readable message naming how many genes are outside the background and which they
  are, instead of a generic error. The underlying limitation is unchanged and deliberate.
* **MSET internal errors** from an incomplete Python 3 migration, and a worker crash that
  used the wrong background for the second list.
* **DBSCAN crashed when a run produced no clusters.** A run with no clusters is now a
  result, not an error.
* **Diagram-producing tools failed when the graph renderer was not at an expected path.**
* **Jaccard Similarity reported a p-value of 0** for any pair of gene set sizes not already
  in its sampling cache, and the caches were missing in some environments.

### Security

Both of the following affect earlier versions. If you run your own GeneWeaver instance, they
are the reason to upgrade.

* **The admin data-table endpoints accepted SQL through request parameters** and ran it
  unbound, which allowed statements beyond reading — and two of the four endpoints turned out
  not to require an administrator, or any login, at all. The same two also took the user
  whose gene sets and tool results to list from the request, so anyone could list another
  user's by guessing an identifier. All parameters are now bound, table and column names are
  checked against a fixed list, and the user is taken from the session.
* **An authentication client secret was written to the server log** on every start-up. It no
  longer is. Anyone self-hosting a version before 1.6.0 should treat that secret as exposed
  and rotate it.

### Added

* **Batch upload accepts pasted text**, not only a file.

### Changed — where a value exactly on its threshold belongs

For P-Value and Q-Value gene sets, a value **exactly equal** to the cutoff is **outside** the
threshold. Two parts of the application had disagreed about this for years, so a value on its
cutoff could be a member or not depending on which one last saved the set.

The behaviour every environment has actually stored was the exclusive rule, and it was kept:
no gene set's membership was changed by this decision. Choosing the other reading would have
retroactively added genes to roughly 600 published gene sets per environment, some created as
far back as 2007, which is a change to the scientific record rather than a fix. The
*Set Threshold* preview count, which had used the inclusive rule and could therefore promise
more genes than the set would end up holding, now matches. Correlation and Effect ranges
remain inclusive at both ends, which was never in question.

### Known issues

* **Some gene sets claim genes while holding none.** A number of older gene sets record a
  gene count but contain no genes. The count was deliberately left alone rather than reset to
  zero: where genes may have been lost, a stale number is a better record than an authoritative
  zero. Being investigated separately.
* **MSET cannot run against gene sets whose genes fall outside the curated background.** The
  error message is now clear about why; the limitation is unchanged, and is expected to be
  resolved by the next generation of the analysis tools.
* **A threshold of `NaN` puts every gene in threshold.** The database accepts the spelling and
  treats it as greater than any number. Correcting it would move published membership, so it is
  being handled as a curation decision rather than a defect fix. No live gene set currently has
  one.
* **"Find other GeneSets from this publication" fails on very large publications.** For a
  publication with thousands of associated gene sets the page does not finish loading, and for
  a gene set with no publication it returns an error. Long-standing — present in every earlier
  version. **Fixed in 1.6.2.**
