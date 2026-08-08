#!/usr/bin/env python3
"""Minimum detectable effect for the Proposal 2 pilot (card C2.5).

Usage:
    python scripts/pilot_power_analysis.py

Reproduces the figures in section 2 of
`docs/research/pilot-data-collection-plan-v0.md`. It lives in the repo rather
than in a notebook because the plan's central claim — that this pilot cannot
test the between-arm question and should not be written up as though it can —
rests on these numbers, and a reviewer should be able to re-run them.

Uses the noncentral t distribution rather than the normal approximation; at
n = 10-15 per arm the approximation overstates power enough to matter.
"""

from __future__ import annotations

import numpy as np
from scipy import stats

ALPHA = 0.05
POWER = 0.80


def _solve(achieved, lo: float = 0.001, hi: float = 5.0) -> float:
    """Bisect for the smallest effect size reaching POWER."""
    for _ in range(200):
        mid = (lo + hi) / 2
        if achieved(mid) < POWER:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def power_two_sample(n_per_arm: int, d: float, alpha: float = ALPHA) -> float:
    """Power of a two-sided independent-samples t-test at effect size d."""
    df = 2 * n_per_arm - 2
    t_crit = stats.t.ppf(1 - alpha / 2, df)
    ncp = d * np.sqrt(n_per_arm / 2)
    return 1 - stats.nct.cdf(t_crit, df, ncp)


def power_paired(n_pairs: int, d: float, alpha: float = ALPHA) -> float:
    """Power of a two-sided paired t-test at effect size d_z."""
    df = n_pairs - 1
    t_crit = stats.t.ppf(1 - alpha / 2, df)
    return 1 - stats.nct.cdf(t_crit, df, d * np.sqrt(n_pairs))


def mde_two_sample(n_per_arm: int) -> float:
    return _solve(lambda d: power_two_sample(n_per_arm, d))


def mde_paired(n_pairs: int) -> float:
    return _solve(lambda d: power_paired(n_pairs, d))


def main() -> None:
    print(f"Two-sided alpha={ALPHA}, power={POWER:.0%}, noncentral t\n")

    print("BETWEEN GROUPS (Arm A vs Arm B) - plan section 2.1")
    print(f"  {'total N':>8} {'per arm':>8} {'MDE (d)':>9}")
    for total in (20, 24, 30):
        per = total // 2
        print(f"  {total:>8} {per:>8} {mde_two_sample(per):>9.2f}")

    print("\n  Power to detect a moderate effect (d=0.50):")
    for total in (20, 24, 30):
        per = total // 2
        print(f"    total N={total:>3} ({per}/arm): {power_two_sample(per, 0.50):>4.0%}")

    n = 2
    while mde_two_sample(n) > 0.50:
        n += 1
    print(f"\n  N to detect d=0.50 at {POWER:.0%} power: {n}/arm = {2 * n} total")

    print("\nWITHIN SUBJECT (pre vs post, pooled) - plan section 2.2")
    print(f"  {'N pairs':>8} {'MDE (d_z)':>10}")
    for n_pairs in (20, 24, 30):
        print(f"  {n_pairs:>8} {mde_paired(n_pairs):>10.2f}")

    print("\nATTRITION - plan section 2.3")
    for att in (0.15, 0.25):
        for total in (24, 30):
            retained = int(round(total * (1 - att)))
            per = retained // 2
            print(
                f"  {att:.0%} on N={total}: {retained} retained "
                f"({per}/arm) -> MDE d={mde_two_sample(per):.2f}"
            )


if __name__ == "__main__":
    main()
