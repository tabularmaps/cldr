"""Documentation consistency: declared counts, dimensions, profile and CLDR
version must agree across metadata.json, the layout, board.csv, README.md,
OPTIMIZATION.md and CHANGELOG.md."""

import json
import re

import pytest

from cldrmap import LAYOUTS, ROOT
from cldrmap.board import Layout


@pytest.fixture(scope="module")
def meta():
    p = ROOT / "metadata.json"
    if not p.exists():
        pytest.fail("metadata.json is missing; the selected board has not been committed")
    return json.loads(p.read_text("utf-8"))


def test_metadata_matches_layout_and_csv(meta, profile, ids):
    lay = Layout.load(LAYOUTS / meta["layout"])
    assert (meta["width"], meta["height"]) == (lay.width, lay.height)
    assert meta["identifier_count"] == len(lay.cells) == len(ids)
    assert meta["structural_space_count"] == len(lay.blanks) == lay.width * lay.height - len(ids)
    assert meta["profile"] == profile.name == lay.profile
    assert meta["cldr_version"] == profile.cldr_version == lay.cldr_version
    csv_lay = Layout.from_board_csv(ROOT / "board.csv")
    assert csv_lay.rows() == lay.rows()
    assert lay.validate(ids, profile) == []


def test_readme_states_the_facts(meta):
    text = (ROOT / "README.md").read_text("utf-8")
    assert f"CLDR {meta['cldr_version']}" in text
    assert str(meta["identifier_count"]) in text
    assert f"{meta['width']} × {meta['height']}" in text or f"{meta['width']}x{meta['height']}" in text or f"{meta['width']} by {meta['height']}" in text
    for phrase in ("not the same thing as a sovereign state", "does not settle", "approximate", "intentional", "not necessarily a global optimum", "does not represent"):
        assert phrase in text, phrase


def test_optimization_report_matches_layout(meta):
    lay = Layout.load(LAYOUTS / meta["layout"])
    rec = lay.generator["score"]
    text = (ROOT / "OPTIMIZATION.md").read_text("utf-8")
    assert f"{rec['combined']:.3f}" in text, "OPTIMIZATION.md must quote the selected layout's combined score"
    assert f"seed {lay.generator['seed']}" in text or f"seed = {lay.generator['seed']}" in text
    for k, w in rec["weights"].items():
        assert re.search(rf"\b{k}\b.*\b{w:g}\b", text), f"weight of {k} ({w}) not documented"


def test_changelog_mentions_release(meta):
    text = (ROOT / "CHANGELOG.md").read_text("utf-8")
    assert meta["cldr_version"] in text and str(meta["identifier_count"]) in text
