import numpy as np
import pytest

from cldrmap.baselines import alphabetical, legacy_extension, projection, rank_projection, region_bucket
from cldrmap.board import Layout
from cldrmap.optimize import Annealer, anneal
from cldrmap.scoring import DEFAULT_WEIGHTS, Grid, build_problem, compact_mean_distance, score


@pytest.fixture(scope="module")
def problem(geo, legacy):
    return build_problem(geo, Grid(19, 14), legacy=legacy)


def test_scoring_is_deterministic(geo, problem):
    lay = rank_projection(geo, Grid(19, 14))
    a, b = score(lay, problem), score(lay, problem)
    assert a["components"] == b["components"] and a["combined"] == b["combined"]


def test_components_combine_as_documented(geo, problem):
    rep = score(alphabetical(geo, Grid(19, 14)), problem)
    assert rep["combined"] == pytest.approx(sum(DEFAULT_WEIGHTS[k] * v for k, v in rep["components"].items()))
    assert set(rep["components"]) == set(DEFAULT_WEIGHTS)
    assert all(v >= -1e-9 for k, v in rep["components"].items() if k != "region")


def test_baselines_rank_sensibly(geo, problem):
    g = Grid(19, 14)
    s = {name: score(fn(geo, g), problem)["combined"] for name, fn in [("alphabetical", alphabetical), ("region_bucket", region_bucket), ("projection", projection)]}
    assert s["projection"] < s["region_bucket"] < s["alphabetical"]


def test_legacy_boards_can_be_scored(geo, legacy, ids):
    ext = legacy_extension(legacy, geo)
    assert ext.validate(ids, strict_profile=False) == []
    rep = score(ext, build_problem(geo, Grid(ext.width, ext.height), legacy=legacy))
    assert rep["diagnostics"]["legacy"]["moved"] == 0
    from cldrmap.geo import load_geo
    sub = load_geo([i for i in ids if i in legacy.cells])
    rep = score(legacy, build_problem(sub, Grid(16, 16), legacy=legacy))
    assert rep["diagnostics"]["blank_cells"] == 6


def test_incremental_energy_matches_full(geo, problem):
    ann = Annealer(problem, Grid(19, 14), rank_projection(geo, Grid(19, 14)), seed=7)
    e = ann.full_energy()
    rng = np.random.default_rng(0)
    for _ in range(200):
        m = None
        while m is None:
            m = ann.propose(3, 0.5)
        d = ann.delta(*m)
        ann.apply(*m)
        e2 = ann.full_energy()
        assert e2 - e == pytest.approx(d, abs=1e-9)
        e = e2
    rep = score(ann.to_layout(), problem, ann.tables)
    assert rep["combined"] == pytest.approx(e + DEFAULT_WEIGHTS["global"] * 1.0 - DEFAULT_WEIGHTS["region"] * 1.0, abs=1e-9)


def test_fixed_seed_reproduces(geo, problem):
    g = Grid(19, 14)
    start = rank_projection(geo, g)
    a, ra, _ = anneal(problem, g, start, seed=5, iterations=3000, t0=0.02)
    b, rb, _ = anneal(problem, g, start, seed=5, iterations=3000, t0=0.02)
    assert a.cells == b.cells and ra["combined"] == rb["combined"]


def test_compact_reference():
    assert compact_mean_distance(1) == 1.0
    assert compact_mean_distance(2) == pytest.approx(1.0)
    assert compact_mean_distance(4) == pytest.approx((4 * 1 + 2 * np.sqrt(2)) / 6)  # 2x2 square
    assert compact_mean_distance(9) < compact_mean_distance(10) < compact_mean_distance(20)


def test_whitespace_term():
    ids = [f"{a}{b}" for a in "ABCDE" for b in "ABCDE"][:24]
    cells = {cid: (k % 5, k // 5) for k, cid in enumerate(ids)}
    lay = Layout(5, 5, cells, {(4, 4)})
    from cldrmap.scoring import whitespace_penalty
    v, d = whitespace_penalty(lay)
    assert v == 0.0  # corner blank, 2 occupied neighbours
    cells = dict(cells)
    cells["EE"] = (4, 4)
    del cells["BB"]  # (1,1) becomes an enclosed hole
    lay = Layout(5, 5, cells, {(1, 1)})
    v, d = whitespace_penalty(lay)
    assert v == 1.0 and d["enclosed_holes"] == 1
