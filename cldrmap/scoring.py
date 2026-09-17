"""Deterministic objective components for a tabular map.

Every component is a non-negative number where lower is better, computed
from (a) the geographic inputs and (b) the cell of each identifier. The
combined score is a weighted sum. Weights are a normative choice and are
recorded with every report; see OPTIMIZATION.md for the rationale.

Components
----------
neighborhood     mean grid (Euclidean, cells) distance from each identifier
                 to its K=6 nearest geographic neighbours (great-circle).
global           1 - cov(sqrt(geo distance), grid distance) / reference
                 scale: a distance-correlation term that keeps the overall
                 world shape, compressed with sqrt so intercontinental
                 distances do not dominate.
adjacency        mean gap between land-border neighbours: 0 if orthogonally
                 adjacent, 0.5 if only diagonally adjacent, else the
                 Chebyshev distance.
direction        mean reversal, in cells, over eligible east-west and
                 north-south relations (same continent, or within 12 nearest
                 neighbours; longitude gap >= 12 deg or latitude gap >= 8
                 deg): 0 when the western/northern identifier is strictly
                 west/north on the board, 1 when in the same column/row,
                 k+1 when k cells reversed. The number of reversed
                 relations is reported as a diagnostic.
region           mean intra-subregion grid distance relative to the most
                 compact arrangement of the same number of cells, minus 1,
                 averaged over CLDR/M49 subregions (QO members excluded).
false_adjacency  count (per identifier) of orthogonally adjacent cell pairs
                 (0.5 for diagonal) whose identifiers are more than 2000 km
                 apart, share no land border, and are not within each
                 other's 12 nearest neighbours.
whitespace       share of blank cells that are enclosed holes: 1.0 when all
                 four orthogonal neighbours are occupied, 0.25 when three.
legacy           reported, weight 0 by default: fraction of identifiers whose
                 cell differs from the aligned 8bit board, and mean Manhattan
                 displacement.

All pairwise components are expressed as sums of F[i, j] * D[cell_i, cell_j]
so that a swap can be evaluated incrementally; ``score()`` recomputes from
scratch and is the reference implementation used by tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .board import Layout
from .geo import GeoInputs

DEFAULT_WEIGHTS = {
    "neighborhood": 1.0,
    "global": 0.5,
    "adjacency": 2.0,
    "direction": 2.0,
    "region": 1.0,
    "false_adjacency": 1.0,
    "whitespace": 0.5,
    "legacy": 0.0,
}

PARAMS = {
    "knn": 6,
    "direction_knn": 12,
    "lon_gap_deg": 12.0,
    "lat_gap_deg": 8.0,
    "far_km": 2000.0,
}

TERMS = ("sym", "adjacency", "false_adjacency", "east_west", "north_south")


def compact_mean_distance(m: int) -> float:
    """Mean pairwise Euclidean distance of a compact blob of m lattice cells.

    The blob is the m lattice points nearest to one of four centres
    ((0,0), (0.5,0), (0,0.5), (0.5,0.5)); the smallest mean distance is
    returned. This is a documented reference, not a proven optimum."""
    if m < 2:
        return 1.0
    r = int(np.ceil(np.sqrt(m))) + 2
    xs, ys = np.meshgrid(np.arange(-r, r + 1), np.arange(-r, r + 1))
    all_pts = np.stack([xs.ravel(), ys.ravel()], 1).astype(float)
    best = None
    for cx, cy in ((0.0, 0.0), (0.5, 0.0), (0.0, 0.5), (0.5, 0.5)):
        d2 = (all_pts[:, 0] - cx) ** 2 + (all_pts[:, 1] - cy) ** 2
        order = np.lexsort((all_pts[:, 0], all_pts[:, 1], np.round(d2, 9)))
        pts = all_pts[order[:m]]
        d = np.sqrt(((pts[:, None, :] - pts[None, :, :]) ** 2).sum(-1))
        v = float(d.sum() / (m * (m - 1)))
        best = v if best is None else min(best, v)
    return best


@dataclass
class Grid:
    width: int
    height: int

    @property
    def cells(self) -> int:
        return self.width * self.height

    def xy(self) -> tuple[np.ndarray, np.ndarray]:
        idx = np.arange(self.cells)
        return idx % self.width, idx // self.width

    def index(self, x: int, y: int) -> int:
        return y * self.width + x

    def distance_tables(self) -> np.ndarray:
        """Stack of (T, C, C) cell-pair tables in the order of ``TERMS``."""
        x, y = self.xy()
        dx = x[:, None] - x[None, :]
        dy = y[:, None] - y[None, :]
        euc = np.sqrt(dx ** 2 + dy ** 2)
        cheb = np.maximum(np.abs(dx), np.abs(dy))
        orth = (np.abs(dx) + np.abs(dy) == 1)
        diag = (cheb == 1) & ~orth
        adj = np.where(orth, 0.0, np.where(diag, 0.5, cheb.astype(float)))
        fa = np.where(orth, 1.0, np.where(diag, 0.5, 0.0))
        ew = np.maximum(0.0, x[:, None] - x[None, :] + 1.0)   # cells by which a fails to be west of b
        ns = np.maximum(0.0, y[:, None] - y[None, :] + 1.0)   # cells by which a fails to be north of b
        return np.stack([euc, adj, fa, ew, ns]).astype(float)


@dataclass
class Problem:
    """Geographic inputs turned into flow matrices for one weight set."""
    geo: GeoInputs
    weights: dict
    params: dict
    F: np.ndarray                    # (T, n, n) weighted flows (weights applied)
    F_raw: dict                      # unweighted component flows for reporting
    region_ideal: dict
    sigma_ref: float = 1.0
    legacy: dict | None = None       # id -> (x, y) of the aligned 8bit board

    @property
    def n(self) -> int:
        return self.geo.n


def build_problem(geo: GeoInputs, grid: Grid, weights: dict | None = None, params: dict | None = None, legacy: Layout | None = None) -> Problem:
    weights = {**DEFAULT_WEIGHTS, **(weights or {})}
    params = {**PARAMS, **(params or {})}
    n = geo.n
    off = ~np.eye(n, dtype=bool)

    # neighborhood ---------------------------------------------------
    k = params["knn"]
    nn = geo.knn(k)
    A = np.zeros((n, n))
    for i in range(n):
        A[i, nn[i]] = 1.0
    F_nb = (A + A.T) / 2 / (n * k)

    # global distance correlation -----------------------------------
    x, y = grid.xy()
    dg_all = np.sqrt((x[:, None] - x[None, :]) ** 2 + (y[:, None] - y[None, :]) ** 2)
    sigma_ref = float(dg_all[np.triu_indices(grid.cells, 1)].std())
    dt = np.sqrt(geo.dist_km)
    vals = dt[off]
    mu, sd = vals.mean(), vals.std()
    npairs = n * (n - 1)
    F_gl = np.where(off, -(dt - mu) / (npairs * sd * sigma_ref), 0.0)  # sum(F*dg) = -cov/(sd*sigma_ref)

    # adjacency ------------------------------------------------------
    adj = geo.adjacency_set()
    F_adj = np.zeros((n, n))
    for a, b in adj:
        F_adj[a, b] = F_adj[b, a] = 0.5 / max(len(adj), 1)

    # direction ------------------------------------------------------
    kd = params["direction_knn"]
    nnd = geo.knn(kd)
    elig = np.zeros((n, n), dtype=bool)
    for i in range(n):
        elig[i, nnd[i]] = True
    elig |= elig.T
    elig_knn = elig.copy()   # mutual 12-nearest neighbourhood, reused by false_adjacency
    cont = np.array(geo.continent, dtype=object)
    same_cont = (cont[:, None] == cont[None, :]) & (cont[:, None] != None)  # noqa: E711
    elig |= same_cont
    elig &= off
    dlon = geo.lon_unwrapped[None, :] - geo.lon_unwrapped[:, None]   # >0 when j east of i
    dlat = geo.lat[:, None] - geo.lat[None, :]                       # >0 when i north of j
    west_of = elig & (dlon >= params["lon_gap_deg"])                  # i west of j
    north_of = elig & (dlat >= params["lat_gap_deg"])                 # i north of j
    nrel = int(west_of.sum() + north_of.sum())
    F_ew = west_of.astype(float) / nrel     # penalised when x_i >= x_j
    F_ns = north_of.astype(float) / nrel    # penalised when y_i >= y_j

    # region cohesion ------------------------------------------------
    F_reg = np.zeros((n, n))
    regions: dict[str, list[int]] = {}
    for i, r in enumerate(geo.subregion):
        if r is not None:
            regions.setdefault(r, []).append(i)
    region_ideal = {r: compact_mean_distance(len(m)) for r, m in regions.items()}
    R = len(regions)
    for r, members in regions.items():
        m = len(members)
        if m < 2:
            continue
        w = 1.0 / (R * m * (m - 1) * region_ideal[r])
        idx = np.array(members)
        F_reg[np.ix_(idx, idx)] = w
        F_reg[idx, idx] = 0.0

    # false adjacency ------------------------------------------------
    far = (geo.dist_km > params["far_km"]) & off & ~elig_knn
    for a, b in adj:
        far[a, b] = far[b, a] = False
    F_fa = far.astype(float) / (2 * n)     # ordered pairs -> per identifier

    F_sym = weights["neighborhood"] * F_nb + weights["global"] * F_gl + weights["region"] * F_reg
    F = np.stack([F_sym, weights["adjacency"] * F_adj, weights["false_adjacency"] * F_fa, weights["direction"] * F_ew, weights["direction"] * F_ns])
    raw = {"neighborhood": F_nb, "global": F_gl, "adjacency": F_adj, "region": F_reg, "false_adjacency": F_fa, "east_west": F_ew, "north_south": F_ns, "eligible_relations": nrel}
    legacy_cells = None
    if legacy is not None:
        legacy_cells = align_legacy(legacy, grid, geo)
    return Problem(geo, weights, params, F, raw, region_ideal, sigma_ref, legacy_cells)


# ----------------------------------------------------------------------
# reference (from-scratch) scoring
# ----------------------------------------------------------------------

def positions(layout: Layout, geo: GeoInputs) -> np.ndarray:
    pos = np.empty(geo.n, dtype=int)
    for i, cid in enumerate(geo.ids):
        if cid not in layout.cells:
            raise KeyError(f"{cid} is not placed")
        x, y = layout.cells[cid]
        pos[i] = y * layout.width + x
    return pos


def whitespace_penalty(layout: Layout) -> tuple[float, dict]:
    occ = {c for c in layout.cells.values()}
    blanks = sorted(layout.blanks)
    if not blanks:
        return 0.0, {"blank_cells": 0, "enclosed_holes": 0, "three_sided": 0, "blank_components": 0}
    total = 0.0
    holes = three = 0
    for (x, y) in blanks:
        c = sum((x + dx, y + dy) in occ for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        if c == 4:
            total += 1.0
            holes += 1
        elif c == 3:
            total += 0.25
            three += 1
    return total / len(blanks), {"blank_cells": len(blanks), "enclosed_holes": holes, "three_sided": three, "blank_components": components(set(blanks), diagonal=False)}


def components(cells: set[tuple[int, int]], diagonal: bool = True) -> int:
    steps = [(1, 0), (-1, 0), (0, 1), (0, -1)] + ([(1, 1), (1, -1), (-1, 1), (-1, -1)] if diagonal else [])
    seen: set = set()
    count = 0
    for start in cells:
        if start in seen:
            continue
        count += 1
        stack = [start]
        seen.add(start)
        while stack:
            x, y = stack.pop()
            for dx, dy in steps:
                nb = (x + dx, y + dy)
                if nb in cells and nb not in seen:
                    seen.add(nb)
                    stack.append(nb)
    return count


def align_legacy(legacy: Layout, grid: Grid, geo: GeoInputs) -> dict[str, tuple[int, int]]:
    """Cells of the legacy board for identifiers in the mother set. The
    integer translation that best aligns it with a layout is found at score
    time by ``legacy_metrics``."""
    return {cid: legacy.cells[cid] for cid in geo.ids if cid in legacy.cells}


def legacy_metrics(layout: Layout, legacy_cells: dict[str, tuple[int, int]] | None) -> dict:
    if not legacy_cells:
        return {"compared": 0}
    shared = [cid for cid in legacy_cells if cid in layout.cells]
    best = None
    for ox in range(-layout.width, layout.width + 1):
        for oy in range(-layout.height, layout.height + 1):
            cost = 0
            for cid in shared:
                lx, ly = legacy_cells[cid]
                x, y = layout.cells[cid]
                cost += abs(lx + ox - x) + abs(ly + oy - y)
            if best is None or cost < best[0]:
                best = (cost, ox, oy)
    cost, ox, oy = best
    moved = sum(1 for cid in shared if (legacy_cells[cid][0] + ox, legacy_cells[cid][1] + oy) != layout.cells[cid])
    euc = float(np.mean([np.hypot(legacy_cells[c][0] + ox - layout.cells[c][0], legacy_cells[c][1] + oy - layout.cells[c][1]) for c in shared]))
    return {"compared": len(shared), "offset": [ox, oy], "moved": moved, "moved_fraction": moved / len(shared), "mean_manhattan": cost / len(shared), "mean_euclidean": euc}


def score(layout: Layout, problem: Problem, tables: np.ndarray | None = None) -> dict:
    """Reference scorer. Returns components, diagnostics, and the combined score."""
    grid = Grid(layout.width, layout.height)
    tables = tables if tables is not None else grid.distance_tables()
    pos = positions(layout, problem.geo)
    D = tables[:, pos][:, :, pos]          # (T, n, n)
    raw = problem.F_raw
    comp = {
        "neighborhood": float((raw["neighborhood"] * D[0]).sum()),
        "global": 1.0 + float((raw["global"] * D[0]).sum()),
        "adjacency": float((raw["adjacency"] * D[1]).sum()),
        "direction": float((raw["east_west"] * D[3]).sum() + (raw["north_south"] * D[4]).sum()),
        "region": float((raw["region"] * D[0]).sum()) - 1.0,
        "false_adjacency": float((raw["false_adjacency"] * D[2]).sum()),
    }
    ws, ws_diag = whitespace_penalty(layout)
    comp["whitespace"] = ws
    leg = legacy_metrics(layout, problem.legacy)
    comp["legacy"] = float(leg.get("moved_fraction", 0.0))
    combined = sum(problem.weights[k] * v for k, v in comp.items())

    # diagnostics ------------------------------------------------------
    geo = problem.geo
    off = ~np.eye(geo.n, dtype=bool)
    dg = D[0][off]
    dgeo = np.sqrt(geo.dist_km)[off]
    pearson = float(np.corrcoef(dgeo, dg)[0, 1])
    rg = np.argsort(np.argsort(dg))
    rgeo = np.argsort(np.argsort(dgeo))
    spearman = float(np.corrcoef(rgeo, rg)[0, 1])
    region_cells: dict[str, set] = {}
    for i, r in enumerate(geo.subregion):
        if r is not None:
            region_cells.setdefault(r, set()).add(layout.cells[geo.ids[i]])
    region_components = {r: components(c) for r, c in region_cells.items()}
    adj = geo.adjacency_set()
    kept = sum(1 for a, b in adj if D[1][a, b] == 0.0)
    within1 = sum(1 for a, b in adj if D[1][a, b] <= 0.5)
    viol = int(((raw["east_west"] > 0) & (D[3] > 0)).sum() + ((raw["north_south"] > 0) & (D[4] > 0)).sum())
    diag = {
        "pearson_sqrt_geo_vs_grid": pearson,
        "spearman_geo_vs_grid": spearman,
        "adjacency_pairs": len(adj),
        "adjacency_orthogonal": kept,
        "adjacency_within_1": within1,
        "direction_relations": int(raw["eligible_relations"]),
        "direction_violations": viol,
        "region_components": region_components,
        "region_components_excess": int(sum(v - 1 for v in region_components.values())),
        "false_adjacent_pairs": float(comp["false_adjacency"] * geo.n),
        **ws_diag,
        "legacy": leg,
    }
    return {"grid": [layout.width, layout.height], "weights": dict(problem.weights), "params": dict(problem.params), "components": comp, "combined": combined, "diagnostics": diag}
