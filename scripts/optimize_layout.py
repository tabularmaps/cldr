#!/usr/bin/env python3
"""Optimize a layout for one grid with simulated annealing.

Runs one annealing chain per seed from a geographic starting layout, keeps
the best chain by combined score, re-scores it from scratch, and writes a
layout JSON with full provenance (seed, budget, weights, component scores).
Optional constraints:

- ``--pins JSON``       ``{"JP": [18, 3], ...}`` fixed cells (documented in
                        DECISIONS.md with a reason for every pin)
- ``--territories TXT`` a design/territories-WxH.txt map: each identifier may
                        only occupy cells carrying its subregion's letter;
                        '.' cells stay blank (see design/README.md)

Usage:
  uv run scripts/optimize_layout.py --grid 19x14 --seeds 1 2 3 4 --iterations 400000 \
      --out layouts/candidates/19x14.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cldrmap import DATA  # noqa: E402
from cldrmap.baselines import projection, rank_projection  # noqa: E402
from cldrmap.board import Layout  # noqa: E402
from cldrmap.geo import load_geo  # noqa: E402
from cldrmap.mother_set import Profile, load_ids  # noqa: E402
from cldrmap.optimize import Annealer  # noqa: E402
from cldrmap.scoring import DEFAULT_WEIGHTS, PARAMS, Grid, build_problem, score  # noqa: E402


def parse_grid(s: str) -> Grid:
    w, h = s.lower().split("x")
    return Grid(int(w), int(h))


def load_territories(path: Path, grid: Grid, geo) -> tuple[dict[int, list[int]], set[int]]:
    """Parse a territory map. Header lines ``# X=021,013`` assign subregion
    codes to a letter; '.' marks fixed blanks; '*' cells accept anything."""
    letters: dict[str, set[str]] = {}
    rows = []
    for line in path.read_text("utf-8").splitlines():
        if line.startswith("#"):
            body = line[1:].strip()
            if "=" in body and len(body.split("=")[0].strip()) == 1:
                letter, codes = body.split("=", 1)
                letters[letter.strip()] = {c.strip() for c in codes.split(",") if c.strip()}
            continue
        if line.strip():
            rows.append(line.strip())
    if len(rows) != grid.height or any(len(r) != grid.width for r in rows):
        raise SystemExit(f"territory map must be {grid.width}x{grid.height}; got {[len(r) for r in rows]}")
    cells_of_letter: dict[str, list[int]] = {}
    fixed_blank = set()
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            c = grid.index(x, y)
            if ch == ".":
                fixed_blank.add(c)
            else:
                cells_of_letter.setdefault(ch, []).append(c)
    allowed: dict[int, list[int]] = {}
    for i, code in enumerate(geo.ids):
        sub = geo.subregion[i] or "QO"
        letters_for = [L for L, codes in letters.items() if sub in codes or code in codes]
        if not letters_for:
            continue  # unconstrained
        cells = sorted({c for L in letters_for for c in cells_of_letter.get(L, [])} | set(cells_of_letter.get("*", [])))
        allowed[i] = cells
    return allowed, fixed_blank


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--grid", required=True, type=parse_grid)
    ap.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3, 4])
    ap.add_argument("--iterations", type=int, default=400000)
    ap.add_argument("--t0", type=float, default=0.02)
    ap.add_argument("--t1", type=float, default=1e-4)
    ap.add_argument("--local-radius", type=int, default=2)
    ap.add_argument("--p-local", type=float, default=0.7)
    ap.add_argument("--p-targeted", type=float, default=0.2, help="share of moves that place an identifier next to one of its geographic neighbours")
    ap.add_argument("--start", choices=["rank", "projection", "layout"], default="rank")
    ap.add_argument("--start-layout", type=Path)
    ap.add_argument("--weights", type=json.loads, default=None)
    ap.add_argument("--pins", type=json.loads, default=None)
    ap.add_argument("--territories", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    profile = Profile.load()
    ids = load_ids()
    geo = load_geo(ids)
    legacy = Layout.from_board_csv(DATA / "legacy" / "8bit-board.csv")
    grid = args.grid
    if grid.cells < geo.n:
        raise SystemExit(f"grid {grid.width}x{grid.height} has {grid.cells} cells < {geo.n} identifiers")
    weights = {**DEFAULT_WEIGHTS, **(args.weights or {})}
    problem = build_problem(geo, grid, weights=weights, legacy=legacy)

    if args.start == "layout":
        start = Layout.load(args.start_layout)
    elif args.start == "projection":
        start = projection(geo, grid, profile.name, profile.cldr_version)
    else:
        start = rank_projection(geo, grid, profile.name, profile.cldr_version)

    allowed, fixed_blank = None, set()
    if args.territories:
        allowed, fixed_blank = load_territories(args.territories, grid, geo)
    if args.pins:
        allowed = allowed or {}
        for cid, (x, y) in args.pins.items():
            allowed[geo.index[cid]] = [grid.index(x, y)]
    if allowed is not None or fixed_blank:
        start = repair_start(start, geo, grid, allowed or {}, fixed_blank)

    runs = []
    best = None
    for seed in args.seeds:
        ann = Annealer(problem, grid, start, allowed=allowed, fixed_blanks=fixed_blank, seed=seed)
        stats = ann.run(args.iterations, t0=args.t0, t1=args.t1, local_radius=args.local_radius, p_local=args.p_local, p_targeted=args.p_targeted, log_every=0 if args.quiet else args.iterations // 4)
        lay = ann.to_layout()
        rep = score(lay, problem, ann.tables)
        runs.append({"seed": seed, "combined": rep["combined"], "components": rep["components"], "stats": stats})
        print(f"seed {seed}: combined {rep['combined']:.4f} ({stats['seconds']}s)", flush=True)
        if best is None or rep["combined"] < best[1]["combined"]:
            best = (lay, rep, seed)
    lay, rep, seed = best
    lay.profile, lay.cldr_version = profile.name, profile.cldr_version
    lay.generator = {
        "script": "scripts/optimize_layout.py",
        "date": dt.date.today().isoformat(),
        "method": "simulated annealing (single-item relocation/swap moves, geometric cooling)",
        "start": args.start,
        "seed": seed,
        "seeds_tried": args.seeds,
        "iterations": args.iterations,
        "t0": args.t0,
        "t1": args.t1,
        "local_radius": args.local_radius,
        "p_local": args.p_local,
        "p_targeted": args.p_targeted,
        "pins": args.pins,
        "territories": str(args.territories) if args.territories else None,
        "runs": runs,
        "score": {"weights": weights, "params": PARAMS, "combined": rep["combined"], "components": rep["components"], "diagnostics": rep["diagnostics"]},
    }
    errors = lay.validate(ids, profile)
    if errors:
        raise SystemExit("NG " + "; ".join(errors))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    lay.save(args.out)
    print(f"wrote {args.out}: best seed {seed}, combined {rep['combined']:.4f}")
    print(lay.ascii())
    return 0


def repair_start(start: Layout, geo, grid: Grid, allowed: dict[int, list[int]], fixed_blank: set[int]) -> Layout:
    """Move identifiers that violate constraints into allowed free cells
    (nearest first) so annealing starts from a feasible state."""
    from scipy.optimize import linear_sum_assignment
    import numpy as np
    x, y = grid.xy()
    pos = {}
    for i, cid in enumerate(geo.ids):
        cx, cy = start.cells[cid]
        pos[i] = grid.index(cx, cy)
    # rebuild by assignment with large penalty for disallowed cells
    cost = np.zeros((geo.n, grid.cells))
    for i in range(geo.n):
        cx, cy = x[pos[i]], y[pos[i]]
        cost[i] = (x - cx) ** 2 + (y - cy) ** 2
        if i in allowed:
            mask = np.ones(grid.cells, dtype=bool)
            mask[allowed[i]] = False
            cost[i, mask] = 1e6
    for c in fixed_blank:
        cost[:, c] = 1e9
    rows, cols = linear_sum_assignment(cost)
    if cost[rows, cols].max() >= 1e6:
        raise SystemExit("constraints are infeasible: some identifier has no allowed free cell")
    cells = {geo.ids[i]: (int(x[c]), int(y[c])) for i, c in zip(rows, cols)}
    blanks = {(int(x[c]), int(y[c])) for c in range(grid.cells)} - set(cells.values())
    return Layout(grid.width, grid.height, cells, blanks, start.profile, start.cldr_version)


if __name__ == "__main__":
    raise SystemExit(main())
