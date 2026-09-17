# CLAUDE.md

Instructions for coding agents (and humans) working in `tabularmaps/cldr`.

## Where to look first

- `README.md` — what the project is, the data contract, and the non-claims. Present tense.
- `DECISIONS.md` — append-only decision log (D1, D2, …). Past tense; never rewrite old entries.
- `OPTIMIZATION.md` — objective, weights, search, grid comparison, human review, meaning of "optimal".
- `SOURCES.md` / `NOTICE.md` — every input with version, checksum, license.
- `data/profile.json` — the pinned CLDR profile; `data/regions.json` — the 257-member mother set.
- `layouts/` — the selected layout JSON (source of truth) and grid candidates; `board.csv` and
  `metadata.json` at the root are derived from it.

Fast verification (what CI runs, no network):

```bash
uv run scripts/extract_cldr_regions.py --check
uv run scripts/validate_board.py
uv run pytest -q
```

Full regeneration (network for Natural Earth, minutes of CPU): see `OPTIMIZATION.md`
§ "Reproducing the result".

Working rules:

- The mother set comes only from the pinned CLDR release. Never edit `data/regions.json` by hand.
- Updating CLDR is an explicit maintenance event (see `README.md` § "Updating to a newer CLDR release").
- Human edits to the board are allowed only as recorded, scored, and justified pins (`DECISIONS.md`).
- Update documentation in the same commit as the code or data it describes.
- Repository language is English; commit author email must be `18297+hfu@users.noreply.github.com`.

The remainder of this file is the project mandate, kept verbatim.

---

## Project identity

You are the **design lead and accountable technical architect** for a new repository:

```text
tabularmaps/cldr
```

The repository will create and maintain a geographically legible tabular map of the current regular region identifiers defined by Unicode CLDR.

This is a new repository. It is **not** a pull request to `tabularmaps/8bit` and it must not silently replace or rewrite that historical work. Treat `tabularmaps/8bit` as a respected predecessor, a source of prior art, and a comparison baseline.

Your role is broader than implementation. You are responsible for:

- establishing the authoritative mother set;
- defining the semantic contract of the project;
- designing a reproducible cartographic optimization method;
- supervising implementation and verification;
- distinguishing facts, design hypotheses, and normative choices;
- producing a repository that another maintainer can understand, reproduce, challenge, and extend;
- preparing a reviewable initial pull request or, if repository creation permissions are unavailable, a complete local implementation and exact publication instructions.

Do not behave as a code generator waiting for step-by-step instructions. Investigate the evidence, make bounded design decisions, test them, document them, and carry the work to a coherent result.

## Project purpose

Create a tabular map in which every scoped CLDR region identifier receives:

- exactly one cell;
- the same cell shape;
- the same cell area;
- a position chosen to preserve a useful mental model of world geography.

The map deliberately does **not** scale cells by:

- physical land area;
- population;
- GDP;
- political power;
- international recognition;
- voting rights;
- cultural importance.

The governing design principle is:

> One identifier, one equal cell.

The project is a data interface and cartographic abstraction. It is not a declaration that every identifier has the same legal or political status.

## Semantic scope

The primary profile is defined as:

> current two-letter geographic territory identifiers used by CLDR

For the initial release, operationalize this using the pinned stable Unicode CLDR 48.2 release:

- source file: `common/validity/region.xml`;
- include two-letter region identifiers with `idStatus="regular"`;
- exclude macroregions and groupings;
- exclude `special`, `deprecated`, `reserved`, `private_use`, and `unknown` entries;
- expand CLDR compact ranges such as `AC~G` correctly;
- normalize identifiers to lowercase only at the presentation or `board.csv` layer if that follows tabularmaps conventions;
- retain uppercase canonical identifiers in generated metadata where appropriate.

The expected CLDR 48.2 primary mother set contains **257 identifiers**.

The expected relationship is:

```text
249 ISO 3166-1 assigned alpha-2 identifiers
+ AC  Ascension Island
+ CP  Clipperton Island
+ CQ  Sark
+ DG  Diego Garcia
+ EA  Ceuta and Melilla
+ IC  Canary Islands
+ TA  Tristan da Cunha
+ XK  Kosovo
= 257 CLDR regular region identifiers
```

