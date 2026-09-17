#!/usr/bin/env python3
"""Weight-sensitivity analysis for the selected grid.

For each alternative weight set (each component halved and doubled, plus a
"legacy-aware" set), (a) re-scores the selected layout, (b) re-optimizes
from the same start with the same seed and budget, and (c) reports how far
the re-optimized board moves from the selected one. Writes
``reports/sensitivity.json`` and ``reports/sensitivity.md``.

Usage:
  uv run scripts/sensitivity.py layouts/cldr-48.2-regular-2alpha-19x14.json --iterations 1500000
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cldrmap import DATA, ROOT  # noqa: E402
from cldrmap.baselines import rank_projection  # noqa: E402
from cldrmap.board import Layout  # noqa: E402
from cldrmap.geo import load_geo  # noqa: E402
from cldrmap.mother_set import load_ids  # noqa: E402
from cldrmap.optimize import Annealer  # noqa: E402
from cldrmap.scoring import DEFAULT_WEIGHTS, Grid, build_problem, legacy_metrics, score  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("layout", type=Path)
    ap.add_argument("--iterations", type=int, default=1500000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out-dir", type=Path, default=ROOT / "reports")
    args = ap.parse_args()
    ids = load_ids()
    geo = load_geo(ids)
    legacy = Layout.from_board_csv(DATA / "legacy" / "8bit-board.csv")
    sel = Layout.load(args.layout)
    grid = Grid(sel.width, sel.height)
    base_w = sel.generator["score"]["weights"]
    variants = {"default": dict(base_w)}
    for k in ("neighborhood", "global", "adjacency", "direction", "region", "false_adjacency", "whitespace"):
        for f, tag in ((0.5, "half"), (2.0, "double")):
            w = dict(base_w)
            w[k] = base_w[k] * f
            variants[f"{k}_{tag}"] = w
    w = dict(base_w)
    w["legacy"] = 1.0
    variants["legacy_1.0"] = w
    start = rank_projection(geo, grid)
    sel_cells = {cid: xy for cid, xy in sel.cells.items()}
    rows = []
    for name, weights in variants.items():
        problem = build_problem(geo, grid, weights=weights, legacy=legacy)
        s_sel = score(sel, problem)
        ann = Annealer(problem, grid, start, seed=args.seed)
        stats = ann.run(args.iterations, t0=0.02)
        lay = ann.to_layout()
        s_new = score(lay, problem)
        s_new_default = score(lay, build_problem(geo, grid, weights=base_w, legacy=legacy))
        moved = legacy_metrics(lay, sel_cells)
        rows.append({"variant": name, "weights": weights, "selected_under_variant": s_sel["combined"], "reoptimized_under_variant": s_new["combined"], "reoptimized_under_default": s_new_default["combined"], "reoptimized_components": s_new["components"], "moved_vs_selected": moved, "seconds": stats["seconds"]})
        print(f"{name:24s} selected={s_sel['combined']:.4f} reopt={s_new['combined']:.4f} (default weights: {s_new_default['combined']:.4f}) moved {moved['moved_fraction']:.0%} mean manhattan {moved['mean_manhattan']:.2f}", flush=True)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "sensitivity.json").write_text(json.dumps({"layout": str(args.layout), "seed": args.seed, "iterations": args.iterations, "rows": rows}, indent=1) + "\n", "utf-8")
    lines = [f"# Weight sensitivity ({args.layout.name}, seed {args.seed}, {args.iterations} iterations per variant)", "", "| variant | selected board scored under variant | re-optimized board under variant | re-optimized board under default weights | identifiers moved vs selected | mean Manhattan |", "|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['variant']} | {r['selected_under_variant']:.3f} | {r['reoptimized_under_variant']:.3f} | {r['reoptimized_under_default']:.3f} | {r['moved_vs_selected']['moved_fraction']:.0%} | {r['moved_vs_selected']['mean_manhattan']:.2f} |")
    (args.out_dir / "sensitivity.md").write_text("\n".join(lines) + "\n", "utf-8")
    print(f"wrote {args.out_dir / 'sensitivity.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
