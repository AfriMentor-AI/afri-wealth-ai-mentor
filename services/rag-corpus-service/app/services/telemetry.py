"""In-memory latency telemetry for the RAG query path (card C2.2).

Backs the "Inference Latency" tile on the RAG Corpus Admin screen. Deliberately
process-local and unpersisted: a rolling window of the most recent query
durations, reset on restart. `latency_snapshot()` reports `sample_count` so a
consumer can tell an idle service (no samples) from a fast one.

If cross-replica or historical latency is ever needed, this should be replaced
by a real metrics exporter (Prometheus histogram) rather than extended here.
"""
from __future__ import annotations

import os
from collections import deque

# Window size is a trade-off: large enough that p95 means something, small
# enough that the numbers track recent behaviour rather than all-time history.
LATENCY_WINDOW = int(os.getenv("RAG_LATENCY_WINDOW", "200"))

# deque.append with maxlen is atomic under the GIL, so the threadpool workers
# FastAPI uses for sync endpoints can append without a lock.
_latencies: deque[float] = deque(maxlen=LATENCY_WINDOW)


def record_query_latency(elapsed_ms: float) -> None:
    """Record one query duration in milliseconds."""
    _latencies.append(float(elapsed_ms))


def reset() -> None:
    """Clear the window. Used by tests."""
    _latencies.clear()


def _percentile(sorted_values: list[float], pct: float) -> float:
    """Nearest-rank percentile. `sorted_values` must be non-empty and sorted."""
    if len(sorted_values) == 1:
        return round(sorted_values[0], 2)
    rank = max(1, min(len(sorted_values), round(pct / 100.0 * len(sorted_values))))
    return round(sorted_values[rank - 1], 2)


def latency_snapshot() -> dict:
    """Summarise the current window.

    Returns zeroed percentiles with ``sample_count: 0`` when no queries have run
    yet — callers should read the count before trusting p50/p95.
    """
    values = sorted(_latencies)
    if not values:
        return {"p50": 0.0, "p95": 0.0, "mean": 0.0, "sample_count": 0}
    return {
        "p50": _percentile(values, 50),
        "p95": _percentile(values, 95),
        "mean": round(sum(values) / len(values), 2),
        "sample_count": len(values),
    }