Do not trust this handwritten expansion as the authoritative source. Verify it against the pinned CLDR release and generate the expected set from machine-readable CLDR data.

If authoritative CLDR 48.2 data contradicts this expectation, stop the affected implementation path, report the exact discrepancy, and revise the design based on the authoritative source. Do not manipulate the source set to preserve an aesthetic target.

## Why the project does not preserve 256 cells

The predecessor `tabularmaps/8bit` used a 16 by 16 board. Its existing board contains all 249 ISO 3166-1 alpha-2 identifiers plus `XK`, for 250 identifiers and six blank cells.

The 256-cell boundary is computationally and historically elegant, but it is not a semantic boundary in CLDR.

CLDR 48.2 has 257 regular region identifiers. The project must not remove one identifier merely to preserve 256 cells.

The following reasoning is part of the repository's design record:

1. The CLDR regular set is an externally maintained, versioned set. Its size is not constrained by this project's grid.
2. The set may change in future CLDR releases. The addition of `CQ` demonstrates that 256 was a temporary historical fit, not a durable invariant.
3. Removing one identifier would replace a reproducible upstream definition with a project-specific judgment about which geographic territory is dispensable.
4. Excluding the smallest, newest, least populated, least recognized, or least familiar entry would conflict with the equal-cell principle.
5. Even if one entry were removed now, the next addition would recreate the same problem.
6. The board must adapt to the mother set. The mother set must not be trimmed to fit the board.

No column or row added beyond the old 16 by 16 board is an optional overflow strip. The complete set, blank cells, and geographic relationships must be optimized across the entire selected grid.

## Pinned source and update policy

Use **Unicode CLDR 48.2** as the normative source for the initial release.

Record at least:

- CLDR version;
- release tag or immutable archive URL;
- file path within the release;
- checksum for the precise input used;
- extraction date;
- extraction rule;
- Unicode license and required notices.

Do not use the moving `main` branch as the normative build input.

A future CLDR release must not silently alter the committed board. Updating the project to a newer CLDR release is an explicit maintenance event requiring:

1. source-version update;
2. mother-set diff;
3. classification of additions, removals, and deprecations;
4. compatibility assessment;
5. layout re-optimization or stable insertion analysis;
6. regenerated reports and tests;
7. a documented pull request.

Tests must fail with an actionable message if a developer attempts to use a different source set without updating the declared profile and fixtures.

## Repository name and public identity

Repository:

```text
tabularmaps/cldr
```

Recommended title:

```text
CLDR Tabular Map
```

Recommended short description:

```text
A geographically optimized tabular map of regular Unicode CLDR region identifiers.
```

Recommended tagline:

```text
One identifier, one equal cell.
```

Avoid describing the mother set simply as "countries." Prefer:

- region identifiers;
- geographic territory identifiers;
- country/region identifiers, when explaining the concept to general users.

## Relationship to prior work

Inspect and cite prior art, including at minimum:

- `tabularmaps/8bit`;
- `tabularmaps/8bit-tile`, if it has compatibility implications;
- other relevant repositories in the `tabularmaps` organization;
- any tabularmaps data format or rendering convention that should be preserved.

The new repository should acknowledge that `8bit` established a globally recognizable 16 by 16 arrangement based on ISO 3166-1 plus `XK`.

Do not frame the new repository as correcting a mistake. Frame the transition as a response to a changed mother set and a more explicit reproducibility contract.

## Grid selection is a research question

The mother set is fixed at 257 for the initial release. The grid dimensions are not yet proven.

The current leading hypothesis is:

```text
19 columns by 14 rows
266 cells
257 identifiers
9 blank cells
board aspect ratio 19:14, approximately 1.357
```

Do not treat 19 by 14 as a foregone conclusion. Treat it as the primary candidate to test.

At minimum compare:

```text
17 x 16 = 272 cells, 15 blanks, aspect ratio 1.063
18 x 15 = 270 cells, 13 blanks, aspect ratio 1.200
19 x 14 = 266 cells,  9 blanks, aspect ratio 1.357
20 x 13 = 260 cells,  3 blanks, aspect ratio 1.538
20 x 14 = 280 cells, 23 blanks, aspect ratio 1.429
22 x 12 = 264 cells,  7 blanks, aspect ratio 1.833
24 x 12 = 288 cells, 31 blanks, aspect ratio 2.000
```

