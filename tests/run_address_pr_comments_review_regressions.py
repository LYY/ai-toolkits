#!/usr/bin/env python3
"""Deterministic regression runner for address-pr-comments-review.

Reads cases.json manifest, executes each case in isolated environment,
captures stdout/stderr/exit, writes case bundles. stdlib only.

Usage:
  python3 run_address_pr_comments_review_regressions.py [--resume] [--validate-manifest-only]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import NoReturn

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA_VERSION = 1
SCRIPT_DIR = Path(__file__).resolve().parent
REGRESSIONS_DIR = SCRIPT_DIR / "address-pr-comments-review-regressions"
CASES_DIR = REGRESSIONS_DIR / "cases"


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha256(path: str) -> str:
    with open(path, "rb") as fh:
        return _sha256_hex(fh.read())


def _canonical_json_bytes(obj: object) -> bytes:
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return (text + "\n").encode("utf-8")


def _format_json_bytes(obj: object) -> str:
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return text + "\n"


def _die(message: str, exit_code: int = 2) -> NoReturn:
    sys.stderr.write(message + "\n")
    sys.exit(exit_code)


# ---------------------------------------------------------------------------
# Manifest validation
# ---------------------------------------------------------------------------


def _validate_manifest(manifest: dict) -> list[str]:
    """Validate cases.json manifest structure. Returns list of errors."""
    errors: list[str] = []

    if not isinstance(manifest, dict):
        return ["Manifest is not a JSON object"]

    if manifest.get("schema_version") != 1:
        errors.append("schema_version must be 1")

    cases = manifest.get("cases")
    if not isinstance(cases, list):
        errors.append("'cases' must be an array")
        return errors

    if len(cases) != 20:
        errors.append(f"Expected 20 cases, got {len(cases)}")

    required_fields = {
        "case_id",
        "driver",
        "fixture_path",
        "fixture_sha256",
        "argv",
        "stdin_base64",
        "env",
        "expected_exit",
        "expected_stdout",
        "expected_diagnostic",
        "sentinels",
    }

    seen_ids: set[str] = set()
    for i, case in enumerate(cases):
        if not isinstance(case, dict):
            errors.append(f"Case {i}: not a JSON object")
            continue
        cid = case.get("case_id", "")
        if cid in seen_ids:
            errors.append(f"Duplicate case_id: {cid}")
        seen_ids.add(cid)

        missing = required_fields - set(case.keys())
        if missing:
            errors.append(f"Case '{cid}': missing fields: {missing}")

        driver = case.get("driver")
        if driver not in ("contract", "helper"):
            errors.append(f"Case '{cid}': invalid driver '{driver}'")

        if not isinstance(case.get("argv"), list):
            errors.append(f"Case '{cid}': argv must be a list")

        expected_exit = case.get("expected_exit")
        if not isinstance(expected_exit, int):
            errors.append(f"Case '{cid}': expected_exit must be an integer")

        if not isinstance(case.get("sentinels"), list):
            errors.append(f"Case '{cid}': sentinels must be a list")

    # Validate case_ids_sha256
    expected_ids_path = REGRESSIONS_DIR / "case-ids.txt"
    if expected_ids_path.exists():
        with open(expected_ids_path, "r") as fh:
            ids_text = fh.read()
        computed_sha = _sha256_hex(ids_text.encode("utf-8"))
        declared_sha = manifest.get("case_ids_sha256", "")
        if declared_sha != computed_sha:
            errors.append(
                f"case_ids_sha256 mismatch: declared={declared_sha}, computed={computed_sha}"
            )

    return errors


def _load_manifest() -> dict:
    manifest_path = REGRESSIONS_DIR / "cases.json"
    if not manifest_path.exists():
        _die(f"Manifest not found: {manifest_path}", 2)
    try:
        with open(manifest_path, "rb") as fh:
            return json.loads(fh.read().decode("utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        _die(f"Failed to load manifest: {e}", 2)


# ---------------------------------------------------------------------------
# Case execution
# ---------------------------------------------------------------------------


def _find_executable(argv0: str, case: dict) -> str | None:
    """Resolve the first argv element to an executable path."""
    if os.path.isabs(argv0) and os.access(argv0, os.X_OK):
        return argv0

    # Check relative to regressions directory
    candidate = str(REGRESSIONS_DIR / argv0)
    if os.access(candidate, os.X_OK):
        return candidate

    # Check relative to skill scripts
    skill_scripts = (
        SCRIPT_DIR.parent / "skills" / "address-pr-comments-review" / "scripts"
    )
    candidate = str(skill_scripts / argv0)
    if os.access(candidate, os.X_OK):
        return candidate

    # Check contract checker
    candidate = str(SCRIPT_DIR.parent / "scripts" / argv0)
    if os.access(candidate, os.X_OK):
        return candidate

    # Fallback to $PATH lookup
    candidate = shutil.which(argv0)
    if candidate:
        return candidate

    return None


def _run_case(case: dict, case_dir: Path) -> dict:
    """Execute a single regression case. Returns result dict."""
    case_id = case["case_id"]
    driver = case["driver"]
    argv = case["argv"]
    env = dict(case.get("env", {}))
    stdin_b64 = case.get("stdin_base64", "")
    expected_exit = case["expected_exit"]
    expected_diag = case.get("expected_diagnostic", "")
    sentinels = case.get("sentinels", [])

    # Resolve executable
    exe = _find_executable(argv[0], case)
    if exe is None:
        return {
            "case_id": case_id,
            "status": "skip",
            "reason": f"Executable not found: {argv[0]}",
            "exit_code": None,
            "expected_exit": expected_exit,
            "passed": False,
        }

    argv_resolved = [exe] + argv[1:]

    # Prepare stdin
    stdin_bytes = b""
    if stdin_b64:
        import base64

        stdin_bytes = base64.b64decode(stdin_b64)

    # Run
    try:
        proc = subprocess.run(
            argv_resolved,
            input=stdin_bytes,
            capture_output=True,
            timeout=30,
            env={**os.environ, **env},
            cwd=str(case_dir),
        )
    except subprocess.TimeoutExpired:
        return {
            "case_id": case_id,
            "status": "timeout",
            "reason": "Process timed out after 30s",
            "exit_code": None,
            "expected_exit": expected_exit,
            "passed": False,
        }
    except OSError as e:
        return {
            "case_id": case_id,
            "status": "error",
            "reason": f"OS error: {e}",
            "exit_code": None,
            "expected_exit": expected_exit,
            "passed": False,
        }

    exit_code = proc.returncode
    stdout_bytes = proc.stdout
    stderr_bytes = proc.stderr

    # Write outputs
    (case_dir / "stdout.bin").write_bytes(stdout_bytes)
    (case_dir / "stderr.bin").write_bytes(stderr_bytes)

    # Check exit code
    exit_ok = exit_code == expected_exit

    # Check diagnostic in stderr
    stderr_text = stderr_bytes.decode("utf-8", errors="replace")
    diag_ok = True
    actual_diag = ""
    if expected_diag:
        # Simple substring match
        diag_ok = expected_diag in stderr_text
        # Try to extract diagnostic code
        import re

        m = re.search(r'"diagnostic_code"\s*:\s*"([^"]+)"', stderr_text)
        if m:
            actual_diag = m.group(1)
            diag_ok = actual_diag == expected_diag

    # Check sentinels
    combined_text = stdout_bytes.decode("utf-8", errors="replace") + stderr_text
    sentinel_ok = True
    missing_sentinels: list[str] = []
    for s in sentinels:
        if s not in combined_text:
            sentinel_ok = False
            missing_sentinels.append(s)

    passed = exit_ok and diag_ok and sentinel_ok

    # Build log
    log = {
        "case_id": case_id,
        "driver": driver,
        "argv": argv,
        "argv_resolved": argv_resolved,
        "env": env,
        "expected_exit": expected_exit,
        "actual_exit": exit_code,
        "expected_diagnostic": expected_diag,
        "actual_diagnostic": actual_diag,
        "exit_ok": exit_ok,
        "diag_ok": diag_ok,
        "sentinel_ok": sentinel_ok,
        "missing_sentinels": missing_sentinels,
        "passed": passed,
        "stdout_sha256": _sha256_hex(stdout_bytes),
        "stderr_sha256": _sha256_hex(stderr_bytes),
    }
    (case_dir / "log.json").write_text(_format_json_bytes(log), encoding="utf-8")

    return {
        "case_id": case_id,
        "status": "run",
        "exit_code": exit_code,
        "expected_exit": expected_exit,
        "actual_diag": actual_diag,
        "missing_sentinels": missing_sentinels,
        "passed": passed,
        "exit_ok": exit_ok,
        "diag_ok": diag_ok,
        "sentinel_ok": sentinel_ok,
    }


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def _do_run(args: argparse.Namespace) -> None:
    manifest = _load_manifest()

    # Validate manifest
    errors = _validate_manifest(manifest)
    if errors:
        sys.stderr.write("Manifest validation errors:\n")
        for e in errors:
            sys.stderr.write(f"  - {e}\n")
        if args.validate_manifest_only:
            sys.exit(1)
        _die(
            "Manifest validation failed. Fix cases.json or use --validate-manifest-only.",
            2,
        )

    if args.validate_manifest_only:
        print("Manifest validation passed.")
        return

    cases = manifest["cases"]

    # Determine which cases to run
    resume_from: str | None = args.resume
    skip_until_resume = resume_from is not None
    found_resume = False

    total = 0
    passed = 0
    failed = 0
    skipped = 0

    for case in cases:
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

        # Create isolated case directory
        case_dir = CASES_DIR / case_id
        case_dir.mkdir(parents=True, exist_ok=True)

        # Run case
        result = _run_case(case, case_dir)
        total += 1

        if result["passed"]:
            passed += 1
            print(f"  PASS: {case_id}")
        else:
            failed += 1
            reason_parts = []
            if not result.get("exit_ok", False):
                reason_parts.append(
                    f"exit={result['exit_code']} (expected {result['expected_exit']})"
                )
            if not result.get("diag_ok", False):
                reason_parts.append(
                    f"diag={result.get('actual_diag', '?')} (expected {case.get('expected_diagnostic', '')})"
                )
            if not result.get("sentinel_ok", False):
                reason_parts.append(
                    f"missing sentinels: {result.get('missing_sentinels', [])}"
                )
            reason = (
                "; ".join(reason_parts)
                if reason_parts
                else result.get("reason", "unknown")
            )
            print(f"  FAIL: {case_id} ({reason})")

    print(f"\ntotal={total} passed={passed} failed={failed} skipped={skipped}")

    if not found_resume and resume_from:
        _die(f"Resume point '{resume_from}' not found in manifest", 2)

    if failed > 0:
        sys.exit(1)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Deterministic regression runner for address-pr-comments-review"
    )
    parser.add_argument(
        "--resume",
        type=str,
        default=None,
        help="Resume from a specific case_id",
    )
    parser.add_argument(
        "--validate-manifest-only",
        action="store_true",
        help="Only validate the manifest, do not run cases",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        _do_run(args)
    except OSError as e:
        _die(f"I/O error: {e}", 4)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
