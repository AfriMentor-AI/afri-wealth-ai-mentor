"""Shared helpers for the pilot-scale load-test scripts (card O4.3).

Mirrors the percentile/Sample pattern already established in
services/chat-orchestration-service/scripts/chat_latency_benchmark.py (D3.5) so
all four service benchmarks report results the same shape.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass


@dataclass
class Sample:
    """One simulated user's round trip. ``elapsed_ms`` covers every request in
    the scenario (e.g. create goal + add milestone + complete milestone), not
    just the last call — the dashboard cares about the whole user action."""

    elapsed_ms: float
    status_code: int


def percentile(values: list[float], rank: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((rank / 100) * len(ordered)) - 1))
    return ordered[index]


def summarize(service: str, samples: list[Sample], p95_threshold_ms: float) -> dict:
    """Build the common result shape: counts, latency percentiles, pass/fail.

    A "P0" for this service is either a non-2xx/3xx response or blowing the p95
    latency budget — both make it into ``failed``/``status`` so the orchestrator
    can roll every service's result into one no-P0-failures verdict (O4.3 AC).
    """
    failures = [s for s in samples if s.status_code >= 400]
    ok = [s.elapsed_ms for s in samples if s.status_code < 400]

    result: dict = {
        "service": service,
        "requests": len(samples),
        "successful": len(ok),
        "failed": len(failures),
        "p95_threshold_ms": p95_threshold_ms,
    }
    if not ok:
        result["status"] = "P0_NO_SUCCESSFUL_REQUESTS"
        return result

    p50 = round(percentile(ok, 50), 2)
    p95 = round(percentile(ok, 95), 2)
    result["elapsed_ms"] = {"p50": p50, "p95": p95, "mean": round(statistics.mean(ok), 2)}
    result["status"] = "PASS" if (not failures and p95 < p95_threshold_ms) else "P0_FAIL"
    return result
