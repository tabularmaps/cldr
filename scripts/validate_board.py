#!/usr/bin/env python3
"""Validate a layout JSON and the derived board.csv against the profile.

Checks: pinned CLDR source checksum, mother-set extraction, grid dimensions,
one cell per identifier, no unknown identifier, no omitted member, every
cell either placed or declared blank, board.csv and metadata.json agree with
the layout, and the recorded scores match a recomputation.

Usage:
  uv run scripts/validate_board.py                  # committed artifacts
  uv run scripts/validate_board.py layouts/x.json   # any layout
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cldrmap import DATA, LAYOUTS, ROOT  # noqa: E402
from cldrmap.board import Layout  # noqa: E402
from cldrmap.geo import load_geo  # noqa: E402
from cldrmap.mother_set import Profile, SourceMismatch, extract  # noqa: E402
from cldrmap.scoring import Grid, build_problem, score  # noqa: E402

TOLERANCE = 1e-6


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("layout", type=Path, nargs="?")
    ap.add_argument("--board-csv", type=Path, default=ROOT / "board.csv")
    ap.add_argument("--metadata", type=Path, default=ROOT / "metadata.json")
    args = ap.parse_args()
    problems: list[str] = []

    profile = Profile.load()
    try:
        ids = extract(profile)
    except SourceMismatch as e:
        print(f"NG {e}")
        return 1
    print(f"OK mother set: {len(ids)} identifiers from CLDR {profile.cldr_version} ({profile.name})")

    meta = json.loads(args.metadata.read_text("utf-8")) if args.metadata.exists() else None
    layout_path = args.layout or (LAYOUTS / meta["layout"] if meta else None)
    if layout_path is None or not layout_path.exists():
        print("NG no layout to validate (metadata.json missing or layout path absent)")
        return 1
    layout = Layout.load(layout_path)
    problems += layout.validate(ids, profile)
    doc = json.loads(layout_path.read_text("utf-8"))
    if doc.get("board") != layout.rows():
        problems.append("layout.board does not match placements")
    if doc.get("identifier_count") != len(layout.cells) or doc.get("structural_space_count") != len(layout.blanks):
        problems.append("declared counts in layout do not match placements/structural_spaces")

    if args.layout is None:
        # committed artifact checks
        csv_layout = Layout.from_board_csv(args.board_csv)
        if csv_layout.rows() != layout.rows():
            problems.append(f"{args.board_csv} differs from {layout_path}")
        if meta:
            for key, want in (("width", layout.width), ("height", layout.height), ("identifier_count", len(layout.cells)), ("structural_space_count", len(layout.blanks)), ("profile", profile.name), ("cldr_version", profile.cldr_version)):
                if meta.get(key) != want:
                    problems.append(f"metadata.json {key}={meta.get(key)!r} but layout has {want!r}")
        rec = doc.get("generator", {}).get("score")
        if rec:
            geo = load_geo(ids)
            legacy = Layout.from_board_csv(DATA / "legacy" / "8bit-board.csv")
            problem = build_problem(geo, Grid(layout.width, layout.height), weights=rec.get("weights"), params=rec.get("params"), legacy=legacy)
            rep = score(layout, problem)
            if abs(rep["combined"] - rec["combined"]) > TOLERANCE:
                problems.append(f"recorded combined score {rec['combined']} != recomputed {rep['combined']}")
            for k, v in rec["components"].items():
                if abs(rep["components"][k] - v) > TOLERANCE:
                    problems.append(f"recorded component {k}={v} != recomputed {rep['components'][k]}")
            if not problems:
                print(f"OK recorded score {rec['combined']:.6f} matches recomputation")
    if problems:
        print("\n".join("NG " + p for p in problems))
        return 1
    print(f"OK {layout_path.name}: {layout.width}x{layout.height}, {len(layout.cells)} identifiers, {len(layout.blanks)} structural spaces")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
