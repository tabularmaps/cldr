#!/usr/bin/env python3
"""Render a layout to SVG (and the docs/ static preview for the selected board).

Usage:
  uv run scripts/render_preview.py layouts/candidates/19x14.json --out reports/19x14.svg
  uv run scripts/render_preview.py            # committed board -> docs/board.svg + docs/index.html
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cldrmap import LAYOUTS, ROOT  # noqa: E402
from cldrmap.board import Layout  # noqa: E402
from cldrmap.geo import load_geo  # noqa: E402
from cldrmap.render import render_svg  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("layout", type=Path, nargs="?")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--title", default=None)
    args = ap.parse_args()
    if args.layout is None:
        meta = json.loads((ROOT / "metadata.json").read_text("utf-8"))
        args.layout = LAYOUTS / meta["layout"]
        args.out = args.out or ROOT / "docs" / "board.svg"
        args.title = args.title or f"CLDR Tabular Map — CLDR {meta['cldr_version']}, {meta['width']}x{meta['height']}, {meta['identifier_count']} identifiers"
    layout = Layout.load(args.layout)
    geo = load_geo(sorted(layout.cells))
    svg = render_svg(layout, geo, title=args.title)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(svg, "utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
