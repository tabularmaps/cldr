"""Geographic inputs: representative points, adjacency, regions.

Distances are great-circle (haversine) on a sphere of radius 6371 km, so the
antimeridian needs no special handling for distance. Longitude *order*
(east/west) does need a convention: the board is Atlantic-centred like the
predecessor ``8bit``, but Polynesia straddles 180°. ``unwrap_lon`` therefore
moves longitudes west of ``LON_CUT`` (default -125°) by +360 so that the
Pacific islands east of 180° sort after New Zealand and Fiji instead of
before Alaska and the Americas. The cut is a documented parameter.
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import DATA
from .mother_set import load_regions

EARTH_RADIUS_KM = 6371.0
LON_CUT = -125.0


def unwrap_lon(lon: float, cut: float = LON_CUT) -> float:
    """Map longitude into (cut, cut + 360]."""
    return lon + 360.0 if lon <= cut else lon


def haversine_km(lat1, lon1, lat2, lon2):
    """Vectorised great-circle distance in km (inputs in degrees)."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = p2 - p1
    dlmb = np.radians(lon2) - np.radians(lon1)
    h = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.clip(h, 0.0, 1.0)))


@dataclass
class GeoInputs:
    ids: list[str]
    index: dict[str, int]
    lat: np.ndarray
    lon: np.ndarray
    lon_unwrapped: np.ndarray
    dist_km: np.ndarray            # (n, n) great-circle distances
    adjacency: list[tuple[int, int]]
    subregion: list[str | None]     # CLDR/M49 subregion code or None (QO members)
    continent: list[str | None]
    names: list[str]
    points_meta: list[dict] = field(default_factory=list)
    adjacency_meta: list[dict] = field(default_factory=list)

    @property
    def n(self) -> int:
        return len(self.ids)

    def knn(self, k: int) -> np.ndarray:
        """Indices of the k nearest identifiers (by great-circle distance)."""
        d = self.dist_km.copy()
        np.fill_diagonal(d, np.inf)
        return np.argsort(d, axis=1, kind="stable")[:, :k]

    def adjacency_set(self) -> set[tuple[int, int]]:
        return {(min(a, b), max(a, b)) for a, b in self.adjacency}


def load_geo(ids: list[str] | None = None, geo_dir: Path | None = None, lon_cut: float = LON_CUT) -> GeoInputs:
    geo_dir = geo_dir or DATA / "geo"
    regions = load_regions()
    if ids is None:
        ids = [r["id"] for r in regions]
    by_id = {r["id"]: r for r in regions}
    unknown = [i for i in ids if i not in by_id]
    if unknown:
        raise ValueError(f"identifiers not in the mother set: {unknown}")
    index = {c: i for i, c in enumerate(ids)}

    pts: dict[str, dict] = {}
    with (geo_dir / "points.csv").open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            pts[row["id"]] = row
    missing = [i for i in ids if i not in pts]
    if missing:
        raise ValueError(f"no representative point for {missing}")
    lat = np.array([float(pts[i]["lat"]) for i in ids])
    lon = np.array([float(pts[i]["lon"]) for i in ids])
    lon_u = np.array([unwrap_lon(v, lon_cut) for v in lon])
    dist = haversine_km(lat[:, None], lon[:, None], lat[None, :], lon[None, :])
    np.fill_diagonal(dist, 0.0)

    adjacency: list[tuple[int, int]] = []
    adj_meta = []
    with (geo_dir / "adjacency.csv").open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            a, b = row["a"], row["b"]
            if a in index and b in index:
                adjacency.append((index[a], index[b]))
                adj_meta.append(row)
    return GeoInputs(
        ids=list(ids),
        index=index,
        lat=lat,
        lon=lon,
        lon_unwrapped=lon_u,
        dist_km=dist,
        adjacency=adjacency,
        subregion=[None if by_id[i]["subregion"] == "QO" else by_id[i]["subregion"] for i in ids],
        continent=[by_id[i]["continent"] for i in ids],
        names=[by_id[i]["name_en"] for i in ids],
        points_meta=[pts[i] for i in ids],
        adjacency_meta=adj_meta,
    )
