"""Orchestrates the O4.3 pilot-scale load test across chat, goals, library, and
progress services and writes a combined markdown report.

Concurrency baseline: docs/research/pilot-data-collection-plan-v0.md fixes the
pilot cohort at N = 30 participants (card C2.5's sample-size analysis). This
script treats "expected pilot concurrency" as the conservative worst case of
all 30 participants active at once, and tests at 2x that per the O4.3
acceptance criterion — i.e. 60 concurrent simulated users by default.

Each service benchmark is a standalone script (also runnable on its own) so a
single service can be re-tested in isolation without re-running the full
suite. This orchestrator runs all four concurrently, against a stack that is
already up (see docs/deployment/pilot-load-test.md for how to bring one up).

Example:
  python run_pilot_load_test.py --concurrency 60 --requests-per-user 5
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import UTC, datetime

PILOT_PARTICIPANTS = 30  # docs/research/pilot-data-collection-plan-v0.md, card C2.5
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
CHAT_BENCHMARK = os.path.join(
    REPO_ROOT, "services", "chat-orchestration-service", "scripts", "chat_latency_benchmark.py"
)


async def _run_script(script: str, args: list[str]) -> tuple[str, int, dict | None, str]:
    proc = await asyncio.create_subprocess_exec(
        sys.executable, script, *args,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    try:
        parsed = json.loads(stdout.decode())
    except json.JSONDecodeError:
        parsed = None
    return script, proc.returncode, parsed, stderr.decode(errors="replace")


def _chat_status(result: dict | None, returncode: int) -> str:
    if result is None:
        return "P0_NO_SUCCESSFUL_REQUESTS"
    if result.get("successful", 0) == 0:
        return "P0_NO_SUCCESSFUL_REQUESTS"
    return "PASS" if returncode == 0 else "P0_FAIL"


async def run(args: argparse.Namespace) -> dict:
    requests = args.concurrency * args.requests_per_user
    common_flags = [
        "--users", str(args.concurrency),
        "--requests", str(requests),
        "--timeout-seconds", str(args.timeout_seconds),
    ]

    jobs = [
        _run_script(
            CHAT_BENCHMARK,
            ["--base-url", args.chat_url, *common_flags],
        ),
        _run_script(
            os.path.join(SCRIPT_DIR, "goals_benchmark.py"),
            ["--base-url", args.goals_url, *common_flags],
        ),
        _run_script(
            os.path.join(SCRIPT_DIR, "library_benchmark.py"),
            ["--base-url", args.library_url, *common_flags],
        ),
        _run_script(
            os.path.join(SCRIPT_DIR, "progress_benchmark.py"),
            ["--base-url", args.progress_url, *common_flags],
        ),
    ]
    results = await asyncio.gather(*jobs)

    services = {}
    for script, returncode, parsed, stderr in results:
        name = os.path.basename(script).removesuffix(".py")
        if name == "chat_latency_benchmark":
            services["chat-orchestration-service"] = {
                **(parsed or {}),
                "status": _chat_status(parsed, returncode),
                "stderr_tail": stderr[-2000:] if returncode != 0 and not parsed else "",
            }
        else:
            services[(parsed or {}).get("service", name)] = parsed or {
                "status": "P0_SCRIPT_ERROR",
                "stderr_tail": stderr[-2000:],
            }

    return {
        "run_at": datetime.now(UTC).isoformat(),
        "concurrency": args.concurrency,
        "pilot_participants_baseline": PILOT_PARTICIPANTS,
        "concurrency_multiplier": round(args.concurrency / PILOT_PARTICIPANTS, 2),
        "services": services,
    }


def render_markdown(report: dict) -> str:
    lines = [
        "# O4.3 Pilot-Scale Load Test Report",
        "",
        f"Run at: {report['run_at']}",
        "",
        f"Concurrency: {report['concurrency']} simulated users "
        f"({report['concurrency_multiplier']}x the "
        f"{report['pilot_participants_baseline']}-participant pilot baseline from "
        "docs/research/pilot-data-collection-plan-v0.md, card C2.5).",
        "",
        "| Service | Status | Requests | Successful | Failed | p50 (ms) | p95 (ms) |",
        "|---|---|---|---|---|---|---|",
    ]
    any_p0 = False
    for service, result in report["services"].items():
        status = result.get("status", "UNKNOWN")
        if status != "PASS":
            any_p0 = True
        latency = result.get("elapsed_ms") or result.get("complete_ms") or {}
        lines.append(
            f"| {service} | {status} | {result.get('requests', '—')} | "
            f"{result.get('successful', '—')} | {result.get('failed', '—')} | "
            f"{latency.get('p50', '—')} | {latency.get('p95', '—')} |"
        )

    lines += [
        "",
        "## Verdict",
        "",
        ("**FAIL — at least one service reported a P0 at 2x pilot concurrency.**"
         if any_p0 else
         "**PASS — no P0 failures at 2x pilot concurrency.**"),
    ]

    for service, result in report["services"].items():
        if result.get("stderr_tail"):
            lines += [
                "",
                f"### {service} — stderr (truncated)",
                "```",
                result["stderr_tail"],
                "```",
            ]

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--concurrency", type=int, default=2 * PILOT_PARTICIPANTS,
        help="Simulated concurrent users; default is 2x the documented pilot cohort size.",
    )
    parser.add_argument("--requests-per-user", type=int, default=5)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--chat-url", default="http://localhost:8003")
    parser.add_argument("--goals-url", default="http://localhost:8006")
    parser.add_argument("--progress-url", default="http://localhost:8007")
    parser.add_argument("--library-url", default="http://localhost:8008")
    parser.add_argument(
        "--out",
        default=os.path.join(REPO_ROOT, "docs", "deployment", "o4-3-pilot-load-test-report.md"),
    )
    args = parser.parse_args()

    report = asyncio.run(run(args))
    markdown = render_markdown(report)

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(markdown)

    print(markdown)
    print(f"Report written to {args.out}")

    any_p0 = any(r.get("status") != "PASS" for r in report["services"].values())
    return 1 if any_p0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
