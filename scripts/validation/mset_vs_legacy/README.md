# MSET: v3 against the legacy worker (G3-784)

Checks the two things G3-784 left unverified once MSET's background came from the database:

1. **A Tier-IV gene set legacy refuses runs on v3.** GS407805 (human, Tier IV) is the
   reference case from GWC-51 / G3-783.
2. **v3 gives legacy's results on real gene sets**, per the §9 pattern in
   `docs/tools/TOOLS_MIGRATION.md`. The comparison holds the universe fixed, which isolates
   the port from the rule change. Then it measures the rule change on its own.

Everything runs where the tools really run: legacy's half in the legacy tools worker pod, and
v3's half in the v3 native tools worker pod, which is the image AsyncTask schedules MSET on,
with the real `MSETcpp`. All database access is read-only.

## Scripts

| script | pod | what it does |
|---|---|---|
| `legacy_side.py` | `geneweaver-legacy-tools` | Samples curated (Tier I–III) gene-symbol pairs. Resolves each list with legacy's own query and runs `MSETcpp` exactly as `MSET.py` does, against the background file legacy reads in that environment. |
| `v3_side.py` | `geneweaver-tools-native-worker` | Reruns those pairs through v3's resolvers and `MSET` tool, against legacy's background and then against the full gene space the worker resolves. |
| `tier4_check.py` | `geneweaver-tools-native-worker` | Builds the request as the API does, with a universe reference, expands it through the worker's resolver, and runs MSET. |

## Running on dev

```bash
L=geneweaver-legacy-tools N=geneweaver-tools-native-worker D=scripts/validation/mset_vs_legacy

# 1. Legacy: its lists, its background, its binary.
kubectl -n dev exec -i deploy/$L -c $L -- sh -c 'cat > /tmp/mset_legacy_side.py' < $D/legacy_side.py
kubectl -n dev exec deploy/$L -c $L -- python /tmp/mset_legacy_side.py 5000 6 784 > legacy.jsonl
for f in GeneSymbolMusmusculusBG.txt GeneSymbolHomosapiensBG.txt; do
  kubectl -n dev exec deploy/$L -c $L -- cat /var/geneweaver/results/mset_backgrounds/$f > $f
done
kubectl -n dev exec deploy/$L -c $L -- rm -f /tmp/mset_legacy_side.py

# 2. v3: the same pairs, both universes; then the Tier-IV case.
kubectl -n dev exec deploy/$N -- mkdir -p /tmp/mset_vs_legacy
for f in GeneSymbolMusmusculusBG.txt GeneSymbolHomosapiensBG.txt legacy.jsonl \
         $D/v3_side.py $D/tier4_check.py; do
  kubectl -n dev exec -i deploy/$N -- sh -c "cat > /tmp/mset_vs_legacy/$(basename $f)" < $f
done
kubectl -n dev exec deploy/$N -- env MSET_LEGACY_BG_DIR=/tmp/mset_vs_legacy \
  python /tmp/mset_vs_legacy/v3_side.py /tmp/mset_vs_legacy/legacy.jsonl 5000 > v3.jsonl
kubectl -n dev exec deploy/$N -- python /tmp/mset_vs_legacy/tier4_check.py 407805,218676
```

When you're done, remove the copied files from `/tmp/mset_vs_legacy` in the v3 pod.

On dev, legacy reads the backgrounds regenerated onto the results volume
(`/var/geneweaver/results/mset_backgrounds`, the GWC-45 fix). `legacy_side.py` resolves
them the way `MSET.py` does, so it reads the same files in any environment.

## Results on dev, 2026-11-24

### 1. GS407805 runs on v3

The pair is GS407805 (human, Tier IV) with GS218676 (human, Tier III), as in the release plan.

| | legacy | v3 |
|---|---|---|
| genes in GS407805's list (uploader threshold) | 5,319 | 5,319 |
| genes outside the universe | **63** (`LINC02853`, `LINC02133`, `LINC02641`, `LINC01285`, `HPYR1`, …) | **0** |
| universe | 30,711 (curated genes) | 40,956 (every human gene) |
| outcome | refused: "not a subset of its background" | **runs**: 266 shared genes, p < 0.001, 1.6 s |

With every gene rather than the uploader's threshold (9,623 genes), v3 also runs, in 5.5 s.

### 2. v3 matches legacy

These are 12 curated pairs (seed 784) at 5,000 trials. Legacy's lists and v3's are the same
size for every pair, and so are the shared genes and, with legacy's background, the universe.

| Pair | Species | Genes | Shared | Legacy p | v3 p, legacy's universe | v3 p, full universe |
|---|---|---|---:|---:|---:|---:|
| 229457, 378249 | mouse | 193, 204 | 8 | 0.0000 | 0.0000 | 0.0000 |
| 84293, 167323 | mouse | 548, 775 | 13 | 0.5694 | 0.5494 | **0.0128** |
| 136969, 167307 | mouse | 435, 623 | 14 | 0.0416 | 0.0424 | 0.0000 |
| 166289, 169589 | mouse | 105, 333 | 17 | 0.0000 | 0.0000 | 0.0000 |
| 233499, 230790 | mouse | 201, 192 | 2 | 0.3348 | 0.3378 | 0.1140 |
| 227304, 229184 | mouse | 196, 160 | 2 | 0.2498 | 0.2442 | 0.0854 |
| 392132, 125159 | human | 243, 240 | 16 | 0.0000 | 0.0000 | 0.0000 |
| 230124, 227711 | human | 420, 198 | 4 | 0.2818 | 0.2774 | 0.1462 |
| 396651, 242336 | human | 452, 313 | 11 | 0.0070 | 0.0062 | 0.0010 |
| 232531, 370294 | human | 248, 490 | 2 | 0.9094 | 0.9036 | 0.8026 |
| 235493, 366579 | human | 699, 193 | 27 | 0.0000 | 0.0000 | 0.0000 |
| 397987, 372649 | human | 178, 169 | 7 | 0.0000 | 0.0002 | 0.0000 |

- **With the same universe, v3 reproduces legacy.** The largest p difference is 0.020, at
  p ≈ 0.56. Two independent 5,000-trial runs of the same test differ by about 0.010 there
  (one standard deviation), so 0.020 is about two standard deviations, within Monte Carlo
  error. The port changes nothing but the universe.
- **The full universe only ever lowers p.** Mouse's universe doubles (32,356 → 66,866) and
  human's grows a third (30,711 → 40,956). Two mouse pairs cross α = 0.05:
  84293/167323 drops from 0.57 to 0.013, and 136969/167307 from 0.042 to below 0.001.
  - This sample is small, and it keeps only pairs that share at least two genes. So it
    shows the direction of the shift, not its rate. The rate over 200 random pairs per
    species is in the A7 decision note (`docs/v3/V3_ROADMAP_AND_GAP.md`), from
    `scripts/analysis/mset_universe_impact/`.

MSETcpp names the *second* list it's given "List 1" in its output (in legacy as well as
v3), so "List 1 Size" is the second gene set's size. That's the binary's labelling, not a
swap in either caller.