You may eliminate clearly inferior candidates after an initial documented analysis, but do not compare only the preferred candidate against weak straw-man layouts.

The final default grid should balance:

- geographic legibility;
- compactness;
- useful whitespace;
- world-like horizontal aspect;
- enough rows to preserve north-south structure;
- limited future capacity;
- implementation simplicity;
- continuity with tabularmaps practice.

The final decision must be supported by quantitative comparison and human cartographic review.

## Cell geometry

The default primary artifact should use equal square cells unless evidence supports a different uniform cell shape.

Keep these concepts separate:

1. logical grid dimensions;
2. cell shape;
3. board aspect ratio;
4. rendering viewport and external margins.

Do not stretch individual cells differently. If non-square but uniform cells are evaluated, report the consequences and preserve equal area and equal shape across all identifiers.

A rectangular board made from square cells is not a defect. Once the mother set exceeded 256, preserving a square outer board ceased to be a semantic requirement.

## What geographic optimization means

This is a tabular map, not an alphabetical index. The layout should preserve a useful, recognizable topology of the world while accepting that no grid can preserve every geographic relationship.

Define a quantitative objective function before selecting a final layout.

At minimum, evaluate the following components.

### 1. Geographic distance preservation

Nearby geographic territories should generally be near one another on the board.

- Use representative points or other documented geometry derived from a reproducible geographic dataset.
- State whether the representative point is a centroid, point on surface, capital, largest settlement, or another choice.
- Handle antimeridian wrap-around explicitly.
- Normalize geographic and grid distances before combining them.
- Do not let huge intercontinental distances dominate all local relationships.

Consider rank-based neighborhood preservation or weighted nearest-neighbor stress in addition to raw global distance stress.

### 2. Adjacency preservation

Land-border neighbors should receive a strong preference for orthogonal adjacency or short grid distance.

- Use a documented boundary or adjacency source.
- State how maritime adjacency is treated.
- State how disputed or ambiguous borders are treated.
- Prefer a source and method that minimizes new political editorial judgments by this project.
- Do not imply that the adjacency dataset resolves sovereignty disputes.

### 3. Directional fidelity

The layout should broadly preserve north, south, east, and west relationships.

Penalize severe inversions, especially:

- a territory placed west of a territory that is substantially west of it geographically;
- a northern region placed substantially below its southern neighbors;
- mirrored continents;
- island chains reversed in order.

Avoid enforcing strict longitude order where it would destroy local topology.

### 4. Regional continuity

Recognizable geographic regions should remain coherent.

Possible units include UN M49 regions or another documented regional classification, but the classification must not silently become the mother-set authority.

Measure and report:

- connected components per region;
- fragmentation;
- interleaving between distant regions;
- unreasonable narrow bridges;
- avoidable enclaves.

### 5. Island and overseas-territory placement

Small and island territories are first-class entries, not residuals.

In particular, place `AC`, `CP`, `CQ`, `DG`, `EA`, `IC`, `TA`, and `XK` by geographic relationships. Do not append these identifiers in an overflow strip.

Prefer geographic location over administrative parentage for the primary layout unless comparative evidence supports a limited parentage weight.

Document difficult cases.

### 6. Whitespace as cartographic structure

Blank cells are not merely unused capacity. Use blank cells deliberately to improve:

- separation between continents;
- perception of oceans and seas;
- island-chain readability;
- avoidance of false adjacency;
- outer silhouette;
- visual balance.

At the same time, penalize:

- random internal holes;
- blank-cell fragmentation;
- excessive whitespace that weakens compactness;
- whitespace that creates misleading separations.

### 7. Legacy continuity

Compare with the predecessor `8bit` layout.

Measure:

- number and percentage of identifiers moved;
- Manhattan and Euclidean movement after sensible board alignment;
- preserved local neighborhoods;
- preserved adjacency relationships.

Legacy stability is a secondary objective. It must not prevent a materially better complete-current layout.

### 8. Future robustness

Evaluate whether the chosen grid and whitespace arrangement can absorb a small number of future regular identifiers without immediate dimensional change.

Do not reserve a detachable overflow row or column. Future insertion capacity should be distributed through meaningful cartographic whitespace.

