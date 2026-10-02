# Jira ticket — ready to paste

**Project:** G3 · **Issue type:** Bug · **Epic / parent:** G3-754
**Components:** legacy · **Labels:** legacy, performance, n+1, authorization
**Priority:** suggest Medium (contained by 1.6.1; still a 500 on a public route)

---

## Summary (issue title)

`/findPublications` runs one permission query per sibling gene set: 60s timeouts on large publications, and a 500 when the gene set has no publication

---

## Description

### What is wrong

`/findPublications/<gs_id>` — the *"Find other GeneSets from this publication"* link on every gene set
page — runs a separate database round trip for **every** gene set that shares the publication, then
throws the results of those queries away. On the largest publications that is ~15,000 sequential
queries in one request, and the request never finishes inside Gunicorn's 60-second worker timeout.

Confirmed live against prod (1.6.1, 2026-09-16):

| request | result |
| --- | --- |
| `GET /findPublications/374128` (publication has 14,799 gene sets) | **HTTP 500 after 61.1 s** — Gunicorn killed the worker mid-request |
| `GET /findPublications/408661` (gene set has no publication) | **HTTP 500 in 0.17 s** — SQL syntax error |

This is long-standing, not a 1.6.1 regression: `/findPublications` appears in prod's error log on
2026-08-23, 08-25, 09-04, 09-10, 09-11, 09-12, 09-13 and 09-14, i.e. on the previous release as well.
What changed in 1.6.1 is that it is now *contained* — four workers per pod instead of one, and a 60-second
timeout instead of 300 — so one of these requests no longer takes the site with it. It is still 6 of the
10 worker timeouts prod has had in the 8 hours since the 1.6.1 deploy.

### Root cause

`geneweaverdb.get_similar_genesets_by_publication()` — `legacy/src/geneweaverdb.py:4340-4372`.

```python
cursor.execute('''SELECT gs_id FROM geneset WHERE pub_id IN
                  (SELECT pub_id FROM geneset WHERE gs_id=%s)''', (geneset_id,))
for r in cursor.fetchall():
    gs_ids.append(r[0])

for gs_id in gs_ids:                                        # (1) one round trip per sibling
    cursor.execute('''SELECT geneset_is_readable2(%s, %s)''', (user_id, gs_id))
    if cursor.fetchone()[0]:
        gs_ids_clean.append(gs_id)                          # (2) never used again

# s = ','.join(gs_ids_clean)
cursor.execute(cursor.mogrify(                              # (3) %-interpolation; IN () when empty
    '''SELECT geneset.* FROM geneset WHERE geneset.gs_id IN (%s)'''
    % ",".join(str(x) for x in gs_ids)))                    #     ^ gs_ids, not gs_ids_clean
```

Four distinct defects in fourteen lines:

1. **N+1 permission loop.** `geneset_is_readable2` is called once per sibling, each as its own round
   trip. Measured on prod for `gs_id = 374128`:

   | stage | time |
   | --- | --- |
   | sibling id lookup | 0.02 s |
   | **14,799 × `geneset_is_readable2` round trips** | **18.62 s** (1.26 ms each) |
   | final `SELECT geneset.*` (14,799 rows) | 0.37 s |
   | **database total** | **19.01 s** |

   The remaining ~40 s to the 60 s timeout goes on constructing 14,799 `Geneset` objects and rendering
   all of them into a single page — `viewsamepublications.html` has no pagination and no limit.

2. **The permission filter is computed and discarded.** `gs_ids_clean` is built by the loop and then
   never read; the final query uses the unfiltered `gs_ids`. So the 18.62 s buys nothing — and the
   route returns gene sets the visitor is not allowed to read. The commented-out
   `# s = ','.join(gs_ids_clean)` immediately above shows the original intent.

   This is not merely theoretical. On prod: **170 publications** contain a mix of readable and
   non-readable gene sets, and **14,630** gene sets are not readable by an anonymous visitor. The route
   has no `@login_required` and passes `user_id = 0` for anonymous callers, and
   `viewsamepublications.html` prints `name`, `abbreviation`, `description`, `count`, `cur_id`, `sp_id`
   and `attribution` for every gene set it is handed. So on those 170 publications an anonymous visitor
   is shown the metadata of gene sets the permission check had already marked unreadable. Gene *values*
   are not exposed by this template.

