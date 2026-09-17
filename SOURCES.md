# Sources

Every input to the board is pinned, checksummed, and reproducible. Facts
about the inputs live here; the rationale for choosing them lives in
[DECISIONS.md](DECISIONS.md).

## 1. Mother set: Unicode CLDR 48.2

| item | value |
|---|---|
| organization | Unicode, Inc. |
| dataset | Unicode Common Locale Data Repository (CLDR), release 48.2 |
| release date | 2026-03-16 (tag `release-48-2`, commit `11299982335beb974c1c63c45265184e759c0f41`) |
| immutable archive | <https://unicode.org/Public/cldr/48.2/cldr-common-48.2.zip> |
| archive sha512 | `de8660f5371e0fcfd03a42e3b4fc4c686ec6cd602b402f1e3d227844005a54eb7952873894443523837d5828c42874a1a267a19f91ded207a2d166144791fa62` (matches the published `hashes/SHASUM512.txt`) |
| file used | `common/validity/region.xml` (1905 bytes, sha256 `e751e0eedd46b52c38f3cdb72b0fab61ac8b48e052e8b28ba74b6ac26c4c8cb1`; identical in the archive and at the git tag) |
| committed copy | [data/cldr/48.2/region.xml](data/cldr/48.2/region.xml) |
| license | Unicode License v3 (SPDX `Unicode-3.0`), copy at [data/cldr/48.2/LICENSE](data/cldr/48.2/LICENSE) |
| extraction | `<id type="region" idStatus="regular">`, compact ranges expanded, `^[A-Z]{2}$` kept: **257 identifiers** ([data/regions.json](data/regions.json)) |
| also used | `common/main/en.xml` (English display names, informational) and `common/supplemental/supplementalData.xml` (`territoryContainment`, UN M49 based subregions used for the *region* score component and for preview colours). Checksums are recorded in `data/regions.json`. |
| extraction date | 2026-09-17 |
| script | [scripts/extract_cldr_regions.py](scripts/extract_cldr_regions.py) |

Status counts in the pinned file: regular 257, special 2, macroregion 35,
deprecated 12, reserved 13, private_use 23, unknown 1. Only `regular` is
used.

### Non-normative cross-check with ISO 3166-1

The 257 regular identifiers are the 249 ISO 3166-1 alpha-2 codes plus eight
CLDR-specific identifiers: `AC`, `CP`, `CQ`, `DG`, `EA`, `IC`, `TA`, `XK`.
The check in `tests/test_mother_set.py` uses the predecessor board (249 ISO
codes + `XK`) as the reference; it was also confirmed against `pycountry`
26.2.16 (Debian `iso-codes`) on 2026-09-17. ISO is **not** the normative
source of this project.

## 2. Representative points: Wikidata

| item | value |
|---|---|
| organization | Wikimedia Foundation / Wikidata community |
| dataset | Wikidata, properties P297 (ISO 3166-1 alpha-2 code) and P625 (coordinate location) |
| snapshot | SPARQL result retrieved 2026-09-17, committed as [data/geo/raw/wikidata_p297_p625_2026-09-17.csv](data/geo/raw/wikidata_p297_p625_2026-09-17.csv); query text in [data/geo/raw/wikidata_query.sparql](data/geo/raw/wikidata_query.sparql) |
| license | CC0 1.0 (Wikidata data) |
| rule | the P625 value of the item carrying `P297 = <id>`; when several items carry the same code (AQ, CY, NL in this snapshot) the item with the lowest Q-number is used |
| meaning of the point | whatever the Wikidata item records as its coordinate location: usually a point near the geographic centre of the main territory, sometimes the capital (e.g. `KI` = Tarawa, `NO` = near Oslo). It is **not** a centroid computed by this project. |
| coverage gaps | `EA` (Ceuta & Melilla) and `IC` (Canary Islands) have no ISO code, so no P297 entry; see supplements |
| supplements | [data/geo/points_supplement.csv](data/geo/points_supplement.csv): `EA` = Ceuta (Q5823), `IC` = Canary Islands (Q5813), both with notes |
| output | [data/geo/points.csv](data/geo/points.csv), one row per identifier with `source`, `source_id`, `snapshot` |

