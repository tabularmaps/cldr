#!/usr/bin/env python3
"""Compare candidate grid dimensions under an identical search budget.

For each grid, runs ``optimize_layout.py``-equivalent annealing from the
same starting rule with the same seeds, weights, and iteration budget, and
records the best result. Also scores the baselines (alphabetical,
region-bucket, projection, naive 8bit extension) and the 8bit board itself.
Writes ``reports/grid-comparison.json`` and ``reports/grid-comparison.md``.

Usage:
  uv run scripts/compare_grids.py --grids 17x16 18x15 19x14 20x13 20x14 22x12 24x12 \
      --seeds 1 2 3 4 --iterations 400000
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cldrmap import DATA, ROOT  # noqa: E402
from cldrmap.baselines import alphabetical, legacy_extension, projection, rank_projection, region_bucket  # noqa: E402
from cldrmap.board import Layout  # noqa: E402
from cldrmap.geo import load_geo  # noqa: E402
from cldrmap.mother_set import Profile, load_ids  # noqa: E402
from cldrmap.optimize import Annealer  # noqa: E402
from cldrmap.scoring import DEFAULT_WEIGHTS, PARAMS, Grid, build_problem, score  # noqa: E402

COMPONENTS = ["neighborhood", "global", "adjacency", "direction", "region", "false_adjacency", "whitespace", "legacy"]


def parse_grid(s: str) -> Grid:
    w, h = s.lower().split("x")
    return Grid(int(w), int(h))


def row(name: str, rep: dict, extra: str = "") -> str:
    d = rep["diagnostics"]
    comps = " | ".join(f"{rep['components'][k]:.3f}" for k in COMPONENTS)
    return f"| {name} | {rep['grid'][0]}x{rep['grid'][1]} | {d['blank_cells']} | {rep['combined']:.3f} | {comps} | {d['adjacency_orthogonal']}/{d['adjacency_pairs']} | {d['direction_violations']} | {d['region_components_excess']} | {d['enclosed_holes']} | {d['legacy'].get('moved_fraction', 0):.0%} |{extra}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--grids", nargs="+", type=parse_grid, default=[parse_grid(g) for g in ["17x16", "18x15", "19x14", "20x13", "20x14", "22x12", "24x12"]])
    ap.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3, 4])
    ap.add_argument("--iterations", type=int, default=400000)
    ap.add_argument("--t0", type=float, default=0.02)
    ap.add_argument("--t1", type=float, default=1e-4)
    ap.add_argument("--local-radius", type=int, default=2)
    ap.add_argument("--p-local", type=float, default=0.7)
    ap.add_argument("--p-targeted", type=float, default=0.2)
    ap.add_argument("--weights", type=json.loads, default=None)
    ap.add_argument("--out-dir", type=Path, default=ROOT / "reports")
    ap.add_argument("--layout-dir", type=Path, default=ROOT / "layouts" / "candidates")
    ap.add_argument("--tag", default="")
    ap.add_argument("--merge", nargs="+", type=Path, help="merge per-grid JSON reports (from parallel runs) into one report instead of running")
    args = ap.parse_args()
    if args.merge:
        return merge(args.merge, args.out_dir, args.tag)

    profile = Profile.load()
    ids = load_ids()
    geo = load_geo(ids)
    legacy = Layout.from_board_csv(DATA / "legacy" / "8bit-board.csv")
    weights = {**DEFAULT_WEIGHTS, **(args.weights or {})}
    args.out_dir.mkdir(parents=True, exist_ok=True)
    args.layout_dir.mkdir(parents=True, exist_ok=True)

    results = {"date": dt.date.today().isoformat(), "profile": profile.name, "weights": weights, "params": PARAMS, "seeds": args.seeds, "iterations": args.iterations, "t0": args.t0, "t1": args.t1, "baselines": {}, "grids": {}}

    # baselines --------------------------------------------------------
    ext = legacy_extension(legacy, geo, profile.name, profile.cldr_version)
    g = Grid(ext.width, ext.height)
    results["baselines"]["legacy_extension"] = score(ext, build_problem(geo, g, weights=weights, legacy=legacy))
    geo_sub = load_geo([i for i in ids if i in legacy.cells])
    results["baselines"]["8bit_partial"] = score(legacy, build_problem(geo_sub, Grid(16, 16), weights=weights, legacy=legacy))
    for grid in args.grids:
        key = f"{grid.width}x{grid.height}"
        problem = build_problem(geo, grid, weights=weights, legacy=legacy)
        tables = grid.distance_tables()
        base = {name: score(fn(geo, grid, profile.name, profile.cldr_version), problem, tables) for name, fn in [("alphabetical", alphabetical), ("region_bucket", region_bucket), ("projection", projection), ("rank_projection", rank_projection)]}
        start = rank_projection(geo, grid, profile.name, profile.cldr_version)
        runs, best = [], None
        for seed in args.seeds:
            ann = Annealer(problem, grid, start, seed=seed)
            stats = ann.run(args.iterations, t0=args.t0, t1=args.t1, local_radius=args.local_radius, p_local=args.p_local, p_targeted=args.p_targeted)
            lay = ann.to_layout()
            rep = score(lay, problem, tables)
            runs.append({"seed": seed, "combined": rep["combined"], "components": rep["components"], "seconds": stats["seconds"]})
            print(f"{key} seed {seed}: {rep['combined']:.4f} ({stats['seconds']}s)", flush=True)
            if best is None or rep["combined"] < best[1]["combined"]:
                best = (lay, rep, seed, stats)
        lay, rep, seed, stats = best
        lay.profile, lay.cldr_version = profile.name, profile.cldr_version
        lay.generator = {"script": "scripts/compare_grids.py", "date": results["date"], "method": "simulated annealing", "start": "rank", "seed": seed, "seeds_tried": args.seeds, "iterations": args.iterations, "t0": args.t0, "t1": args.t1, "local_radius": stats["local_radius"], "p_local": stats["p_local"], "p_targeted": stats["p_targeted"], "runs": runs, "score": {"weights": weights, "params": PARAMS, "combined": rep["combined"], "components": rep["components"], "diagnostics": rep["diagnostics"]}}
        lay.save(args.layout_dir / f"{key}{args.tag}.json")
        combined = [r["combined"] for r in runs]
        results["grids"][key] = {"best_seed": seed, "best": rep, "runs": runs, "mean_combined": sum(combined) / len(combined), "min_combined": min(combined), "max_combined": max(combined), "baselines": base, "aspect": round(grid.width / grid.height, 3), "blanks": grid.cells - geo.n}

    write_report(results, args.out_dir, args.tag)
    return 0


def merge(paths: list[Path], out_dir: Path, tag: str) -> int:
    results = None
    for p in sorted(paths):
        part = json.loads(p.read_text("utf-8"))
        if results is None:
            results = part
        else:
            for k in ("weights", "params", "seeds", "iterations", "t0", "t1"):
                if part[k] != results[k]:
                    raise SystemExit(f"{p}: {k} differs from the first report; runs are not comparable")
            results["grids"].update(part["grids"])
    results["grids"] = dict(sorted(results["grids"].items(), key=lambda kv: (int(kv[0].split("x")[0]), int(kv[0].split("x")[1]))))
    write_report(results, out_dir, tag)
    return 0


def write_report(results: dict, out_dir: Path, tag: str) -> None:
    weights = results["weights"]
    (out_dir / f"grid-comparison{tag}.json").write_text(json.dumps(results, indent=1) + "\n", "utf-8")
    lines = [f"# Grid comparison ({results['date']})", "", f"Weights: `{json.dumps(weights)}`  ", f"Seeds: {results['seeds']}, iterations per seed: {results['iterations']}, t0={results['t0']}, t1={results['t1']}", "",
             "| layout | grid | blanks | combined | " + " | ".join(COMPONENTS) + " | adj kept | dir viol | region excess | holes | moved vs 8bit |",
             "|---|---|---|---|" + "---|" * len(COMPONENTS) + "---|---|---|---|---|"]
    lines.append(row("8bit (250 ids, partial)", results["baselines"]["8bit_partial"]))
    lines.append(row("8bit naive extension", results["baselines"]["legacy_extension"]))
    for key, r in results["grids"].items():
        for name in ("alphabetical", "region_bucket", "rank_projection"):
            lines.append(row(f"{name} {key}", r["baselines"][name]))
        lines.append(row(f"**annealed {key}** (seed {r['best_seed']})", r["best"], f" mean over seeds {r['mean_combined']:.3f} [{r['min_combined']:.3f}, {r['max_combined']:.3f}]"))
    (out_dir / f"grid-comparison{tag}.md").write_text("\n".join(lines) + "\n", "utf-8")
    print(f"wrote {out_dir / ('grid-comparison' + tag + '.md')}")


if __name__ == "__main__":
    raise SystemExit(main())