3. **Empty sibling list produces invalid SQL.** When the gene set's `pub_id` is `NULL`,
   `pub_id IN (SELECT pub_id ... )` matches nothing, `gs_ids` is empty, and the final query becomes
   `... WHERE geneset.gs_id IN ()` → `SyntaxError: syntax error at or near ")"` → HTTP 500.
   **154,651** of prod's gene sets (56%) have no `pub_id`. The UI link is only rendered when a PubMed
   id exists, so this path is reached by direct URL rather than by clicking — which is exactly what
   crawlers walking `/findPublications/<n>` do.

4. **`%`-interpolation of a query string**, against the repository's database guardrail in `CLAUDE.md`
   ("Parameterise SQL — never `%`-interpolate a query string"). The interpolated values are integers
   that came from the database, so this is not injectable today; it is the prohibited pattern, and it
   is what makes defect 3 possible.

### Effect

* **37,745 gene sets** (of 275,711) belong to a publication with more than 1,000 gene sets, so their
  *"Find other GeneSets from this publication"* link cannot complete. The four publications
  responsible:

  | pub_id | gene sets | |
  | --- | --- | --- |
  | 8461 | 14,799 | PMID 10802651 — *Gene ontology: tool for the unification of biology* |
  | 79099 | 7,976 | |
  | 1 | 7,715 | |
  | 104 | 7,255 | |

* **154,651 gene sets** return a 500 on this route by direct URL.
* **170 publications** disclose unreadable gene set metadata to anonymous visitors.
* Each affected request occupies one Gunicorn worker for the full 60 seconds. Prod runs 4 workers per
  pod across 2–8 pods, so this is now bounded — but it was one of the paths amplifying the
  2026-09-16 outage, when a pod had a single worker and a 300-second timeout.

### Suggested fix

1. **Do the permission filter in SQL**, in the query that already selects the rows — one statement
   instead of N+1:

   ```sql
   SELECT g.* FROM geneset g
   WHERE g.pub_id = (SELECT pub_id FROM geneset WHERE gs_id = %(gs_id)s)
     AND geneset_is_readable2(%(user_id)s, g.gs_id)
   ORDER BY g.gs_id
   LIMIT %(limit)s OFFSET %(offset)s
   ```

   This also fixes defect 2 by construction: there is no separate list to forget to use. Note the
   `pub_id = (SELECT …)` form returns no rows for a `NULL` publication instead of building `IN ()`,
   which fixes defect 3, and it is fully parameterised, which fixes defect 4.

2. **Bound the result set.** Paginate `viewsamepublications.html`, or cap it and show a count with a
   link to the publication's search results. 14,799 gene sets in one page is not usable even if it
   were fast.

3. **Handle "no publication" explicitly** in the route — render an empty state rather than relying on
   a query returning zero rows.

4. Consider whether the route should exist unauthenticated at all, given it enumerates gene sets by
   publication.

### Acceptance criteria

* `GET /findPublications/374128` returns 200 in under 2 s.
* `GET /findPublications/408661` (no publication) returns a rendered empty state, not a 500.
* For a publication that mixes readable and non-readable gene sets, an anonymous request returns
  **only** the readable ones. A regression test should pin this — pick one of the 170 publications.
* No `/findPublications` entry appears in prod's `WORKER TIMEOUT` log for a week after deploy.

### How the numbers above were obtained

All measured against `geneweaver-prod` on 2026-09-16, read-only, from inside a prod web pod:

* Worker timeouts: Cloud Logging, `resource.labels.container_name="geneweaver-legacy"`,
  `textPayload:"WORKER TIMEOUT"` / `"Error handling request"`.
* Stage timings: the three statements of `get_similar_genesets_by_publication` run in order against
  `gs_id = 374128` with `search_path` set as the app's pool sets it.
* Blast radius: `GROUP BY pub_id HAVING count(*) > 1000`; `count(*) WHERE pub_id IS NULL`.
* Authorization: publications where `bool_or(geneset_is_readable2(-1, gs_id))` and
  `bool_or(NOT geneset_is_readable2(-1, gs_id))` are both true.
* The two live requests in the table at the top, via `curl` against `https://geneweaver.jax.org`.
