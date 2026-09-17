# Optimization

What is optimized, how, with which weights, and what the result means.
Numbers in this file are produced by the scripts named in each section and
are checked against the committed artifacts by `tests/test_docs.py`.

## 1. What is optimized

A **layout** assigns each of the 257 mother-set identifiers to one
cell of a W × H grid; the remaining cells are structural blanks. The
objective is a weighted sum of the components below, computed by
`cldrmap/scoring.py` from three inputs (`SOURCES.md`): representative
points, land-adjacency pairs, and CLDR/M49 subregions. All components are
"lower is better"; each is normalized to a per-item or per-pair scale so
that grids of different size are comparable. Every pairwise component has
the form Σ F[i,j] · D[cell_i, cell_j], which lets the optimizer evaluate a
move in O(n), and `scripts/score_layout.py` recomputes everything from
scratch for any board.

| component | definition | why it exists | default weight |
|---|---|---|---|
| `neighborhood` | mean grid Euclidean distance (cells) from each identifier to its 6 nearest geographic neighbours (great-circle) | local topology: places that are near each other should be near on the board; rank-based so intercontinental distances do not dominate | 1.0 |
| `global` | 1 − cov(√geo-distance, grid distance) / (σ_√geo · σ_grid-reference), over all pairs | keeps the overall shape of the world (continents in the right places); √ compresses long distances | 0.5 |
| `adjacency` | mean gap over land-border pairs: 0 if orthogonally adjacent, 0.5 if only diagonal, else Chebyshev distance | land neighbours should touch | 2.0 |
| `direction` | mean reversal in cells over eligible east–west and north–south relations (pairs in the same continent or within 12 nearest neighbours, separated by ≥ 12° longitude or ≥ 8° latitude): 0 if the western/northern one is strictly west/north, 1 if in the same column/row, k+1 if k cells reversed | no mirrored continents or reversed chains; thresholds keep it from enforcing strict longitude order at small scales | 2.0 |
| `region` | mean intra-subregion grid distance ÷ that of the most compact blob of the same size, − 1, averaged over CLDR/M49 subregions (QO members excluded) | recognizable regions stay coherent; the M49 classification is an input, never the mother-set authority | 1.0 |
| `false_adjacency` | per identifier: number of orthogonally adjacent cell pairs (0.5 for diagonal) whose identifiers are > 2000 km apart, share no land border, and are not within each other's 12 nearest neighbours | misleading proximity is worse than missing proximity | 1.0 |
| `whitespace` | share of blank cells that are enclosed holes (1.0 if all four orthogonal neighbours are occupied, 0.25 if three) | blanks should read as seas or margins, not as missing data; where the blanks go is otherwise left to the other components | 0.5 |
| `legacy` | fraction of the 250 shared identifiers whose cell differs from the `8bit` board after the best integer translation (mean Manhattan displacement also reported) | reported for continuity; **weight 0** so legacy stability never blocks a better complete layout | 0.0 |

Parameters: k = 6 (neighborhood), k = 12 (direction eligibility and
false-adjacency exclusion), 12° / 8° direction thresholds, 2000 km
false-adjacency distance, longitude cut at 125° W (`DECISIONS.md` D7).
QO members (AC, AQ, CP, DG, TA) carry CLDR's continent code 009 (Oceania) and therefore fall into the same-continent eligibility set of the direction term with the Oceania identifiers; this is a consequence of using CLDR's containment verbatim and is harmless in practice (their k-nearest relations dominate), but it is noted here rather than corrected.

Diagnostics reported alongside the components: Spearman correlation of
geographic vs grid distance, land-border pairs kept orthogonal / within one
cell, number of reversed direction relations, 8-connected components per
subregion, blank-cell components, and legacy displacement.

### What is not optimized

- Maritime adjacency as such (sea neighbours act only through the
  neighbourhood, global, and false-adjacency terms).
- Administrative parentage (Guernsey is not pulled toward the UK; Réunion is
  not pulled toward France). Geographic location wins; the `direction`
  eligibility set and the `region` term use CLDR/M49 subregions, which
  place overseas territories by geography.
- Visual balance of the silhouette, the recognisability of particular
  shapes, or any target picture. There is no hand-drawn target in the
  objective; the territory-map constraint exists (`design/README.md`) but
  was not used for the selected board.

## 2. Search

`cldrmap/optimize.py`: simulated annealing.

- **State**: one identifier per cell; blanks are free cells.
- **Start**: quantile-scaled unwrapped longitude / latitude, assigned to
  cells by linear sum assignment (`baselines.rank_projection`). The same
  start is used for every seed and every grid.
- **Moves**: relocate one identifier to (a) a cell within Chebyshev radius 2
  of its current cell (probability 0.7), (b) a cell adjacent to one of its
  6 geographic neighbours (0.2), or (c) any cell (0.1); if the target is
  occupied the two identifiers swap.
