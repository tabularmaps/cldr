import json

import pytest

from cldrmap.board import BoardError, Layout


def make(ids, w, h):
    cells = {cid: (k % w, k // w) for k, cid in enumerate(ids)}
    blanks = {(k % w, k // w) for k in range(len(ids), w * h)}
    return Layout(w, h, cells, blanks, "cldr-48.2-regular-2alpha", "48.2")


def test_roundtrip_json_and_csv(ids, tmp_path):
    lay = make(ids, 19, 14)
    assert lay.validate(ids) == []
    p = tmp_path / "l.json"
    lay.save(p)
    doc = json.loads(p.read_text())
    assert doc["grid"] == [19, 14] and doc["identifier_count"] == 257 and doc["structural_space_count"] == 9
    assert len(doc["board"]) == 14 and all(len(r) == 19 for r in doc["board"])
    back = Layout.load(p)
    assert back.cells == lay.cells and back.blanks == lay.blanks
    csv_text = lay.board_csv()
    (tmp_path / "board.csv").write_text(csv_text)
    from_csv = Layout.from_board_csv(tmp_path / "board.csv")
    assert from_csv.rows() == lay.rows()
    assert csv_text.splitlines()[1].startswith("ac,ad,ae")


def test_distinguishes_failure_modes(ids):
    lay = make(ids, 19, 14)
    lay.cells.pop("JP")
    errs = lay.validate(ids)
    assert any("omitted mother-set members: ['JP']" in e for e in errs)
    assert any("missing values" in e for e in errs)
    lay = make(ids, 19, 14)
    lay.cells["ZZ"] = lay.blanks.pop()
    assert any("unrecognized identifier 'ZZ'" in e for e in lay.validate(ids))
    lay = make(ids, 19, 14)
    lay.cells["JP"] = lay.cells["KR"]
    assert any("holds both" in e for e in lay.validate(ids))
    lay = make(ids, 19, 14)
    lay.cells["JP"] = (19, 0)
    assert any("outside" in e for e in lay.validate(ids))
    lay = make(ids, 19, 14)
    lay.profile = "something-else"
    assert any("profile" in e for e in lay.validate(ids))


def test_duplicate_in_matrix_rejected():
    with pytest.raises(BoardError):
        Layout.from_rows([["JP", "JP"]])


def test_legacy_board_shape(legacy):
    assert (legacy.width, legacy.height) == (16, 16)
    assert len(legacy.cells) == 250 and len(legacy.blanks) == 6
