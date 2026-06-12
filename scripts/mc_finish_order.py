"""Pure-function Monte Carlo finish-order core (roadmap transform-v0.2 §4.5).

Pulled forward from the strategy-engine v2 so the simulation core can be validated
offline on existing marts with zero live data. Deliberately dependency-light and
side-effect-free: given per-driver predicted mean pace and its SE, it draws pace
samples and ranks them into finish-position distributions. This same function is
intended to become the live engine's core, so it stays pure (rng passed in, no I/O).

Pace model: lower pace = better finish. Each driver d gets pace_d ~ Normal(mu_d, se_d).
An optional common_se adds a single shared shock per simulation (the §3 host
structural pace, which is common-mode across drivers and cancels in ordering) kept
as a parameter so the live engine can switch it on without changing the core.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class FinishDistribution:
    driver_ids: tuple
    p_position: np.ndarray      # [n_drivers, n_drivers]; p_position[d, k] = P(driver d finishes position k+1)
    expected_position: np.ndarray
    p_win: np.ndarray
    p_podium: np.ndarray
    p_beats_next: np.ndarray    # P(d beats the driver with the next-best mean pace)
    finish_pos_se: np.ndarray   # sd of the simulated finishing position


def simulate_finish_distribution(
    driver_ids,
    mu: np.ndarray,
    se: np.ndarray,
    n_sims: int = 5000,
    common_se: float = 0.0,
    rng: np.random.Generator | None = None,
) -> FinishDistribution:
    """Simulate finish-position distributions from predicted pace ± SE.

    Args:
        driver_ids: identifiers, length n.
        mu: predicted mean lap pace per driver (lower = faster), length n.
        se: per-driver pace SE (driver-specific / differential component), length n.
        n_sims: number of Monte Carlo draws.
        common_se: SE of a per-sim shared shock applied to all drivers (cancels in
            ordering; included for parity with the marginal SE, not order effects).
        rng: numpy Generator; created with a fixed seed if omitted (deterministic).
    """
    rng = rng or np.random.default_rng(0)
    mu = np.asarray(mu, float)
    se = np.asarray(se, float)
    n = len(mu)

    # pace draws: [n_sims, n]
    draws = mu[None, :] + rng.standard_normal((n_sims, n)) * se[None, :]
    if common_se > 0:
        draws = draws + rng.standard_normal((n_sims, 1)) * common_se

    # rank within each sim: fastest (lowest pace) -> position 1
    order = np.argsort(draws, axis=1, kind="stable")          # driver indices sorted by pace
    positions = np.empty_like(order)
    rank_idx = np.broadcast_to(np.arange(n), order.shape)
    np.put_along_axis(positions, order, rank_idx, axis=1)     # positions[s, d] = 0-based finish pos
    positions = positions + 1                                 # 1-based

    # p_position[d, k] = fraction of sims driver d finished position k+1
    p_position = np.zeros((n, n))
    for k in range(n):
        p_position[:, k] = np.mean(positions == (k + 1), axis=0)

    expected_position = (p_position * np.arange(1, n + 1)[None, :]).sum(axis=1)
    p_win = p_position[:, 0]
    p_podium = p_position[:, :3].sum(axis=1)
    finish_pos_se = positions.std(axis=0, ddof=0)

    # p_beats_next: probability d finishes ahead of the driver with the next-worst mean pace
    mean_rank = np.argsort(np.argsort(mu, kind="stable"), kind="stable")  # 0=best mu
    p_beats_next = np.full(n, np.nan)
    for d in range(n):
        nxt = np.where(mean_rank == mean_rank[d] + 1)[0]
        if len(nxt):
            p_beats_next[d] = np.mean(positions[:, d] < positions[:, nxt[0]])

    return FinishDistribution(
        driver_ids=tuple(driver_ids),
        p_position=p_position,
        expected_position=expected_position,
        p_win=p_win,
        p_podium=p_podium,
        p_beats_next=p_beats_next,
        finish_pos_se=finish_pos_se,
    )
