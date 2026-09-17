"""Board data contract.

A *layout* is a JSON document (``layouts/*.json``) with:

- ``profile``           mother-set profile name (must match data/profile.json)
- ``cldr_version``      pinned CLDR version
- ``grid``              ``[width, height]``
- ``placements``        ``[{"id": "JP", "x": 15, "y": 2, "w": 1, "h": 1}, ...]``
                        (``x`` column from the left, ``y`` row from the top,
                        origin top-left; ``w``/``h`` are always 1 here and
                        exist for compatibility with sibling projects)
- ``structural_spaces`` ``[[x, y], ...]`` intentionally blank cells
- ``board``             derived ``height`` rows of ``width`` strings
                        (uppercase identifier or ``""``)
- ``generator``         provenance: script, seed, budget, weights, metrics

Every cell of the grid is either exactly one placement or exactly one
structural space. A missing value, an unknown identifier, an omitted
mother-set member, and a blank cell are therefore four distinguishable
conditions, and ``validate`` reports each by name.

``board.csv`` is the compatibility view used by the tabularmaps family
(``tabularmaps/8bit``): a header row of column indices followed by
``height`` rows of lowercase identifiers, blank cells written as empty
fields.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from pathlib import Path

from .mother_set import Profile, load_ids


class BoardError(ValueError):
    pass


@dataclass
class Layout:
    width: int
    height: int
    cells: dict[str, tuple[int, int]]            # id -> (x, y)
    blanks: set[tuple[int, int]] = field(default_factory=set)
    profile: str = ""
    cldr_version: str = ""
    generator: dict = field(default_factory=dict)

    # ---- construction -------------------------------------------------
    @classmethod
    def from_dict(cls, d: dict) -> "Layout":
        w, h = d["grid"]
        cells = {p["id"]: (int(p["x"]), int(p["y"])) for p in d["placements"]}
        blanks = {(int(x), int(y)) for x, y in d.get("structural_spaces", [])}
        return cls(w, h, cells, blanks, d.get("profile", ""), d.get("cldr_version", ""), d.get("generator", {}))

    @classmethod
    def load(cls, path: Path) -> "Layout":
        return cls.from_dict(json.loads(Path(path).read_text("utf-8")))

    @classmethod
    def from_rows(cls, rows: list[list[str]], **kw) -> "Layout":
        """Build from a matrix of identifiers ('' or None = blank)."""
        h = len(rows)
        w = len(rows[0]) if rows else 0
        cells, blanks = {}, set()
        for y, row in enumerate(rows):
            if len(row) != w:
                raise BoardError(f"row {y} has {len(row)} cells, expected {w}")
            for x, v in enumerate(row):
                v = (v or "").strip().upper()
                if v:
                    if v in cells:
                        raise BoardError(f"{v} appears more than once")
                    cells[v] = (x, y)
                else:
                    blanks.add((x, y))
        return cls(w, h, cells, blanks, **kw)

    @classmethod
    def from_board_csv(cls, path: Path, **kw) -> "Layout":
        text = Path(path).read_text("utf-8")
        rows = list(csv.reader(io.StringIO(text)))
        rows = [r for r in rows if len(r) > 0]  # keep all-blank rows; drop only empty lines
        header = rows[0]
        if all(c.strip().isdigit() for c in header):
            rows = rows[1:]
        return cls.from_rows(rows, **kw)

    # ---- views -------------------------------------------------------
    def rows(self) -> list[list[str]]:
        grid = [["" for _ in range(self.width)] for _ in range(self.height)]
        for cid, (x, y) in self.cells.items():
            grid[y][x] = cid
        return grid

    def to_dict(self) -> dict:
        placements = [{"id": cid, "x": x, "y": y, "w": 1, "h": 1} for cid, (x, y) in sorted(self.cells.items(), key=lambda kv: (kv[1][1], kv[1][0]))]
        return {
            "profile": self.profile,
            "cldr_version": self.cldr_version,
            "grid": [self.width, self.height],
            "cell_shape": "square",
            "identifier_count": len(self.cells),
            "structural_space_count": len(self.blanks),
            "placements": placements,
            "structural_spaces": [list(c) for c in sorted(self.blanks, key=lambda c: (c[1], c[0]))],
            "board": self.rows(),
            "generator": self.generator,
        }

    def save(self, path: Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=1) + "\n", "utf-8")

    def board_csv(self) -> str:
        out = io.StringIO()
        w = csv.writer(out, lineterminator="\n")
        w.writerow([str(i) for i in range(self.width)])
        for row in self.rows():
            w.writerow([c.lower() for c in row])
        return out.getvalue()

    def ascii(self) -> str:
        return "\n".join(" ".join(c.lower() if c else ".." for c in row) for row in self.rows())

    def copy(self) -> "Layout":
        return Layout(self.width, self.height, dict(self.cells), set(self.blanks), self.profile, self.cldr_version, dict(self.generator))

    # ---- validation --------------------------------------------------
    def validate(self, ids: list[str] | None = None, profile: Profile | None = None, strict_profile: bool = True) -> list[str]:
        """Return a list of human-readable problems (empty = valid)."""
        errors: list[str] = []
        ids = ids if ids is not None else load_ids()
        idset = set(ids)
        if self.width <= 0 or self.height <= 0:
            return [f"grid {self.width}x{self.height} is not positive"]
        occupied: dict[tuple[int, int], str] = {}
        for cid, (x, y) in self.cells.items():
            if not (0 <= x < self.width and 0 <= y < self.height):
                errors.append(f"{cid} at ({x},{y}) is outside the {self.width}x{self.height} grid")
            if (x, y) in occupied:
                errors.append(f"cell ({x},{y}) holds both {occupied[(x, y)]} and {cid}")
            occupied[(x, y)] = cid
            if cid not in idset:
                errors.append(f"unrecognized identifier {cid!r} (not in the {len(ids)}-member mother set)")
        for (x, y) in self.blanks:
            if not (0 <= x < self.width and 0 <= y < self.height):
                errors.append(f"structural space ({x},{y}) is outside the grid")
            if (x, y) in occupied:
                errors.append(f"cell ({x},{y}) is declared blank but holds {occupied[(x, y)]}")
        missing = sorted(idset - set(self.cells))
        if missing:
            errors.append(f"omitted mother-set members: {missing}")
        total = self.width * self.height
        in_grid = {c for c in occupied if 0 <= c[0] < self.width and 0 <= c[1] < self.height}
        covered = len(in_grid) + len({c for c in self.blanks if 0 <= c[0] < self.width and 0 <= c[1] < self.height} - in_grid)
        if covered != total:
            unaccounted = sorted({(x, y) for y in range(self.height) for x in range(self.width)} - set(occupied) - self.blanks)
            errors.append(f"{total - covered} cell(s) neither placed nor declared blank (missing values): {unaccounted[:10]}")
        if strict_profile:
            profile = profile or Profile.load()
            if self.profile and self.profile != profile.name:
                errors.append(f"layout profile {self.profile!r} != declared profile {profile.name!r}")
            if self.cldr_version and self.cldr_version != profile.cldr_version:
                errors.append(f"layout cldr_version {self.cldr_version!r} != declared {profile.cldr_version!r}")
        return errors
