#!/usr/bin/env python3
"""Regenerate ``data/regions.json`` from the pinned CLDR release.

Inputs (all pinned by ``data/profile.json``):

- ``data/cldr/<ver>/region.xml``   committed, checksum-verified (mother set)
- ``common/main/en.xml``            English display names (``--cldr-dir``)
- ``common/supplemental/supplementalData.xml``  territoryContainment (M49)

The last two are read from an unpacked ``cldr-common-<ver>.zip`` given by
``--cldr-dir``. Their checksums are recorded in the manifest. When
``--cldr-dir`` is omitted the script only re-verifies the mother set against
the committed manifest (offline mode used by CI).

Usage:
  uv run scripts/extract_cldr_regions.py --cldr-dir /path/to/cldr-common-48.2
  uv run scripts/extract_cldr_regions.py --check
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cldrmap import DATA  # noqa: E402
from cldrmap.mother_set import Profile, extract, parse_validity  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_names(en_xml: Path) -> dict[str, str]:
    root = ET.parse(en_xml).getroot()
    return {t.get("type"): t.text for t in root.iter("territory") if t.get("alt") is None}


def read_groupings(supp_xml: Path) -> dict[str, set[str]]:
    """Return {group: members} for grouping="true" groups (EU, EZ, UN, ...)."""
    root = ET.parse(supp_xml).getroot()
    out: dict[str, set[str]] = {}
    for g in root.find("territoryContainment").findall("group"):
        if g.get("grouping") == "true" and not g.get("status"):
            out.setdefault(g.get("type"), set()).update(g.get("contains").split())
    return out


def read_containment(supp_xml: Path) -> tuple[dict[str, str], dict[str, list[str]]]:
    """Return (parent_of, contains) for regular (non-grouping, non-deprecated) groups."""
    root = ET.parse(supp_xml).getroot()
    parent: dict[str, str] = {}
    contains: dict[str, list[str]] = {}
    for g in root.find("territoryContainment").findall("group"):
        if g.get("status") or g.get("grouping") == "true":
            continue
        members = g.get("contains").split()
        contains[g.get("type")] = members
        for m in members:
            if m in parent:
                raise SystemExit(f"{m} has two regular parents: {parent[m]} and {g.get('type')}")
            parent[m] = g.get("type")
    return parent, contains


def m49_path(code: str, parent: dict[str, str]) -> list[str]:
    path = []
    while code in parent:
        code = parent[code]
        path.append(code)
    return path  # e.g. ['154', '150', '001']


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cldr-dir", type=Path, help="unpacked cldr-common-<ver> directory")
    ap.add_argument("--check", action="store_true", help="verify the committed manifest only")
    ap.add_argument("--out", type=Path, default=DATA / "regions.json")
    args = ap.parse_args()

    profile = Profile.load()
    ids = extract(profile)
    by_status = parse_validity(profile.source_path.read_text("utf-8"))
    status_counts = {k: len(v) for k, v in by_status.items()}

    if args.check or not args.cldr_dir:
        committed = json.loads(args.out.read_text("utf-8"))
        got = [r["id"] for r in committed["regions"]]
        if got != ids:
            print("NG data/regions.json does not match the pinned CLDR source", file=sys.stderr)
            print("  missing:", sorted(set(ids) - set(got)), file=sys.stderr)
            print("  extra:  ", sorted(set(got) - set(ids)), file=sys.stderr)
            return 1
        print(f"OK {len(ids)} identifiers, profile {profile.name}, statuses {status_counts}")
        return 0

    en_xml = args.cldr_dir / "common/main/en.xml"
    supp_xml = args.cldr_dir / "common/supplemental/supplementalData.xml"
    src_region = args.cldr_dir / "common/validity/region.xml"
    if sha256(src_region) != profile.source_sha256:
        print(f"NG {src_region} does not match the profile checksum", file=sys.stderr)
        return 1
    names = read_names(en_xml)
    parent, contains = read_containment(supp_xml)
    groupings = read_groupings(supp_xml)
    macro_names = {k: names.get(k, k) for k in contains}

    regions = []
    for code in ids:
        path = m49_path(code, parent)
        regions.append(
            {
                "id": code,
                "name_en": names[code],
                "subregion": path[0] if path else None,
                "subregion_name": macro_names.get(path[0]) if path else None,
                "continent": path[-2] if len(path) >= 2 else None,
                "continent_name": macro_names.get(path[-2]) if len(path) >= 2 else None,
                "containment_path": path,
                "un_member": code in groupings.get("UN", set()),
            }
        )
    manifest = {
        "profile": profile.name,
        "cldr_version": profile.cldr_version,
        "generated": dt.date.today().isoformat(),
        "count": len(regions),
        "status_counts": status_counts,
        "sources": {
            "region.xml": {"path": "common/validity/region.xml", "sha256": profile.source_sha256},
            "en.xml": {"path": "common/main/en.xml", "sha256": sha256(en_xml)},
            "supplementalData.xml": {"path": "common/supplemental/supplementalData.xml", "sha256": sha256(supp_xml)},
        },
        "notes": [
            "name_en is the CLDR English display name (alt-less form) and is informational only.",
            "subregion/continent come from CLDR territoryContainment (UN M49 based); "
            "groupings (EU, EZ, UN, 003, 202, 419) and deprecated groups are ignored.",
            "QO (Outlying Oceania) is CLDR's container for AC, AQ, CP, DG and TA; it is "
            "kept verbatim and treated as unclassified for regional-continuity scoring.",
            "un_member reproduces membership of CLDR's UN grouping (territoryContainment type='UN'); "
            "it is informational, used only for optional preview filtering, and plays no role in the layout.",
        ],
        "regions": regions,
    }
    args.out.write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", "utf-8")
    print(f"wrote {args.out} with {len(regions)} identifiers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