- **Cooling**: geometric from t0 = 0.02 to t1 = 1e-4 over the iteration
  budget. The best state seen is kept and re-scored from scratch.
- **Determinism**: `numpy.random.default_rng(seed)`; the layout JSON records
  seed, seeds tried, budget, temperatures, move parameters, weights, and
  the full score of the result.
- **Stopping**: fixed iteration budget (no convergence test).

Calibration on 19 × 14 (seed 1, first objective version, `DECISIONS.md` D9):
t0 = 0.05 / 0.02 / 0.01 / 0.005 at 300 k iterations gave 4.39 / 3.93 / 3.73 /
3.84; 0.02 at 600 k gave 3.61; radius 2 with 90 % local moves at 300 k gave
3.78. Budget scaling with the current objective is in § 4.

## 3. Grid comparison

Seven grids, identical objective, weights, start rule, seeds 1–4 and budget (3 M iterations per seed; `reports/grid-comparison.md`, `reports/grid-comparison.json`, layouts in `layouts/candidates/`). Scores are combined objective values, lower is better; component columns are for the best seed.

| grid | blanks | aspect | best | mean | worst | neighborhood | adjacency | direction | region | false adj. | land pairs orthogonal | reversed relations | region excess components | holes | rank-projection start |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 17x16 | 15 | 1.062 | **3.695** | 3.717 | 3.760 | 1.816 | 0.457 | 0.119 | 0.185 | 0.377 | 188/324 | 775 | 4 | 0 | 4.790 |
| 18x15 | 13 | 1.200 | **3.614** | 3.700 | 3.758 | 1.774 | 0.441 | 0.104 | 0.201 | 0.391 | 184/324 | 675 | 4 | 0 | 4.762 |
| 19x14 | 9 | 1.357 | **3.676** | 3.699 | 3.736 | 1.727 | 0.535 | 0.131 | 0.171 | 0.305 | 181/324 | 805 | 2 | 0 | 4.770 |
| 20x13 | 3 | 1.538 | **3.730** | 3.749 | 3.775 | 1.773 | 0.523 | 0.132 | 0.156 | 0.358 | 178/324 | 808 | 2 | 0 | 4.803 |
| 20x14 | 23 | 1.429 | **3.549** | 3.571 | 3.582 | 1.721 | 0.512 | 0.099 | 0.186 | 0.286 | 179/324 | 630 | 2 | 0 | 4.694 |
| 22x12 | 7 | 1.833 | **3.729** | 3.764 | 3.789 | 1.793 | 0.508 | 0.127 | 0.206 | 0.346 | 182/324 | 811 | 4 | 0 | 4.792 |
| 24x12 | 31 | 2.000 | **3.596** | 3.641 | 3.677 | 1.776 | 0.523 | 0.105 | 0.157 | 0.235 | 185/324 | 684 | 3 | 1 | 4.741 |

Baselines for scale (same weights): the `8bit` board scored on its 250 identifiers = 6.620; the naive 8bit extension (16 × 17, seven new identifiers in blank cells and an added row) = 7.298; alphabetical 19 × 14 = 35.877; region-bucket 19 × 14 = 25.861.

Reading the table:

- **20 × 14 is best on every seed**: its worst seed (3.582) beats every other grid's best seed (24 × 12: 3.596; 18 × 15: 3.614; the rest ≥ 3.676), and its mean (3.571) is 0.07 below the next mean (24 × 12: 3.641). It has the best neighbourhood and direction components (22 × 12 has the best global value, 24 × 12 the lowest false-adjacency value); its 23 blank cells are absorbed as an Arctic margin, an Indian Ocean block between Africa and South-East Asia (with DG as an island in it), a South Atlantic column, and Pacific corners.
- 17 × 16, 18 × 15 and 19 × 14 are indistinguishable within seed noise (means 3.70–3.72; seed spreads up to 0.14). The 19 × 14 hypothesis of the project brief is therefore neither confirmed nor refuted against its immediate neighbours, but it is clearly beaten by 20 × 14.
- 20 × 13 (3 blanks) and 22 × 12 (7 blanks, aspect 1.83) are the worst annealed results: too little whitespace and too flat a board both cost neighbourhood and adjacency quality.
- 24 × 12 (31 blanks) is second best and is the only candidate that opens an Atlantic gap between the Caribbean and Europe, but it is worse than 20 × 14 on the combined score, wider than a typical world map, and its extra whitespace mostly fragments (holes = 1, whitespace term highest).
- The score is not monotonic in the number of blanks (24 × 12 with 31 blanks loses to 20 × 14 with 23; 17 × 16 with 15 ties 19 × 14 with 9), so the comparison is not simply rewarding larger boards.

