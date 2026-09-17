#!/usr/bin/env python3
"""Score any board independently of the optimizer.

Accepts a layout JSON (``layouts/*.json``) or a matrix ``board.csv``. Prints
component scores, the combined score, and diagnostics; ``--json`` writes the
full report. Boards that omit mother-set members are scored on the subset
they contain and flagged as partial (used for the predecessor 8bit board).

Usage:
  uv run scripts/score_layout.py layouts/cldr-48.2-19x14.json
  uv run scripts/score_layout.py data/legacy/8bit-board.csv --partial
  uv run scripts/score_layout.py board.csv --weights '{"adjacency": 3}'
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cldrmap import DATA  # noqa: E402
from cldrmap.board import Layout  # noqa: E402
from cldrmap.geo import load_geo  # noqa: E402
from cldrmap.mother_set import load_ids  # noqa: E402
from cldrmap.scoring import Grid, build_problem, score  # noqa: E402


def load_any(path: Path) -> Layout:
    if path.suffix.lower() == ".json":
        return Layout.load(path)
    return Layout.from_board_csv(path)


def format_report(rep: dict, name: str) -> str:
    lines = [f"{name}: grid {rep['grid'][0]}x{rep['grid'][1]}  combined {rep['combined']:.4f}"]
    for k, v in rep["components"].items():
        lines.append(f"  {k:16s} {v:8.4f}  (weight {rep['weights'][k]})")
    d = rep["diagnostics"]
    lines.append(f"  adjacency kept {d['adjacency_orthogonal']}/{d['adjacency_pairs']} orthogonal, {d['adjacency_within_1']} within 1; "
                 f"direction violations {d['direction_violations']}/{d['direction_relations']}; "
                 f"region components excess {d['region_components_excess']}; false-adjacent pairs {d['false_adjacent_pairs']:.1f}; "
                 f"blank cells {d['blank_cells']} (holes {d['enclosed_holes']}, components {d['blank_components']}); "
                 f"spearman {d['spearman_geo_vs_grid']:.3f}")
    if d["legacy"].get("compared"):
        lg = d["legacy"]
        lines.append(f"  legacy: {lg['moved']}/{lg['compared']} moved ({lg['moved_fraction']:.1%}), mean Manhattan {lg['mean_manhattan']:.2f}, offset {lg['offset']}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("board", type=Path)
    ap.add_argument("--partial", action="store_true", help="allow boards that omit mother-set members")
    ap.add_argument("--weights", type=json.loads, default=None, help="JSON object overriding default weights")
    ap.add_argument("--legacy", type=Path, default=DATA / "legacy" / "8bit-board.csv")
    ap.add_argument("--json", type=Path, help="write the full report here")
    args = ap.parse_args()

    layout = load_any(args.board)
    ids = load_ids()
    present = [i for i in ids if i in layout.cells]
    extra = sorted(set(layout.cells) - set(ids))
    if extra:
        print(f"NG unrecognized identifiers on the board: {extra}", file=sys.stderr)
        return 1
    if len(present) != len(ids):
        if not args.partial:
            print(f"NG board omits {len(ids) - len(present)} mother-set members: {sorted(set(ids) - set(present))}. Use --partial to score the subset.", file=sys.stderr)
            return 1
    geo = load_geo(present)
    legacy = Layout.from_board_csv(args.legacy) if args.legacy and args.legacy.exists() else None
    grid = Grid(layout.width, layout.height)
    problem = build_problem(geo, grid, weights=args.weights, legacy=legacy)
    rep = score(layout, problem)
    rep["board"] = str(args.board)
    rep["partial"] = len(present) != len(ids)
    rep["identifiers_scored"] = len(present)
    print(format_report(rep, args.board.name + (" (partial)" if rep["partial"] else "")))
    if args.json:
        args.json.write_text(json.dumps(rep, indent=1) + "\n", "utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
