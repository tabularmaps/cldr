import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cldrmap.board import Layout  # noqa: E402
from cldrmap.geo import load_geo  # noqa: E402
from cldrmap.mother_set import Profile, extract  # noqa: E402


@pytest.fixture(scope="session")
def profile():
    return Profile.load()


@pytest.fixture(scope="session")
def ids(profile):
    return extract(profile)


@pytest.fixture(scope="session")
def geo(ids):
    return load_geo(ids)


@pytest.fixture(scope="session")
def legacy():
    return Layout.from_board_csv(ROOT / "data" / "legacy" / "8bit-board.csv")
