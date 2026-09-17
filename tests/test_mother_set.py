import json
import re

import pytest

from cldrmap import DATA
from cldrmap.mother_set import (
    Profile,
    SourceMismatch,
    expand_token,
    extract,
    parse_validity,
    select_regular_two_alpha,
    sha256_of,
    verify_source,
)

EXPECTED_ADDITIONS = ["AC", "CP", "CQ", "DG", "EA", "IC", "TA", "XK"]


def test_pinned_checksum(profile):
    assert sha256_of(profile.source_path) == profile.source_sha256
    assert profile.cldr_version == "48.2"


def test_range_expansion():
    assert expand_token("AC~G") == ["AC", "AD", "AE", "AF", "AG"]
    assert expand_token("001~3") == ["001", "002", "003"]
    assert expand_token("XK") == ["XK"]
    assert expand_token("QM~N") == ["QM", "QN"]
    with pytest.raises(ValueError):
        expand_token("A~BC")


def test_status_selection(profile):
    by = parse_validity(profile.source_path.read_text("utf-8"))
    assert set(by) == {"regular", "special", "macroregion", "deprecated", "reserved", "private_use", "unknown"}
    ids = select_regular_two_alpha(by)
    assert all(re.fullmatch(r"[A-Z]{2}", i) for i in ids)
    assert len(ids) == len(set(ids)) == 257
    for status in ("special", "macroregion", "deprecated", "reserved", "private_use", "unknown"):
        assert not set(by[status]) & set(ids)
    assert "ZZ" not in ids and "EU" not in ids and "XA" not in ids and "AN" not in ids


def test_extract_matches_manifest(ids):
    manifest = json.loads((DATA / "regions.json").read_text("utf-8"))
    assert manifest["count"] == 257
    assert [r["id"] for r in manifest["regions"]] == ids
    assert manifest["cldr_version"] == "48.2"
    assert all(r["name_en"] for r in manifest["regions"])
    assert all(r["subregion"] for r in manifest["regions"])


def test_iso_relationship_is_reported_not_normative(ids):
    """257 = 249 ISO 3166-1 alpha-2 + 8 CLDR additions. ISO is a comparison,
    not the source of truth, so this test only checks the additions list."""
    additions = sorted(set(ids) - set(_iso_alpha2_reference(ids)))
    assert additions == EXPECTED_ADDITIONS
    assert len(ids) - len(additions) == 249


def _iso_alpha2_reference(ids):
    # the predecessor board holds all 249 ISO 3166-1 alpha-2 codes plus XK
    import csv
    from cldrmap import DATA as D

    rows = list(csv.reader((D / "legacy" / "8bit-board.csv").open(encoding="utf-8")))[1:]
    codes = {c.strip().upper() for r in rows for c in r if c.strip()}
    assert len(codes) == 250
    return codes - {"XK"}


def test_wrong_source_fails_clearly(tmp_path, profile):
    bad = tmp_path / "region.xml"
    bad.write_text(profile.source_path.read_text("utf-8").replace("XK", "XK XZ"), "utf-8")
    p = Profile(profile.name, profile.cldr_version, bad, profile.source_sha256, profile.expected_count, profile.raw)
    with pytest.raises(SourceMismatch, match="explicit maintenance event"):
        verify_source(p)
    with pytest.raises(SourceMismatch):
        extract(p)


def test_missing_source_fails_clearly(tmp_path, profile):
    p = Profile(profile.name, profile.cldr_version, tmp_path / "nope.xml", profile.source_sha256, profile.expected_count, profile.raw)
    with pytest.raises(SourceMismatch, match="missing"):
        extract(p)