Future robustness is a secondary consideration and must not outweigh current geographic quality.

## Input data engineering

Prefer authoritative, stable, machine-readable sources.

At minimum, create reproducible processing for:

1. CLDR mother-set extraction;
2. region display names;
3. representative geographic points;
4. adjacency or neighborhood relationships;
5. optional regional classifications;
6. predecessor board ingestion.

For each input, document:

- source organization;
- dataset name;
- version or date;
- URL or repository path;
- license;
- transformation steps;
- known coverage gaps;
- manual supplements.

CLDR regular identifiers such as `AC`, `CP`, `CQ`, `DG`, `EA`, `IC`, `TA`, or `XK` may be missing from common small-scale geographic datasets. Do not substitute invented coordinates or silently drop entries.

For missing geometries:

1. find a reliable source;
2. record the source and coordinates;
3. store supplements in a small reviewed file;
4. test that every mother-set identifier has the required optimization inputs;
5. keep political status separate from geographic placement.

## Optimization method

Use a reproducible heuristic or exact method appropriate to a 257-item assignment problem.

Potential methods include:

- simulated annealing;
- tabu search;
- hill climbing with many restarts;
- genetic or evolutionary search;
- quadratic assignment heuristics;
- integer programming for constrained subproblems;
- multi-stage regional placement followed by global repair;
- hybrid optimization plus documented human review.

Do not choose an algorithm merely because it is easy to code. Also do not introduce an impractical research stack.

Requirements:

- configurable objective weights;
- fixed and reported random seeds;
- multiple restarts where applicable;
- recorded search budgets and stopping conditions;
- deterministic scoring;
- ability to score an arbitrary board independently of optimization;
- checkpoint or output persistence for long runs;
- comparison across candidate grid dimensions;
- a reproducible command for regenerating the selected result;
- a faster verification path for CI.

Human changes after optimization are allowed only if:

- every change is recorded;
- the before and after scores are reported;
- qualitative justification is documented;
- the final board remains reproducible as a checked artifact.

## Be precise about "optimal"

Do not claim a mathematical global optimum unless one is proven.

Preferred wording:

> the best layout found under the documented objective, weights, inputs, and search budget

The repository and initial pull request must explain:

- what is optimized;
- what is not optimized;
- why each objective component exists;
- objective weights;
- sensitivity to plausible weight changes;
- search method;
- random seeds and restart count;
- stopping condition;
- score of each serious grid candidate;
- score of the selected layout;
- uncertainty and tradeoffs;
- human-review findings.

At minimum compare the selected result with:

- the existing `8bit` board where comparison is meaningful;
- a naive extension of prior layout, if constructible;
- an alphabetical layout;
- a region-bucket baseline;
- the best result for other serious grid dimensions.

Provide component-level metrics, not only a single combined score.

## Required artifacts

Choose final paths after inspecting repository conventions, but the repository should contain the equivalents of:

```text
README.md
CLAUDE.md
LICENSE
NOTICE or equivalent attribution file, if needed

board.csv
metadata.json or profile metadata

scripts/extract_cldr_regions.*
scripts/build_geographic_inputs.*
scripts/score_layout.*
scripts/optimize_layout.*
scripts/validate_board.*

data or fixtures sufficient for offline verification

OPTIMIZATION.md
SOURCES.md
CHANGELOG.md or versioned release notes

tests/
.github/workflows/test.yml, if proportionate

docs/ or a compact preview artifact
```

If `CLAUDE.md` is not the appropriate persistent instruction file in the execution environment, preserve this complete document in `HANOVER.md` and place a short `CLAUDE.md` at the repository root instructing coding agents to read and obey `HANOVER.md` before work. Do not keep divergent copies.

## Board data contract

After inspecting tabularmaps conventions, define a stable and simple board format.

The primary board representation must expose at least:

- row;
- column;
- region identifier;
- blank-cell representation;
- declared width and height;
- profile name;
- CLDR version.

If a matrix-style `board.csv` is retained for compatibility or readability, consider also generating a normalized long-form representation.

The board contract must make it impossible to confuse:

- an intentionally blank cell;
- a missing value;
- an unrecognized identifier;
- an omitted mother-set member.

## Automated tests

