#!/usr/bin/env python3
"""Build the geographic inputs used for scoring and optimization.

Outputs (committed, reviewed):

- ``data/geo/points.csv``      one representative point per identifier
- ``data/geo/adjacency.csv``   undirected land-boundary pairs
- ``data/geo/ne_units.json``   how every Natural Earth map unit was mapped

Inputs:

- ``data/geo/raw/wikidata_p297_p625_<date>.csv``  committed SPARQL snapshot
  (Wikidata, CC0): items with an ISO 3166-1 alpha-2 (P297) and their
  coordinate location (P625).
- ``data/geo/points_supplement.csv``  reviewed manual points for identifiers
  without a P297 entry (EA, IC), with source metadata.
- Natural Earth 5.1.2 ``ne_10m_admin_0_map_units.geojson`` (public domain),
  downloaded to ``--cache`` if absent and verified against the committed
  sha256.
- ``data/geo/adjacency_supplement.csv``  reviewed manual land-border pairs.

Representative-point rule: the P625 value of the Wikidata item carrying
P297=<id>; when several items carry the same code, the item with the lowest
Q-number is used (documented, mechanical).

Adjacency rule: two map units are land neighbours when they share at least
two identical vertices (coordinates rounded to 1e-6 degrees) and map to
different identifiers. A unit maps to an identifier by, in order,
ISO_A2_EH, then ADM0_ISO (Natural Earth's "ISO point of view" alpha-3),
then ADM0_A3 (Natural Earth's own alpha-3), translated to alpha-2 through
the dataset's own ISO_A3_EH -> ISO_A2_EH table. Units that still do not map
to a mother-set identifier are dropped and listed in ``ne_units.json``.

Usage:
  uv run scripts/build_geographic_inputs.py [--cache .cache]
"""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cldrmap import DATA  # noqa: E402
from cldrmap.mother_set import load_ids  # noqa: E402

GEO = DATA / "geo"
NE_VERSION = "v5.1.2"
NE_FILE = "ne_10m_admin_0_map_units.geojson"
NE_URL = f"https://raw.githubusercontent.com/nvkelso/natural-earth-vector/{NE_VERSION}/geojson/{NE_FILE}"
POINT_RE = re.compile(r"Point\(([-\d.eE+]+) ([-\d.eE+]+)\)")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fetch_ne(cache: Path) -> Path:
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / NE_FILE
    expected = (GEO / "raw" / f"{NE_FILE}.sha256").read_text().split()[0]
    if not target.exists():
        print(f"downloading {NE_URL}")
        urllib.request.urlretrieve(NE_URL, target)
    actual = sha256(target)
    if actual != expected:
        raise SystemExit(f"{target} sha256 {actual} != expected {expected}")
    return target


def build_points(ids: list[str]) -> list[dict]:
    snapshots = sorted((GEO / "raw").glob("wikidata_p297_p625_*.csv"))
    snap = snapshots[-1]
    date = snap.stem.rsplit("_", 1)[1]
    by: dict[str, list[dict]] = collections.defaultdict(list)
    with snap.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            by[row["code"]].append(row)
    manual = {}
    with (GEO / "points_supplement.csv").open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            manual[row["id"]] = row
    out = []
    for code in ids:
        if code in manual:
            m = manual[code]
            out.append({"id": code, "lat": float(m["lat"]), "lon": float(m["lon"]), "source": m["source"], "source_id": m["source_id"], "label": "", "snapshot": "points_supplement.csv"})
            continue
        rows = [r for r in by.get(code, []) if r["coord"]]
        if not rows:
            raise SystemExit(f"{code}: no Wikidata coordinate and no supplement entry")
        rows.sort(key=lambda r: int(r["item"].rsplit("Q", 1)[1]))
        r = rows[0]
        lon, lat = map(float, POINT_RE.match(r["coord"]).groups())
        out.append({"id": code, "lat": round(lat, 6), "lon": round(lon, 6), "source": "wikidata", "source_id": r["item"].rsplit("/", 1)[1], "label": r["itemLabel"], "snapshot": snap.name})
    return out


