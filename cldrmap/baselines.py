"""Baseline and initial layouts.

- ``alphabetical``      row-major by identifier
- ``region_bucket``     subregions in a fixed west-to-east, north-to-south
                        bucket order, members alphabetical, row-major
- ``projection``        geographic projection (unwrapped longitude, latitude)
                        assigned to cells by linear sum assignment
- ``rank_projection``   same with quantile-scaled coordinates
- ``legacy_extension``  the 8bit board with the seven identifiers it lacks
                        placed in its blank cells / an added row (naive)
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import linear_sum_assignment

from .board import Layout
from .geo import GeoInputs
from .scoring import Grid


def _from_order(ids: list[str], grid: Grid, profile: str, ver: str) -> Layout:
    cells = {cid: (k % grid.width, k // grid.width) for k, cid in enumerate(ids)}
    blanks = {(k % grid.width, k // grid.width) for k in range(len(ids), grid.cells)}
    return Layout(grid.width, grid.height, cells, blanks, profile, ver)


def alphabetical(geo: GeoInputs, grid: Grid, profile: str = "", ver: str = "") -> Layout:
    return _from_order(sorted(geo.ids), grid, profile, ver)


def region_bucket(geo: GeoInputs, grid: Grid, profile: str = "", ver: str = "") -> Layout:
    # order subregions by mean unwrapped longitude then latitude (north first)
    groups: dict[str, list[int]] = {}
    for i, r in enumerate(geo.subregion):
        groups.setdefault(r or "QO", []).append(i)
    order = sorted(groups, key=lambda r: (np.mean(geo.lon_unwrapped[groups[r]]), -np.mean(geo.lat[groups[r]])))
    ids = []
    for r in order:
        ids.extend(sorted(geo.ids[i] for i in groups[r]))
    return _from_order(ids, grid, profile, ver)


def _assign(points: np.ndarray, geo: GeoInputs, grid: Grid, profile: str, ver: str) -> Layout:
    x, y = grid.xy()
    cost = (points[:, 0:1] - x[None, :]) ** 2 + (points[:, 1:2] - y[None, :]) ** 2
    rows, cols = linear_sum_assignment(cost)
    cells = {geo.ids[i]: (int(x[c]), int(y[c])) for i, c in zip(rows, cols)}
    used = set(cells.values())
    blanks = {(int(x[c]), int(y[c])) for c in range(grid.cells) if (int(x[c]), int(y[c])) not in used}
    return Layout(grid.width, grid.height, cells, blanks, profile, ver)


def projection(geo: GeoInputs, grid: Grid, profile: str = "", ver: str = "", lat_clip: tuple[float, float] = (-60.0, 80.0)) -> Layout:
    lon = geo.lon_unwrapped
    lat = np.clip(geo.lat, *lat_clip)
    px = (lon - lon.min()) / (lon.max() - lon.min()) * (grid.width - 1)
    py = (lat.max() - lat) / (lat.max() - lat.min()) * (grid.height - 1)
    return _assign(np.stack([px, py], 1), geo, grid, profile, ver)


def rank_projection(geo: GeoInputs, grid: Grid, profile: str = "", ver: str = "") -> Layout:
    n = geo.n
    rx = np.argsort(np.argsort(geo.lon_unwrapped)) / (n - 1) * (grid.width - 1)
    ry = np.argsort(np.argsort(-geo.lat)) / (n - 1) * (grid.height - 1)
    return _assign(np.stack([rx, ry], 1), geo, grid, profile, ver)


def legacy_extension(legacy: Layout, geo: GeoInputs, profile: str = "", ver: str = "") -> Layout:
    """Naive extension: keep every 8bit cell; add missing identifiers into the
    predecessor's blank cells in row-major order, then into an extra bottom
    row if needed. Identifiers not in the mother set are dropped."""
    missing = [cid for cid in geo.ids if cid not in legacy.cells]
    cells = {cid: xy for cid, xy in legacy.cells.items() if cid in geo.index}
    width, height = legacy.width, legacy.height
    free = sorted(legacy.blanks, key=lambda c: (c[1], c[0]))
    for cid in missing:
        if free:
            cells[cid] = free.pop(0)
        else:
            height += 1
            free = [(x, height - 1) for x in range(width)]
            cells[cid] = free.pop(0)
    blanks = {(x, y) for y in range(height) for x in range(width)} - set(cells.values())
    return Layout(width, height, cells, blanks, profile, ver)