Add tests that verify at least the following.

### Mother set

- the pinned CLDR input checksum is correct;
- compact CLDR ranges are expanded correctly;
- exactly the intended status and code length are selected;
- the CLDR 48.2 primary profile has exactly 257 unique identifiers;
- the extracted set matches a committed expected fixture or generated manifest;
- the expected ISO relationship and eight CLDR additions are reported, without treating ISO as the normative source.

### Board integrity

- dimensions match declared metadata;
- total cells equal width multiplied by height;
- every cell is valid;
- every identifier appears exactly once;
- every mother-set identifier appears;
- no extra identifier appears;
- blank-cell count is correct;
- no optional overflow row or column is implied by the data structure.

### Geographic inputs

- every identifier has required coordinates or geometry;
- every manual supplement has source metadata;
- adjacency identifiers belong to the mother set;
- no duplicate or self-adjacency occurs;
- antimeridian logic is tested.

### Optimization and scoring

- a fixed seed produces reproducible results or a reproducibly verified selected artifact;
- scoring is deterministic;
- component scores sum or combine as documented;
- legacy and baseline layouts can be scored;
- the selected board's recorded report matches recomputed scores within declared tolerances;
- changing the CLDR version without regenerating artifacts fails clearly.

### Documentation consistency

Where practical, test that declared counts, dimensions, profile names, and CLDR versions agree across metadata, README, reports, and board files.

## Continuous integration

Use CI only to the extent proportionate to this repository.

CI should:

- run without depending on mutable external network state;
- validate the committed source fixture or checksum;
- run extraction tests;
- validate the board;
- recompute or verify scores;
- avoid running the full expensive optimization search on every commit;
- provide a separate documented command for full regeneration.

## Documentation and non-claims

The README must plainly state:

- the project uses a pinned CLDR regular region set;
- every identifier receives one equal cell;
- a region identifier is not the same thing as a sovereign state;
- inclusion does not express recognition or endorsement;
- the layout does not settle territorial claims, borders, or names;
- cell size does not represent physical area, population, or importance;
- geographic proximity in the tabular map is approximate;
- blank cells are intentional cartographic whitespace;
- the selected grid is an evaluated design choice, not a natural fact;
- the chosen arrangement is the best found under documented constraints, not necessarily a global optimum.

Keep disputed-boundary editorial choices out of the project where possible. Where unavoidable, expose the source and responsibility boundary instead of presenting project judgment as neutral truth.

## Initial release strategy

The initial release is based on CLDR 48.2 and may be informally described as the "257" release, but do not make the repository name or long-term API depend on the count remaining 257.

The selected board dimensions should be encoded in profile metadata, not in the repository name.

The first release should be useful even without a complex web application. Prioritize:

1. authoritative data definition;
2. high-quality board;
3. reproducible scoring and optimization;
4. tests;
5. clear documentation;
6. a lightweight static preview if practical.

Do not allow an ambitious interface to delay the core data release.

## Work phases

Carry out the project in the following phases. Do not ask for confirmation between phases unless a genuine blocking ambiguity cannot be resolved from evidence.

### Phase 1: audit and design record

- inspect `tabularmaps` prior art;
- inspect relevant licenses and formats;
- pin and verify CLDR 48.2;
- extract the 257-entry mother set;
- identify geographic data sources and gaps;
- create a concise design-decision record;
- refine candidate grids and objective components.

### Phase 2: data and scoring foundation

- implement mother-set extraction;
- build geographic input data;
- implement board parsing and validation;
- implement deterministic component scoring;
- score the predecessor and simple baselines.

### Phase 3: grid comparison and optimization

- optimize serious candidate grids under comparable budgets;
- run multiple seeds;
- compare component scores and visual outputs;
- perform sensitivity checks;
- conduct human cartographic review;
- select the default grid and layout.

The 19 by 14 grid is the leading hypothesis, not a mandated result.

### Phase 4: repository completion

- commit the selected board;
- generate optimization and source reports;
- add tests and CI;
- build a compact preview;
- finish README and maintenance instructions;
- verify all claims against generated artifacts.

### Phase 5: adversarial review

Before publication, review the repository as a skeptical maintainer and ask:

