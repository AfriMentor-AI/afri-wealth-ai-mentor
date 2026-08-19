"""Pilot-scale load test for progress-gamification-service (card O4.3).

Scenario per simulated user: record a completed action, then fetch the
progress summary (streak + heatmap + badges) — the read/write pair a goal
completion actually drives in the app, and the one most exposed to R5/R6 in
docs/backlog-grooming.md (event-bus reliability, eventual-consistency UX).

Example:
  python progress_benchmark.py --base-url http://localhost:8007 --users 60 --requests 300
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time

import httpx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Sample, summarize  # noqa: E402


async def one_round_trip(client: httpx.AsyncClient, base_url: str, user_id: str) -> Sample:
    headers = {"X-User-Id": user_id}
    started = time.perf_counter()
    try:
        action_resp = await client.post(
            f"{base_url}/api/v1/progress/actions",
            headers=headers,
            json={"kind": "daily_action"},
        )
        action_resp.raise_for_status()

        summary_resp = await client.get(f"{base_url}/api/v1/progress", headers=headers)
        summary_resp.raise_for_status()
        status_code = summary_resp.status_code
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
    except httpx.HTTPError:
        status_code = 599

    return Sample(elapsed_ms=(time.perf_counter() - started) * 1000, status_code=status_code)


async def run(args: argparse.Namespace) -> list[Sample]:
    limits = httpx.Limits(max_connections=args.users, max_keepalive_connections=args.users)
    timeout = httpx.Timeout(args.timeout_seconds, connect=2.0)
    semaphore = asyncio.Semaphore(args.users)

    async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:
        async def request(index: int) -> Sample:
            async with semaphore:
                # Distinct user per request (not per --users slot): the actions
                # endpoint is a same-day-same-kind no-op the second time, which
                # would silently skew this into a read-only benchmark otherwise.
                return await one_round_trip(
                    client, args.base_url.rstrip("/"), f"{args.user_id}-{index}"
                )

        return await asyncio.gather(*(request(i) for i in range(args.requests)))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8007")
    parser.add_argument("--users", type=int, default=60)
    parser.add_argument("--requests", type=int, default=300)
    parser.add_argument("--timeout-seconds", type=float, default=15.0)
    parser.add_argument("--user-id", default="o43-load-test")
    parser.add_argument("--p95-threshold-ms", type=float, default=1000.0)
    args = parser.parse_args()

    samples = asyncio.run(run(args))
    result = summarize("progress-gamification-service", samples, args.p95_threshold_ms)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
