"""D3.5 staging benchmark for streaming chat latency.

Example:
  python scripts/chat_latency_benchmark.py --base-url http://localhost:8003 \
      --users 20 --requests 200 --user-id load-test-user

The benchmark measures time-to-first-token and time-to-complete separately. It
uses the service directly by default; benchmark the gateway URL to include edge
proxy latency. A real staging LLM_API_KEY and populated RAG service are required
for a meaningful result.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from dataclasses import dataclass

import httpx


@dataclass
class Sample:
    first_token_ms: float
    complete_ms: float
    status_code: int


async def stream_one(
    client: httpx.AsyncClient,
    base_url: str,
    user_id: str,
    prompt: str,
) -> Sample:
    # Card O4.3: a single failed/timed-out request used to raise straight out of
    # asyncio.gather() and abort the whole run — under real concurrency some
    # requests failing is the point of the test, not a reason to lose every
    # other sample. Caught here the same way the goals/library/progress
    # benchmarks (scripts/load-test/) already handle per-request failures.
    try:
        session_response = await client.post(
            f"{base_url}/api/v1/chat/sessions",
            headers={"X-User-Id": user_id},
            json={},
        )
        session_response.raise_for_status()
        session_id = session_response.json()["id"]

        started = time.perf_counter()
        first_token = None
        async with client.stream(
            "POST",
            f"{base_url}/api/v1/chat/sessions/{session_id}/messages/stream",
            headers={"X-User-Id": user_id},
            json={"content": prompt},
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("event: token") and first_token is None:
                    first_token = time.perf_counter()
            completed = time.perf_counter()
            status_code = response.status_code
    except httpx.HTTPStatusError as exc:
        return Sample(first_token_ms=0.0, complete_ms=0.0, status_code=exc.response.status_code)
    except httpx.HTTPError:
        return Sample(first_token_ms=0.0, complete_ms=0.0, status_code=599)

    return Sample(
        first_token_ms=((first_token or completed) - started) * 1000,
        complete_ms=(completed - started) * 1000,
        status_code=status_code,
    )


async def run(args: argparse.Namespace) -> list[Sample]:
    limits = httpx.Limits(max_connections=args.users, max_keepalive_connections=args.users)
    timeout = httpx.Timeout(args.timeout_seconds, connect=2.0)
    prompts = [
        "How can I improve cash flow in my small business?",
        "How do I build a consistent savings habit?",
        "How should I price products in the Nigerian market?",
    ]
    semaphore = asyncio.Semaphore(args.users)
    async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:
        async def request(index: int) -> Sample:
            async with semaphore:
                return await stream_one(
                    client,
                    args.base_url.rstrip("/"),
                    f"{args.user_id}-{index % args.users}",
                    prompts[index % len(prompts)],
                )

        return await asyncio.gather(*(request(index) for index in range(args.requests)))


def percentile(values: list[float], rank: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((rank / 100) * len(ordered)) - 1))
    return ordered[index]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8003")
    parser.add_argument("--users", type=int, default=20)
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--timeout-seconds", type=float, default=15.0)
    parser.add_argument("--user-id", default="d35-load-test")
    args = parser.parse_args()

    samples = asyncio.run(run(args))
    failures = [sample for sample in samples if sample.status_code >= 400]
    first = [sample.first_token_ms for sample in samples if sample.status_code < 400]
    complete = [sample.complete_ms for sample in samples if sample.status_code < 400]
    if not complete:
        print(json.dumps({"requests": len(samples), "successful": 0, "failed": len(failures)}))
        return 1

    result = {
        "requests": len(samples),
        "successful": len(complete),
        "failed": len(failures),
        "first_token_ms": {
            "p50": round(percentile(first, 50), 2),
            "p95": round(percentile(first, 95), 2),
            "mean": round(statistics.mean(first), 2),
        },
        "complete_ms": {
            "p50": round(percentile(complete, 50), 2),
            "p95": round(percentile(complete, 95), 2),
            "mean": round(statistics.mean(complete), 2),
        },
    }
    print(json.dumps(result, indent=2))
    return 0 if result["complete_ms"]["p95"] < 3000 else 2


if __name__ == "__main__":
    raise SystemExit(main())