Sanity check against Natural Earth largest-polygon centroids: 18 identifiers
differ by more than 300 km, the largest being `KI` (Tarawa vs Kiritimati,
3289 km), `MY` (peninsular vs Borneo), `AQ` (pole vs land centroid), `TF`.
All were reviewed and kept; the differences are within one or two cells.

## 3. Land adjacency: Natural Earth

| item | value |
|---|---|
| organization | Natural Earth (naturalearthdata.com), distributed via `nvkelso/natural-earth-vector` |
| dataset | `ne_10m_admin_0_map_units.geojson`, version 5.1.2 |
| URL | <https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/ne_10m_admin_0_map_units.geojson> |
| sha256 | `57da82be755f4afccd8f3b14251bb2752f5df1395f47d2d86f817470c4a48862` (committed in `data/geo/raw/`; the 13.5 MB file itself is downloaded on demand into `.cache/`) |
| license | public domain |
| rule | two map units are land neighbours when they share at least two identical vertices (coordinates rounded to 1e-6°) and map to different identifiers. Unit → identifier mapping: `ISO_A2_EH`; else Natural Earth's ISO point-of-view field `ADM0_ISO` (alpha-3, e.g. Somaliland → `SO`, N. Cyprus → `CY`, UNDOF zone → `SY`); else `ADM0_A3` (Korean DMZ halves → `KP`/`KR`). |
| dropped units | Dhekelia, Akrotiri, USNB Guantanamo Bay, Siachen Glacier, Southern Patagonian Ice Field, Bir Tawil, Spratly Is., Bajo Nuevo Bank, Serranilla Bank, Scarborough Reef (no identifier under the rule; listed in [data/geo/ne_units.json](data/geo/ne_units.json)) |
| rejected by rule | pairs sharing exactly one vertex (`BW`–`ZM`, `NA`–`ZW`, the Kazungula quadripoint) |
| supplements | [data/geo/adjacency_supplement.csv](data/geo/adjacency_supplement.csv): `CN`–`MO` (Natural Earth draws Macao without shared vertices) and `EA`–`MA` (EA is not a map unit) |
| output | [data/geo/adjacency.csv](data/geo/adjacency.csv): 324 undirected pairs |
| maritime adjacency | not modelled. Sea neighbours are handled by the neighbourhood (k-nearest) and false-adjacency components, not by the adjacency component. |
| disputed borders | Natural Earth's de-facto policy determines which polygons exist and where they touch; the ISO point-of-view fields determine which identifier a contested unit counts for. This project adds no boundary judgement of its own and the adjacency list implies no position on sovereignty. |

## 4. Regional classification: CLDR territoryContainment

Subregion codes (`021`, `029`, `154`, …) and continent codes come from the
pinned CLDR `supplementalData.xml`, which follows UN M49. Groupings (`EU`,
`EZ`, `UN`, `003`, `202`, `419`) and deprecated groups are ignored. `QO`
(Outlying Oceania: `AC`, `AQ`, `CP`, `DG`, `TA`) is kept as a label but its
members are excluded from the regional-continuity score because they are
not a geographic region. The classification is never the mother-set
authority; it is used only as a scoring input and for preview colours.

## 5. Predecessor board: tabularmaps/8bit

| item | value |
|---|---|
| repository | <https://github.com/tabularmaps/8bit> (commit `68519fe`, 2019) |
| file | `board.csv`, 16 × 16, 250 identifiers (249 ISO 3166-1 alpha-2 + `XK`), 6 blank cells |
| license | The Unlicense (public domain); copy at [data/legacy/8bit-LICENSE](data/legacy/8bit-LICENSE) |
| committed copy | [data/legacy/8bit-board.csv](data/legacy/8bit-board.csv) |
| use | legacy-continuity metrics, the "naive extension" baseline, and the `board.csv` format convention |

## 6. Tooling

Python ≥ 3.11 with `numpy` and `scipy` (`linear_sum_assignment`); `pytest`
for tests; `uv` for a locked environment (`uv.lock`). No network access is
needed to run the tests or to validate the committed board.