## 4. Selected grid and layout

The selected board is `layouts/cldr-48.2-regular-2alpha-20x14.json` (`board.csv`, `metadata.json`, `docs/board.svg` are derived from it).

- **Grid**: 20 × 14 square cells, 257 identifiers, 23 structural blanks, aspect 1.43.
- **Search**: `scripts/optimize_layout.py --grid 20x14 --iterations 5000000`, one chain per seed for seeds 1–8 (seed 1: 3.509, seed 2: 3.580, seed 3: 3.549, seed 4: 3.546, seed 5: 3.542, seed 6: 3.512, seed 7: 3.540, seed 8: 3.544); the best chain, **seed 1**, was kept and re-scored from scratch. Budget scaling on this grid: 3 M iterations gave 3.549–3.582 over seeds 1–4; 5 M gave 3.509–3.580 over seeds 1–8.
- **Combined score 3.509** with default weights. Components: neighborhood 1.767, global 0.240, adjacency 0.481, direction 0.105, region 0.156, false_adjacency 0.276, whitespace 0.033, legacy 0.960 (weight 0).
- **Diagnostics**: 185 of 324 land-border pairs orthogonally adjacent and 275 within one cell; 683 of 8958 eligible direction relations reversed; subregions form 2 extra connected components in total; 71.0 false-adjacent pairs; 23 blanks in 7 groups with 0 enclosed holes; Spearman correlation of geographic vs grid distance 0.781 (8bit: 0.631).
- **Legacy**: after the best integer alignment (offset [3, -1]), 240 of 250 shared identifiers changed cell; mean Manhattan displacement 3.58 cells, mean Euclidean 2.82. The board is a new arrangement, not a patch of `8bit`; continuity is at the level of conventions (Atlantic-centred, north up, Americas left, Oceania bottom right) rather than cells.
- **Baselines on the same grid**: rank projection 4.694, region bucket 25.757, alphabetical 37.500; the `8bit` board scored on its 250 identifiers 6.620; the naive extension 7.298.
- **No manual pins** were applied; the committed board is exactly the optimizer output.

## 5. Sensitivity

`scripts/sensitivity.py` (seed 1, 1.5 M iterations per variant; `reports/sensitivity.md`, `reports/sensitivity.json`). For each component the weight was halved and doubled (14 variants), plus a variant that gives the legacy term weight 1.0. For every variant the table reports (a) the selected board re-scored under the variant weights, (b) a board re-optimized from the same start under the variant weights, (c) that board's score under the default weights, and (d) how far it moved from the selected board.

Findings:

- **The selected board is never beaten by a re-optimization under any variant** at this budget: in all 15 variants the selected board scored better under the variant's own weights than the board re-optimized for it (e.g. default: 3.509 vs 3.626). This mostly reflects the budget gap (5 M vs 1.5 M iterations) and shows that the selected board sits in a basin that stays good when weights move by a factor of two.
- **Re-optimized boards move little.** Between 61% and 82% of identifiers change cell relative to the selected board, but the mean Manhattan displacement is only 1.01–1.68 cells: the continental structure is stable and weight changes reshuffle neighbours locally.
- **Under the default weights, every re-optimized variant board scores 3.614–3.742**, i.e. within about 0.13 of each other; no plausible weight change produces a board that the default objective considers substantially different in quality.
- **Legacy weight 1.0 changes nothing in the search.** The legacy term is report-only: it is not part of the annealer's energy (only the seven pairwise/whitespace terms are), so the `legacy_1.0` row re-optimizes to exactly the default board (4.622 under its own weights = 3.626 + 1.0 × 0.996). Making legacy stability an optimization target would require adding a per-identifier position term to `cldrmap/optimize.py`; it was deliberately not done for the initial release (`DECISIONS.md` D8).
- **Per-component sensitivity is below the noise floor.** Under the default weights the re-optimized variant boards range from 3.614 (`region_half`) to 3.742 (`whitespace_half`), a spread of 0.13 that is comparable to the seed-to-seed spread of the 3 M grid comparison (up to 0.14) and larger than the 5 M eight-seed spread (0.07). With one seed per variant, no single component can be said to matter more than another; the honest summary is that halving or doubling any one weight yields boards of similar quality that differ locally.

Limits: one seed per variant and a smaller budget than the selected board; the analysis bounds the *direction* of weight effects, not the best achievable score under each variant.

## 6. Human cartographic review

Conducted on the annealed boards of all seven grids (4 seeds) and on the eight 5 M-iteration boards for 20 × 14, by reading the boards as identifier grids and as subregion-letter maps and by inspecting the SVG previews.

Findings that supported the selection:

