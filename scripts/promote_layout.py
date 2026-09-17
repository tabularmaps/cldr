#!/usr/bin/env python3
"""Promote a layout to the repository's selected board.

Copies the layout to ``layouts/<profile>-<W>x<H>.json`` (adding any pins'
provenance already inside it), and regenerates the derived artifacts:
``board.csv``, ``metadata.json``, ``docs/board.svg``, ``docs/index.html``.

Usage:
  uv run scripts/promote_layout.py layouts/candidates/19x14.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cldrmap import DATA, LAYOUTS, ROOT  # noqa: E402
from cldrmap.board import Layout  # noqa: E402
from cldrmap.geo import load_geo  # noqa: E402
from cldrmap.mother_set import Profile, extract  # noqa: E402
from cldrmap.render import render_svg  # noqa: E402
from cldrmap.scoring import Grid, build_problem, score  # noqa: E402

INDEX_HTML = """<!doctype html>
<meta charset="utf-8">
<title>CLDR Tabular Map</title>
<style>
  body {{ font: 14px/1.5 system-ui, sans-serif; margin: 2rem auto; max-width: 64rem; padding: 0 1rem; color: #222; }}
  img {{ max-width: 100%; height: auto; }}
  code {{ background: #f4f4f4; padding: 0 .2em; }}
</style>
<h1>CLDR Tabular Map</h1>
<p><strong>One identifier, one equal cell.</strong> CLDR {cldr} regular region identifiers ({count}) on a {w} × {h} grid
with {blanks} structural blank cells. Cell colour is the CLDR/M49 subregion (informational only).</p>
<p><a href="board.svg"><img src="board.svg" alt="board"></a></p>
<p>Data: <a href="../board.csv"><code>board.csv</code></a>, <a href="../metadata.json"><code>metadata.json</code></a>,
<a href="../layouts/{layout}"><code>layouts/{layout}</code></a>. Documentation and non-claims:
<a href="https://github.com/tabularmaps/cldr">github.com/tabularmaps/cldr</a>.</p>
<p>Cell size does not represent area, population or importance; inclusion expresses no recognition; the layout settles no
territorial question; proximity is approximate; the arrangement is the best found under a documented objective, not a global optimum.</p>
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("layout", type=Path)
    args = ap.parse_args()
    profile = Profile.load()
    ids = extract(profile)
    lay = Layout.load(args.layout)
    lay.profile, lay.cldr_version = profile.name, profile.cldr_version
    errors = lay.validate(ids, profile)
    if errors:
        raise SystemExit("NG " + "; ".join(errors))
    geo = load_geo(ids)
    legacy = Layout.from_board_csv(DATA / "legacy" / "8bit-board.csv")
    rec = lay.generator.get("score", {})
    problem = build_problem(geo, Grid(lay.width, lay.height), weights=rec.get("weights"), params=rec.get("params"), legacy=legacy)
    rep = score(lay, problem)
    lay.generator["score"] = {"weights": rep["weights"], "params": rep["params"], "combined": rep["combined"], "components": rep["components"], "diagnostics": rep["diagnostics"]}

    name = f"{profile.name}-{lay.width}x{lay.height}.json"
    LAYOUTS.mkdir(exist_ok=True)
    lay.save(LAYOUTS / name)
    (ROOT / "board.csv").write_text(lay.board_csv(), "utf-8")
    meta = {
        "title": "CLDR Tabular Map",
        "tagline": "One identifier, one equal cell.",
        "profile": profile.name,
        "cldr_version": profile.cldr_version,
        "cldr_source_sha256": profile.source_sha256,
        "layout": name,
        "width": lay.width,
        "height": lay.height,
        "cell_shape": "square",
        "aspect_ratio": round(lay.width / lay.height, 4),
        "identifier_count": len(lay.cells),
        "structural_space_count": len(lay.blanks),
        "identifier_case": {"layout_json": "uppercase", "board_csv": "lowercase"},
        "blank_representation": {"layout_json": "structural_spaces list; board entries \"\"", "board_csv": "empty field"},
        "generated": dt.date.today().isoformat(),
        "score": {"combined": rep["combined"], "components": rep["components"], "weights": rep["weights"]},
        "legacy_8bit": rep["diagnostics"]["legacy"],
        "predecessor": "https://github.com/tabularmaps/8bit",
        "license": "CC0-1.0 (this repository); see NOTICE.md for inputs",
    }
    (ROOT / "metadata.json").write_text(json.dumps(meta, indent=1) + "\n", "utf-8")
    docs = ROOT / "docs"
    docs.mkdir(exist_ok=True)
    title = f"CLDR Tabular Map — CLDR {profile.cldr_version}, {lay.width}x{lay.height}, {len(lay.cells)} identifiers"
    (docs / "board.svg").write_text(render_svg(lay, geo, title=title), "utf-8")
    (docs / "index.html").write_text(INDEX_HTML.format(cldr=profile.cldr_version, count=len(lay.cells), w=lay.width, h=lay.height, blanks=len(lay.blanks), layout=name), "utf-8")
    shutil.copy(ROOT / "board.csv", docs / "board.csv")
    print(f"promoted {args.layout} -> layouts/{name}, board.csv, metadata.json, docs/ (combined {rep['combined']:.4f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
