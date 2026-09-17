# Changelog

## 0.1.0 — initial release (2026-09-17)

- Mother set: Unicode CLDR 48.2 `common/validity/region.xml`,
  `idStatus="regular"`, two-letter identifiers: 257 identifiers
  (249 ISO 3166-1 alpha-2 + AC, CP, CQ, DG, EA, IC, TA, XK).
- Board: 20 × 14 square cells, 23 structural blank cells,
  selected after optimizing 17×16, 18×15, 19×14, 20×13, 20×14, 22×12 and
  24×12 under identical budgets (see OPTIMIZATION.md).
- Inputs: Wikidata representative points (CC0), Natural Earth 5.1.2 land
  adjacency (public domain), CLDR territoryContainment subregions.
- Artifacts: `layouts/*.json` (source of truth), `board.csv` (8bit-style
  matrix), `metadata.json`, `docs/board.svg`.
- Predecessor: `tabularmaps/8bit` (250 identifiers, 16×16) is kept as a
  comparison baseline and is not modified.