- Continents are where a reader expects them: Americas in the left five columns, Europe top-centre, Africa centre-bottom, Asia right, Oceania bottom-right, Antarctica on the bottom row.
- The 23 blanks form seas: a North Atlantic gap (cells (3,0), (3,1), (4,1), (4,2)) between Greenland/US Virgin Islands/Anguilla on the American side and Iceland/Isle of Man/Guernsey on the European side; a South Atlantic between South America and West/Southern Africa holding AC, SH, TA, BV, GS as an island column; an Indian Ocean block between the Horn of Africa and Micronesia with DG and IO as islands; an Arctic margin at the top right and one blank beside UM in the Pacific.
- Oceania keeps Micronesia (MP, PW, GU, FM, UM, MH) above Melanesia (PG, SB, VU, NC, FJ) above Polynesia (TK, TV, WF, AS, TO, WS, PF, NU, CK, PN), and NZ south of AU.
- The eight CLDR additions are placed by geography, none in an overflow strip: AC and TA in the South Atlantic column, CP directly north of MX at the Pacific edge, CQ in the GG/JE/CQ/IM block on Europe's Atlantic edge, DG in the Indian Ocean, EA east of MA and west of MT, IC west of MA, XK between MT and AL with ME above it in the Balkans.
- The Channel Islands and the Isle of Man (GG, JE, CQ, IM) form a 2 × 2 block on Europe's Atlantic edge, separated from the Caribbean by the gap; on 19 × 14 they touched the Caribbean.

Findings recorded as accepted weaknesses (no pins applied; a pin would need a DECISIONS entry with before/after scores):

- NO sits between DK and LT in the second row rather than west of SE; SE/FI/LV/EE run along the top row. Norway–Sweden are still orthogonal neighbours.
- BH sits at (13,7) directly under QA and east of DJ, at the join between the Horn of Africa and the Gulf, with blanks to its east.
- HM and CC sit on the bottom row beside NZ; geographically they are far south-west of Australia, so this is defensible but reads oddly.
- Europe is dense: with 50 identifiers in roughly 8 × 7 cells there is no Mediterranean gap, and MT/XK/AL/CY form the southern rim.
- Caribbean islands and Central America share the left columns without a Gulf of Mexico gap.

Alternatives considered and rejected in review: 24 × 12 opens more Atlantic space but scores worse, has a 2:1 aspect and fragments its whitespace; 19 × 14 (the brief's hypothesis) has no Atlantic gap at all; the 20 × 14 seed-6 board (3.512) has a Siberian gap between KG and KR but no North Atlantic gap and puts AC beside Suriname.

## 7. Meaning of "optimal"

The committed board is **the best layout found under the documented
objective, weights, inputs, seeds and search budget**. It is not a proven
global optimum: the problem is a quadratic-assignment-type problem with
n = 257, the objective is a normative construction, and different seeds
reach different local optima (the spread is reported above). Anyone can
score a competing board with `scripts/score_layout.py` and propose it.

## 8. Reproducing the result

```bash
# inputs (both committed; the Natural Earth file is downloaded once into .cache/ when absent)
uv run scripts/extract_cldr_regions.py --cldr-dir /path/to/cldr-common-48.2   # optional; committed
uv run scripts/build_geographic_inputs.py                                   # optional; committed

# grid comparison: 7 grids × 4 seeds × 3 M iterations. One process per grid (≈ 25–35 min wall clock on
# 8 cores; each seed takes 6–8 min when 7 processes share the machine), then merge the per-grid reports.
for g in 17x16 18x15 19x14 20x13 20x14 22x12 24x12; do
  uv run scripts/compare_grids.py --grids $g --seeds 1 2 3 4 --iterations 3000000 \
      --out-dir reports/parts --layout-dir layouts/candidates --tag="-$g" &
done; wait
uv run scripts/compare_grids.py --merge reports/parts/grid-comparison-*.json --out-dir reports
# (a single sequential invocation without --tag/--merge gives the same result in ~3 h)

# selected board: 8 seeds × 5 M iterations, one process per seed (≈ 10 min in parallel), best chain promoted
for s in 1 2 3 4 5 6 7 8; do
  uv run scripts/optimize_layout.py --grid 20x14 --seeds $s --iterations 5000000 --out runs/s$s.json --quiet &
done; wait
uv run scripts/promote_layout.py runs/s1.json --runs runs/s2.json runs/s3.json runs/s4.json runs/s5.json runs/s6.json runs/s7.json runs/s8.json
# seed 1 alone reproduces the committed cells: optimize_layout.py --grid 20x14 --seeds 1 --iterations 5000000

# sensitivity
uv run scripts/sensitivity.py layouts/cldr-48.2-regular-2alpha-20x14.json --iterations 1500000   # ≈ 25 min

# fast verification
uv run scripts/validate_board.py && uv run pytest -q
```
