"""Simulated annealing over a fixed grid.

State: ``pos[i]`` = cell index of identifier i; ``occ[c]`` = identifier at
cell c or -1. A move relocates one identifier to another cell, swapping with
the identifier there if any. The energy is the combined score of
``scoring.build_problem`` plus the whitespace term; pairwise terms are
evaluated incrementally (O(n) per move) and the whitespace term locally.

Determinism: all randomness comes from ``numpy.random.default_rng(seed)``.
Every run records seed, iterations, temperatures, acceptance counts, and the
best energy, and the result is re-scored from scratch before being saved.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

import numpy as np

from .board import Layout
from .scoring import Grid, Problem, score

NEIGH4 = ((1, 0), (-1, 0), (0, 1), (0, -1))


@dataclass
class Annealer:
    problem: Problem
    grid: Grid
    layout: Layout
    allowed: dict[int, np.ndarray] | None = None   # item -> allowed cell indices (None = any)
    fixed_blanks: set[int] = field(default_factory=set)  # cells that must stay blank
    seed: int = 1

    def __post_init__(self):
        g, p = self.grid, self.problem
        self.tables = g.distance_tables()             # (T, C, C)
        self.F = p.F                                  # (T, n, n)
        self.FT = np.ascontiguousarray(p.F.transpose(0, 2, 1))
        self.n = p.n
        self.C = g.cells
        self.pos = np.empty(self.n, dtype=int)
        self.occ = np.full(self.C, -1, dtype=int)
        for i, cid in enumerate(p.geo.ids):
            x, y = self.layout.cells[cid]
            c = g.index(x, y)
            self.pos[i] = c
            self.occ[c] = i
        self.x, self.y = g.xy()
        self.w_ws = p.weights["whitespace"]
        self.nblank = self.C - self.n
        self.rng = np.random.default_rng(self.seed)
        self.targets = p.geo.knn(p.params["knn"])
        self.energy = self.full_energy()

    # ---- energies --------------------------------------------------
    def pair_energy(self) -> float:
        D = self.tables[:, self.pos][:, :, self.pos]
        return float((self.F * D).sum())

    def blank_penalty_at(self, c: int) -> float:
        if self.occ[c] != -1:
            return 0.0
        x, y = self.x[c], self.y[c]
        k = 0
        for dx, dy in NEIGH4:
            nx, ny = x + dx, y + dy
            if 0 <= nx < self.grid.width and 0 <= ny < self.grid.height and self.occ[ny * self.grid.width + nx] != -1:
                k += 1
        return 1.0 if k == 4 else 0.25 if k == 3 else 0.0

    def whitespace_energy(self) -> float:
        if self.nblank == 0:
            return 0.0
        return self.w_ws * sum(self.blank_penalty_at(c) for c in range(self.C) if self.occ[c] == -1) / self.nblank

    def full_energy(self) -> float:
        return self.pair_energy() + self.whitespace_energy()

    def _item_delta(self, i: int, a: int, a2: int, exclude: int | None) -> float:
        """Change in pairwise energy when item i moves from cell a to a2, all
        other items fixed (item ``exclude`` is skipped and handled by caller)."""
        Fi, FiT = self.F[:, i, :], self.FT[:, i, :]
        pos = self.pos
        Dn = self.tables[:, a2, :][:, pos]      # D[a2, p_k]
        Do = self.tables[:, a, :][:, pos]       # D[a, p_k]
        DnT = self.tables[:, :, a2][:, pos]     # D[p_k, a2]
        DoT = self.tables[:, :, a][:, pos]      # D[p_k, a]
        d = (Fi * (Dn - Do)).sum(1) + (FiT * (DnT - DoT)).sum(1)   # (T,)
        # self-terms F[i,i] are zero; exclude partner handled by caller
        total = float(d.sum())
        if exclude is not None:
            k = exclude
            pk = pos[k]
            total -= float((Fi[:, k] * (self.tables[:, a2, pk] - self.tables[:, a, pk])).sum())
            total -= float((FiT[:, k] * (self.tables[:, pk, a2] - self.tables[:, pk, a])).sum())
        return total

    def delta(self, i: int, c2: int) -> float:
        """Energy change of moving item i to cell c2 (swapping if occupied)."""
        a = self.pos[i]
        j = self.occ[c2]
        if j == -1:
            d = self._item_delta(i, a, c2, None)
            if self.nblank and self.w_ws:
                d += self.w_ws * self._blank_delta_move(a, c2)
            return d
        b = c2
        d = self._item_delta(i, a, b, j) + self._item_delta(j, b, a, i)
        # pair (i, j) with both moved: before D[a,b]/D[b,a], after D[b,a]/D[a,b]
        T = self.tables
        d += float((self.F[:, i, j] * (T[:, b, a] - T[:, a, b])).sum() + (self.F[:, j, i] * (T[:, a, b] - T[:, b, a])).sum())
        return d

    def _blank_delta_move(self, a: int, c2: int) -> float:
        """Whitespace-term change (unweighted, per-blank normalised) when the
        item at cell a moves to blank cell c2."""
        affected = set()
        for c in (a, c2):
            x, y = self.x[c], self.y[c]
            affected.add(c)
            for dx, dy in NEIGH4:
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.grid.width and 0 <= ny < self.grid.height:
                    affected.add(ny * self.grid.width + nx)
        before = sum(self.blank_penalty_at(c) for c in affected)
        i = self.occ[a]
        self.occ[a], self.occ[c2] = -1, i
        after = sum(self.blank_penalty_at(c) for c in affected)
        self.occ[a], self.occ[c2] = i, -1
        return (after - before) / self.nblank

    def apply(self, i: int, c2: int) -> None:
        a = self.pos[i]
        j = self.occ[c2]
        self.pos[i] = c2
        self.occ[c2] = i
        self.occ[a] = j
        if j != -1:
            self.pos[j] = a

    # ---- search ----------------------------------------------------
    def propose(self, local_radius: int, p_local: float, p_targeted: float = 0.0) -> tuple[int, int] | None:
        i = int(self.rng.integers(self.n))
        a = self.pos[i]
        u = self.rng.random()
        if u < p_targeted and self.targets is not None:
            # move next to a geographic neighbour's cell
            j = int(self.targets[i, self.rng.integers(self.targets.shape[1])])
            b = self.pos[j]
            dx, dy = int(self.rng.integers(-1, 2)), int(self.rng.integers(-1, 2))
            nx, ny = self.x[b] + dx, self.y[b] + dy
            if not (0 <= nx < self.grid.width and 0 <= ny < self.grid.height):
                return None
            c2 = ny * self.grid.width + nx
        elif u < p_targeted + p_local:
            dx = int(self.rng.integers(-local_radius, local_radius + 1))
            dy = int(self.rng.integers(-local_radius, local_radius + 1))
            nx, ny = self.x[a] + dx, self.y[a] + dy
            if not (0 <= nx < self.grid.width and 0 <= ny < self.grid.height):
                return None
            c2 = ny * self.grid.width + nx
        else:
            c2 = int(self.rng.integers(self.C))
        if c2 == a:
            return None
        if c2 in self.fixed_blanks:
            return None
        if self.allowed is not None:
            if i in self.allowed and c2 not in self.allowed_sets[i]:
                return None
            j = self.occ[c2]
            if j != -1 and j in self.allowed and a not in self.allowed_sets[j]:
                return None
        return i, c2

    def run(self, iterations: int, t0: float | None = None, t1: float = 1e-4, local_radius: int = 2, p_local: float = 0.7, p_targeted: float = 0.2, log_every: int = 0) -> dict:
        if self.allowed is not None:
            self.allowed_sets = {i: set(map(int, v)) for i, v in self.allowed.items()}
        if t0 is None:
            samples = []
            while len(samples) < 200:
                m = self.propose(local_radius, p_local, p_targeted)
                if m:
                    samples.append(abs(self.delta(*m)))
            t0 = float(np.median(samples)) * 2.0 or 1e-3
        best_e, best_pos = self.energy, self.pos.copy()
        accepted = 0
        proposed = 0
        start = time.time()
        log_t = math.log(t1 / t0)
        for it in range(iterations):
            T = t0 * math.exp(log_t * it / max(iterations - 1, 1))
            m = self.propose(local_radius, p_local, p_targeted)
            if m is None:
                continue
            proposed += 1
            d = self.delta(*m)
            if d <= 0 or self.rng.random() < math.exp(-d / T):
                self.apply(*m)
                self.energy += d
                accepted += 1
                if self.energy < best_e - 1e-12:
                    best_e, best_pos = self.energy, self.pos.copy()
            if log_every and it % log_every == 0:
                print(f"  it={it} T={T:.4g} E={self.energy:.5f} best={best_e:.5f}", flush=True)
        # restore best
        self.pos = best_pos
        self.occ[:] = -1
        self.occ[self.pos] = np.arange(self.n)
        self.energy = self.full_energy()
        return {"seed": self.seed, "iterations": iterations, "t0": t0, "t1": t1, "local_radius": local_radius, "p_local": p_local, "p_targeted": p_targeted, "proposed": proposed, "accepted": accepted, "best_energy": best_e, "final_energy_recomputed": self.energy, "seconds": round(time.time() - start, 1)}

    def to_layout(self) -> Layout:
        cells = {}
        for i, cid in enumerate(self.problem.geo.ids):
            c = int(self.pos[i])
            cells[cid] = (int(self.x[c]), int(self.y[c]))
        blanks = {(int(self.x[c]), int(self.y[c])) for c in range(self.C) if self.occ[c] == -1}
        return Layout(self.grid.width, self.grid.height, cells, blanks, self.layout.profile, self.layout.cldr_version, dict(self.layout.generator))


def anneal(problem: Problem, grid: Grid, start: Layout, seed: int, iterations: int, **kw) -> tuple[Layout, dict, dict]:
    ann = Annealer(problem, grid, start, seed=seed)
    stats = ann.run(iterations, **kw)
    out = ann.to_layout()
    rep = score(out, problem, ann.tables)
    return out, rep, stats
