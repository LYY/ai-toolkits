#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import NoReturn, cast

if __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "tests"

from .address_pr_comments_review_case_runner import CASES_DIR, run_case
from .address_pr_comments_review_manifest import (
    is_regression_manifest,
    load_manifest,
    validate_manifest,
)


class Arguments(argparse.Namespace):
    resume: str | None = None
    validate_manifest_only: bool = False


def _die(message: str, exit_code: int = 2) -> NoReturn:
    sys.stderr.write(message + "\n")
    raise SystemExit(exit_code)


def _do_run(args: Arguments) -> None:
    manifest = load_manifest()
    errors = validate_manifest(manifest)
    if errors:
        sys.stderr.write("Manifest validation errors:\n")
        for error in errors:
            sys.stderr.write(f"  - {error}\n")
        if args.validate_manifest_only:
            raise SystemExit(1)
        _die(
            "Manifest validation failed. Fix cases.json or use --validate-manifest-only."
        )
    if args.validate_manifest_only:
        print("Manifest validation passed.")
        return
    if not is_regression_manifest(manifest):
        _die("Manifest validation returned inconsistent result")

    resume_from: str | None = args.resume
    skip_until_resume = resume_from is not None
    found_resume = False
    total = 0
    passed = 0
    failed = 0
    skipped = 0
    for case in manifest["cases"]:
        case_id = case["case_id"]
        if skip_until_resume:
            if case_id == resume_from:
                skip_until_resume = False
                found_resume = True
            else:
                print(f"  SKIP (resume): {case_id}")
                skipped += 1
                continue
        if not found_resume and resume_from:
            continue

        case_dir = CASES_DIR / case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        result = run_case(case, case_dir)
        total += 1
        if result["passed"]:
            passed += 1
            print(f"  PASS: {case_id}")
            continue

        failed += 1
        reason_parts: list[str] = []
        if not result.get("exit_ok", False):
            reason_parts.append(
                f"exit={result['exit_code']} (expected {result['expected_exit']})"
            )
        if not result.get("diag_ok", False):
            reason_parts.append(
                f"diag={result.get('actual_diag', '?')} (expected {case['expected_diagnostic']})"
            )
        if not result.get("sentinel_ok", False):
            reason_parts.append(
                f"missing sentinels: {result.get('missing_sentinels', [])}"
            )
        reason = "; ".join(reason_parts) or result.get("reason", "unknown")
        print(f"  FAIL: {case_id} ({reason})")

    print(f"\ntotal={total} passed={passed} failed={failed} skipped={skipped}")
    if not found_resume and resume_from:
        _die(f"Resume point '{resume_from}' not found in manifest")
    if failed > 0:
        raise SystemExit(1)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Deterministic regression runner for address-pr-comments-review"
    )
    _ = parser.add_argument(
        "--resume", type=str, default=None, help="Resume from a specific case_id"
    )
    _ = parser.add_argument(
        "--validate-manifest-only",
        action="store_true",
        help="Only validate the manifest, do not run cases",
    )
    return parser


def main() -> int:
    args = cast(Arguments, _build_parser().parse_args())
    try:
        _do_run(args)
    except OSError as error:
        _die(f"I/O error: {error}", 4)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
