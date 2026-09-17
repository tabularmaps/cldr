"""Extract the mother set from a pinned CLDR ``common/validity/region.xml``.

The rule is deliberately small and mechanical:

1. take the ``<id type="region" idStatus="regular">`` element;
2. expand CLDR compact ranges (``AC~G`` means AC, AD, AE, AF, AG: the last
   character of the left token runs up to the right token);
3. keep tokens matching ``^[A-Z]{2}$``;
4. sort and deduplicate.

Nothing in this module knows about ISO 3166, geography, or the board.
"""

from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from . import DATA

TWO_ALPHA = re.compile(r"^[A-Z]{2}$")
RANGE = re.compile(r"^([A-Z0-9]+)~([A-Z0-9]+)$")


def expand_token(token: str) -> list[str]:
    """Expand one CLDR validity token.

    ``AC~G`` -> ``['AC', 'AD', 'AE', 'AF', 'AG']``;
    ``001~3`` -> ``['001', '002', '003']``; plain tokens pass through.
    """
    m = RANGE.match(token)
    if not m:
        return [token]
    left, right = m.groups()
    prefix, start = left[: -len(right)], left[-len(right):]
    if len(start) != len(right):
        raise ValueError(f"malformed CLDR range {token!r}")
    if start.isdigit() and right.isdigit():
        width = len(start)
        return [prefix + str(n).zfill(width) for n in range(int(start), int(right) + 1)]
    if len(start) == 1 and start.isalpha() and right.isalpha():
        return [prefix + chr(c) for c in range(ord(start), ord(right) + 1)]
    raise ValueError(f"unsupported CLDR range {token!r}")


def parse_validity(xml_text: str) -> dict[str, list[str]]:
    """Return ``{idStatus: [expanded identifiers...]}`` for type=region."""
    root = ET.fromstring(xml_text)
    out: dict[str, list[str]] = {}
    for el in root.iter("id"):
        if el.get("type") != "region":
            continue
        ids: list[str] = []
        for tok in (el.text or "").split():
            ids.extend(expand_token(tok))
        out.setdefault(el.get("idStatus", ""), []).extend(ids)
    return out


def select_regular_two_alpha(by_status: dict[str, list[str]]) -> list[str]:
    ids = [i for i in by_status.get("regular", []) if TWO_ALPHA.match(i)]
    return sorted(set(ids))


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class Profile:
    name: str
    cldr_version: str
    source_path: Path
    source_sha256: str
    expected_count: int
    raw: dict

    @classmethod
    def load(cls, path: Path | None = None) -> "Profile":
        path = path or DATA / "profile.json"
        raw = json.loads(path.read_text("utf-8"))
        return cls(
            name=raw["profile"],
            cldr_version=raw["cldr"]["version"],
            source_path=DATA / "cldr" / raw["cldr"]["version"] / "region.xml",
            source_sha256=raw["cldr"]["source_sha256"],
            expected_count=raw["extraction"]["expected_count"],
            raw=raw,
        )


class SourceMismatch(RuntimeError):
    """Raised when the committed CLDR input does not match the declared profile."""


def verify_source(profile: Profile) -> None:
    if not profile.source_path.exists():
        raise SourceMismatch(
            f"pinned CLDR source {profile.source_path} is missing; the profile "
            f"declares CLDR {profile.cldr_version}. Restore the file or update "
            "data/profile.json together with all regenerated artifacts."
        )
    actual = sha256_of(profile.source_path)
    if actual != profile.source_sha256:
        raise SourceMismatch(
            f"{profile.source_path} has sha256 {actual}, but data/profile.json "
            f"declares {profile.source_sha256} for CLDR {profile.cldr_version}. "
            "A different CLDR input is in use. Updating CLDR is an explicit "
            "maintenance event: update the profile, regenerate data/regions.json, "
            "re-run the grid comparison, and document the diff (see CLAUDE.md)."
        )


def extract(profile: Profile | None = None) -> list[str]:
    """Verify the pinned source and return the sorted mother set."""
    profile = profile or Profile.load()
    verify_source(profile)
    by_status = parse_validity(profile.source_path.read_text("utf-8"))
    ids = select_regular_two_alpha(by_status)
    if len(ids) != profile.expected_count:
        raise SourceMismatch(
            f"extracted {len(ids)} regular two-letter identifiers from CLDR "
            f"{profile.cldr_version}, but the profile expects {profile.expected_count}."
        )
    return ids


def load_regions(path: Path | None = None) -> list[dict]:
    """Load the committed manifest ``data/regions.json`` (list of records)."""
    path = path or DATA / "regions.json"
    return json.loads(path.read_text("utf-8"))["regions"]


def load_ids(path: Path | None = None) -> list[str]:
    return [r["id"] for r in load_regions(path)]