def alpha3_table(features, ids: set[str]) -> dict[str, str]:
    """ISO_A3_EH -> ISO_A2_EH from units that carry a mother-set identifier."""
    table = {}
    for ft in features:
        p = ft["properties"]
        a2, a3 = p.get("ISO_A2_EH"), p.get("ISO_A3_EH")
        if a2 in ids and a3 and a3 != "-99":
            table.setdefault(a3, a2)
    return table


def map_unit(p: dict, ids: set[str], a3: dict[str, str]) -> tuple[str | None, str]:
    for field in ("ISO_A2_EH",):
        v = p.get(field)
        if v in ids:
            return v, field
    for field in ("ADM0_ISO", "ADM0_A3"):
        v = a3.get(p.get(field))
        if v in ids:
            return v, field
    return None, "unmapped"


def build_adjacency(ids: list[str], ne_path: Path) -> tuple[list[dict], list[dict]]:
    idset = set(ids)
    data = json.loads(ne_path.read_text("utf-8"))
    feats = data["features"]
    a3 = alpha3_table(feats, idset)
    units = []
    vert: dict[tuple[float, float], set[str]] = collections.defaultdict(set)
    for ft in feats:
        p = ft["properties"]
        code, how = map_unit(p, idset, a3)
        units.append({"name": p["NAME"], "iso_a2_eh": p.get("ISO_A2_EH"), "adm0_iso": p.get("ADM0_ISO"), "adm0_a3": p.get("ADM0_A3"), "mapped_to": code, "mapped_by": how})
        if code is None:
            continue
        g = ft["geometry"]
        polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        for poly in polys:
            for ring in poly:
                for x, y in ring:
                    vert[(round(x, 6), round(y, 6))].add(code)
    shared: collections.Counter = collections.Counter()
    for codes in vert.values():
        if len(codes) < 2:
            continue
        cs = sorted(codes)
        for i in range(len(cs)):
            for j in range(i + 1, len(cs)):
                shared[(cs[i], cs[j])] += 1
    pairs = [{"a": a, "b": b, "source": f"natural-earth-{NE_VERSION}", "shared_vertices": n} for (a, b), n in sorted(shared.items()) if n >= 2]
    rejected = [{"a": a, "b": b, "shared_vertices": n} for (a, b), n in sorted(shared.items()) if n < 2]
    with (GEO / "adjacency_supplement.csv").open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            a, b = sorted([row["a"], row["b"]])
            if a not in idset or b not in idset:
                raise SystemExit(f"supplement pair {a}-{b} not in mother set")
            if any(p["a"] == a and p["b"] == b for p in pairs):
                raise SystemExit(f"supplement pair {a}-{b} already derived; remove it")
            pairs.append({"a": a, "b": b, "source": "manual", "shared_vertices": 0})
    pairs.sort(key=lambda p: (p["a"], p["b"]))
    units_report = {"natural_earth": {"version": NE_VERSION, "file": NE_FILE, "url": NE_URL, "sha256": sha256(ne_path)}, "units": units, "rejected_single_vertex_pairs": rejected}
    return pairs, [units_report]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache", type=Path, default=Path(".cache"))
    args = ap.parse_args()
    ids = load_ids()
    points = build_points(ids)
    with (GEO / "points.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "lat", "lon", "source", "source_id", "label", "snapshot"])
        w.writeheader()
        w.writerows(points)
    ne_path = fetch_ne(args.cache)
    pairs, (units_report,) = build_adjacency(ids, ne_path)
    with (GEO / "adjacency.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["a", "b", "source", "shared_vertices"])
        w.writeheader()
        w.writerows(pairs)
    (GEO / "ne_units.json").write_text(json.dumps(units_report, indent=1, ensure_ascii=False) + "\n", "utf-8")
    deg = collections.Counter()
    for p in pairs:
        deg[p["a"]] += 1
        deg[p["b"]] += 1
    print(f"points: {len(points)}  adjacency pairs: {len(pairs)}  identifiers with a land neighbour: {len(deg)}")
    print("unmapped NE units:", [u["name"] for u in units_report["units"] if u["mapped_to"] is None])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
