#!/usr/bin/env python3
"""Promote a layout to the repository's selected board.

Copies the layout to ``layouts/<profile>-<W>x<H>.json``, re-scores it from
scratch, and regenerates the derived artifacts: ``board.csv``,
``metadata.json``, ``docs/board.svg``, ``docs/board.csv``, and the dashboard data
``docs/data/{layout,regions,points}.json`` (``docs/index.html`` and
``docs/preview.html`` are hand-written and not regenerated).

``--runs`` collects the ``generator.runs`` records of other layout files
produced by separate ``optimize_layout.py`` processes (one per seed) into
the promoted layout's provenance, so that ``seeds_tried`` and ``runs`` list
every chain that competed, not only the winning one.

Usage:
  uv run scripts/promote_layout.py runs/s1.json --runs runs/s*.json
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



def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("layout", type=Path)
    ap.add_argument("--runs", type=Path, nargs="*", default=[], help="other layout files whose generator.runs are merged into the provenance")
    args = ap.parse_args()
    profile = Profile.load()
    ids = extract(profile)
    lay = Layout.load(args.layout)
    lay.profile, lay.cldr_version = profile.name, profile.cldr_version
    if args.runs:
        runs = {}
        for p in [args.layout, *args.runs]:
            for r in json.loads(p.read_text("utf-8")).get("generator", {}).get("runs", []):
                runs[r["seed"]] = r
        lay.generator["runs"] = [runs[s] for s in sorted(runs)]
        lay.generator["seeds_tried"] = sorted(runs)
        lay.generator["note"] = "Chains for the seeds listed in seeds_tried were run as separate optimize_layout.py processes with identical settings; their run records were collected by scripts/promote_layout.py --runs and the best chain was promoted."
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
    shutil.copy(ROOT / "board.csv", docs / "board.csv")
    # data for the Open MCT dashboard / preview (docs/ is what GitHub Pages serves)
    ddir = docs / "data"
    ddir.mkdir(exist_ok=True)
    shutil.copy(LAYOUTS / name, ddir / "layout.json")
    shutil.copy(DATA / "regions.json", ddir / "regions.json")
    import csv
    with (DATA / "geo" / "points.csv").open(encoding="utf-8") as f:
        pts = {r["id"]: {"lat": float(r["lat"]), "lon": float(r["lon"])} for r in csv.DictReader(f)}
    (ddir / "points.json").write_text(json.dumps(pts, indent=0) + "\n", "utf-8")
    print(f"promoted {args.layout} -> layouts/{name}, board.csv, metadata.json, docs/ (combined {rep['combined']:.4f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
