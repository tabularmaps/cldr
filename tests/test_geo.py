import csv

import numpy as np

from cldrmap import DATA
from cldrmap.geo import LON_CUT, haversine_km, unwrap_lon


def test_every_identifier_has_inputs(geo, ids):
    assert geo.ids == ids
    assert np.isfinite(geo.lat).all() and np.isfinite(geo.lon).all()
    assert (np.abs(geo.lat) <= 90).all() and (np.abs(geo.lon) <= 180).all()
    for i, cid in enumerate(ids):
        assert geo.subregion[i] is not None or cid in {"AC", "AQ", "CP", "DG", "TA"}


def test_supplements_have_sources():
    with (DATA / "geo" / "points_supplement.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert {r["id"] for r in rows} == {"EA", "IC"}
    for r in rows:
        assert r["source"] and r["source_id"] and len(r["note"]) > 20
    with (DATA / "geo" / "adjacency_supplement.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows and all(r["source"] == "manual" and len(r["note"]) > 20 for r in rows)


def test_points_have_source_metadata():
    with (DATA / "geo" / "points.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 257
    assert all(r["source"] and r["source_id"] for r in rows)


def test_adjacency_is_clean(geo):
    pairs = geo.adjacency
    assert pairs
    assert all(a != b for a, b in pairs), "self-adjacency"
    norm = {(min(a, b), max(a, b)) for a, b in pairs}
    assert len(norm) == len(pairs), "duplicate pair"
    with (DATA / "geo" / "adjacency.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            assert r["a"] in geo.index and r["b"] in geo.index
            assert r["a"] < r["b"]
    ids = geo.ids
    known = {("CA", "US"), ("ES", "PT"), ("XK", "RS"), ("CN", "MO"), ("EA", "MA"), ("KP", "KR"), ("DJ", "SO")}
    for a, b in known:
        assert (min(geo.index[a], geo.index[b]), max(geo.index[a], geo.index[b])) in norm, (a, b)
    assert ("JP", ids) and not any({ids[a], ids[b]} == {"JP", "KR"} for a, b in pairs)


def test_antimeridian():
    # Fiji (178E) and Samoa (172W) are ~1100 km apart, not ~30000
    d = haversine_km(-18.0, 178.0, -13.8, -172.2)
    assert 1000 < d < 1300
    assert unwrap_lon(-172.2) == 187.8
    assert unwrap_lon(-98.0) == -98.0
    assert unwrap_lon(LON_CUT) == LON_CUT + 360


def test_unwrapped_order_puts_polynesia_east_of_fiji(geo):
    lon = {c: geo.lon_unwrapped[i] for i, c in enumerate(geo.ids)}
    assert lon["FJ"] < lon["WS"] < lon["CK"] < lon["PF"] < lon["PN"]
    assert lon["US"] < lon["GB"] and lon["PN"] > lon["NZ"]


def test_knn_symmetric_sanity(geo):
    nn = geo.knn(6)
    i = geo.index["GB"]
    assert geo.index["IE"] in nn[i]
    assert geo.index["JP"] not in nn[i]
