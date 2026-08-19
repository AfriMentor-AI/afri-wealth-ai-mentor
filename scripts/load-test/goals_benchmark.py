"""Pilot-scale load test for goals-milestones-service (card O4.3).

Scenario per simulated user: create a goal, add a milestone, complete it —
the same round trip S4.1's "CRUD + milestone state machine" acceptance
criterion is built around, and the one that fires the goal.*/milestone.*
events progress-gamification-service consumes.

Example:
  python goals_benchmark.py --base-url http://localhost:8006 --users 60 --requests 300
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
        goal_resp = await client.post(
            f"{base_url}/api/v1/goals",
            headers=headers,
            json={"title": "Save for shop inventory", "description": "Pilot load test goal"},
        )
        goal_resp.raise_for_status()
        goal_id = goal_resp.json()["id"]

        milestone_resp = await client.post(
            f"{base_url}/api/v1/goals/{goal_id}/milestones",
            headers=headers,
            json={"title": "Save first ₦20,000"},
        )
        milestone_resp.raise_for_status()
        milestone_id = milestone_resp.json()["id"]

        complete_resp = await client.post(
            f"{base_url}/api/v1/milestones/{milestone_id}/complete", headers=headers
        )
        complete_resp.raise_for_status()
        status_code = complete_resp.status_code
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
                return await one_round_trip(
                    client, args.base_url.rstrip("/"), f"{args.user_id}-{index % args.users}"
                )

        return await asyncio.gather(*(request(i) for i in range(args.requests)))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8006")
    parser.add_argument("--users", type=int, default=60)
    parser.add_argument("--requests", type=int, default=300)
    parser.add_argument("--timeout-seconds", type=float, default=15.0)
    parser.add_argument("--user-id", default="o43-load-test")
    parser.add_argument("--p95-threshold-ms", type=float, default=1500.0)
    args = parser.parse_args()

    samples = asyncio.run(run(args))
    result = summarize("goals-milestones-service", samples, args.p95_threshold_ms)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
