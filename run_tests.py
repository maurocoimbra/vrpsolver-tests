#!/usr/bin/env python3
"""Run all generated RCSP test instances with a per-instance timeout."""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_TESTS_DIR = PROJECT_ROOT / "tests"
DENSITIES = range(2, 11, 2)
VERTEX_COUNTS = range(5, 51, 5)
TERMINATION_GRACE_SECONDS = 5


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run every density_02..density_10 / nb_verts_5..nb_verts_50 "
            "instance. After a timeout, later instances of the same density "
            "are skipped."
        )
    )
    parser.add_argument(
        "--timeout-minutes",
        type=float,
        default=30,
        help="Maximum runtime for each instance (default: 30 minutes)",
    )
    parser.add_argument(
        "--tests-dir",
        type=Path,
        default=DEFAULT_TESTS_DIR,
        help="Directory containing the density_* folders",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the commands without running them",
    )
    args = parser.parse_args()
    if args.timeout_minutes <= 0:
        parser.error("--timeout-minutes must be greater than zero")
    return args


def stop_process_group(process: subprocess.Popen[bytes]) -> None:
    """Stop the command and any solver processes it started."""
    if process.poll() is not None:
        return

    os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=TERMINATION_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()


def run_with_timeout(command: list[str], timeout_seconds: float) -> int | None:
    process = subprocess.Popen(
        command,
        cwd=PROJECT_ROOT,
        start_new_session=True,
    )
    try:
        return process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        stop_process_group(process)
        return None
    except KeyboardInterrupt:
        stop_process_group(process)
        raise


def display_command(command: list[str]) -> str:
    return " ".join(command)


def main() -> int:
    args = parse_args()
    tests_dir = args.tests_dir.resolve()
    timeout_seconds = args.timeout_minutes * 60

    completed = 0
    failed = 0
    timed_out = 0
    skipped = 0

    for density in DENSITIES:
        print(f"\n=== Density {density:02d} ===", flush=True)

        for position, vertices in enumerate(VERTEX_COUNTS):
            test_file = tests_dir / f"density_{density:02d}" / f"nb_verts_{vertices}.txt"
            if not test_file.is_file():
                print(f"SKIP missing file: {test_file}", flush=True)
                skipped += 1
                continue

            try:
                problem_path = test_file.relative_to(PROJECT_ROOT)
            except ValueError:
                problem_path = test_file

            command = [
                "uv",
                "run",
                "python3",
                "src/main.py",
                "--problem_txt",
                str(problem_path),
            ]
            print(
                f"[{density:02d}/{vertices:02d}] $ {display_command(command)}",
                flush=True,
            )

            if args.dry_run:
                continue

            started_at = time.monotonic()
            return_code = run_with_timeout(command, timeout_seconds)
            elapsed = time.monotonic() - started_at

            if return_code is None:
                remaining = len(VERTEX_COUNTS) - position - 1
                timed_out += 1
                skipped += remaining
                print(
                    f"TIMEOUT after {elapsed:.1f}s: {test_file.name}. "
                    f"Skipping the remaining {remaining} test(s) for density "
                    f"{density:02d}.",
                    flush=True,
                )
                break

            completed += 1
            if return_code == 0:
                print(f"PASS in {elapsed:.1f}s", flush=True)
            else:
                failed += 1
                print(
                    f"FAIL (exit code {return_code}) in {elapsed:.1f}s; continuing",
                    flush=True,
                )

    if not args.dry_run:
        print(
            "\n=== Summary ===\n"
            f"Completed: {completed}\n"
            f"Failed:    {failed}\n"
            f"Timed out: {timed_out}\n"
            f"Skipped:   {skipped}",
            flush=True,
        )

    return 1 if failed or timed_out else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user.", file=sys.stderr)
        sys.exit(130)