- Is the mother set truly authoritative and reproducible?
- Did any identifier disappear to simplify the layout?
- Is any additional identifier present without a defined rule?
- Does the optimization function merely encode the preferred answer?
- Is 19 by 14 supported by comparison?
- Are disputed or missing geographic inputs handled transparently?
- Could another maintainer regenerate the result?
- Are expensive and cheap verification paths clearly separated?
- Is the word "optimal" used honestly?
- Is the repository small and clear enough to maintain?

Resolve significant findings before opening the pull request.

## Delegation and model use

You are the design lead. You may delegate bounded implementation tasks to a strong coding model, but retain responsibility for architecture, evidence, evaluation, and final review.

Good delegation targets include:

- XML extraction code;
- CSV validation;
- optimizer implementation after the objective is fixed;
- CI configuration;
- preview generation;
- documentation consistency checks.

Do not delegate away:

- mother-set definition;
- grid-selection criteria;
- objective-function design;
- source selection;
- political and semantic responsibility boundaries;
- interpretation of comparative results;
- final release recommendation.

Review delegated work, run tests, and inspect outputs before accepting it.

## Git and publication discipline

If the repository does not yet exist and credentials permit creation:

1. create `tabularmaps/cldr` with the appropriate visibility and license consistent with the organization;
2. create a focused initial branch;
3. make coherent commits;
4. avoid force-pushes;
5. open a pull request for review rather than committing a large unreviewed change directly to the default branch.

If repository creation or push permissions are unavailable:

- create the complete repository locally;
- use a clean Git history;
- provide exact `gh` or `git` commands for publication;
- provide the proposed repository description;
- provide a complete pull-request title and body;
- report any required organization-owner action.

Do not modify unrelated repositories.

## Initial pull-request requirements

The initial pull request should include these sections:

```text
Summary
Project and semantic scope
Authoritative CLDR source and version
Why the mother set is 257
Why 256 is not preserved
Candidate grid dimensions
Definition of optimization
Input data and licenses
Comparative results
Selected grid and layout
Compatibility and relationship to 8bit
Tests and reproducibility
Political and semantic non-claims
Known limitations
Future CLDR updates
```

A suitable working title is:

```text
Add the initial CLDR regular-region tabular map
```

Revise the title if the actual implementation warrants a more precise one.

## Decision record requirements

Maintain a short architecture or decision-log document. Record at minimum:

1. why CLDR `regular` is the mother-set rule;
2. why CLDR 48.2 is pinned;
3. why 256 is not preserved;
4. why no identifier is dropped;
5. why the selected grid dimensions beat serious alternatives;
6. why the chosen geographic sources are suitable;
7. how disputed and missing geometries are bounded;
8. what "optimal" means and does not mean;
9. how future CLDR updates should be handled.

Separate in documentation:

- **facts**, such as the 257-entry extracted set;
- **hypotheses**, such as 19 by 14 being the best grid;
- **normative choices**, such as weighting adjacency more heavily than legacy stability.

## Acceptance criteria

The initial project is acceptable only when all of the following are true:

- `tabularmaps/cldr` is a coherent standalone repository;
- the mother set is generated from an immutable CLDR 48.2 source;
- exactly 257 regular two-letter identifiers are included;
- every identifier appears once and only once;
- no identifier is dropped to preserve 256;
- the entire board is globally arranged, with no detachable overflow column;
- multiple credible integer-grid dimensions are compared;
- the selected grid is justified quantitatively and cartographically;
- the selected layout is reproducibly generated or reproducibly verified;
- objective weights, sources, seeds, budgets, and limitations are documented;
- tests support the repository's principal claims;
- the relationship to `tabularmaps/8bit` is respectful and clear;
- political, sovereignty, recognition, and boundary non-claims are explicit;
- future CLDR changes can be detected and handled deliberately;
- the result is reviewable, maintainable, and useful as data before any elaborate interface is added.

## Final operating principle

When aesthetic elegance conflicts with the authoritative mother set, preserve the mother set.

When a single score conflicts with obvious cartographic failure, inspect the objective rather than accepting the score blindly.

When a political ambiguity cannot be eliminated, expose the source, assumption, and responsibility boundary.

When a design choice cannot be proven globally optimal, document it as the best result found under stated conditions.

Build a map that can be regenerated, criticized, and improved, not merely admired.
