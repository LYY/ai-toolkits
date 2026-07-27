from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import TypedDict

from .address_pr_comments_review_manifest import RegressionCase


SCRIPT_DIR = Path(__file__).resolve().parent
REGRESSIONS_DIR = SCRIPT_DIR / "address-pr-comments-review-regressions"
CASES_DIR = REGRESSIONS_DIR / "cases"


class RunResultBase(TypedDict):
    case_id: str
    status: str
    exit_code: int | None
    expected_exit: int
    passed: bool


class RunResult(RunResultBase, total=False):
    reason: str
    actual_diag: str
    missing_sentinels: list[str]
    exit_ok: bool
    diag_ok: bool
    sentinel_ok: bool


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _format_json_bytes(value: dict[str, str | int | bool | list[str]]) -> str:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    )


def _find_executable(argv0: str) -> str | None:
    if os.path.isabs(argv0) and os.access(argv0, os.X_OK):
        return argv0
    candidates = (
        REGRESSIONS_DIR / argv0,
        SCRIPT_DIR.parent / "skills" / "address-pr-comments-review" / "scripts" / argv0,
        SCRIPT_DIR.parent / "scripts" / argv0,
    )
    for candidate in candidates:
        if os.access(candidate, os.X_OK):
            return str(candidate)
    return shutil.which(argv0)


def _resolve_argument(value: str) -> str:
    if os.path.isabs(value):
        return value
    script_dirs = (
        REGRESSIONS_DIR,
        SCRIPT_DIR.parent / "skills" / "address-pr-comments-review" / "scripts",
        SCRIPT_DIR.parent / "scripts",
    )
    for script_dir in script_dirs:
        candidate = script_dir / value
        if candidate.is_file():
            return str(candidate)
    return value


def _resolve_artifact_path(value: str, case_dir: Path) -> str:
    if value.startswith("/readonly/"):
        artifact_dir = case_dir / "readonly"
        artifact_dir.mkdir(exist_ok=True)
        artifact_dir.chmod(0o500)
    else:
        artifact_dir = case_dir / "artifacts"
    artifact_dir.mkdir(exist_ok=True)
    return str(artifact_dir / Path(value).name)


def _resolve_case_argv(case: RegressionCase, case_dir: Path) -> list[str] | None:
    argv = case["argv"]
    executable = _find_executable(argv[0])
    if executable is None:
        return None
    resolved = [executable]
    artifact_path_next = False
    for value in argv[1:]:
        if artifact_path_next:
            resolved.append(_resolve_artifact_path(value, case_dir))
            artifact_path_next = False
        else:
            resolved.append(_resolve_argument(value))
            artifact_path_next = value == "--artifact"
    if case["driver"] == "contract":
        resolved.append(str(SCRIPT_DIR.parent))
    return resolved


def run_case(case: RegressionCase, case_dir: Path) -> RunResult:
    case_id = case["case_id"]
    argv = case["argv"]
    expected_exit = case["expected_exit"]
    resolved = _resolve_case_argv(case, case_dir)
    if resolved is None:
        return {
            "case_id": case_id,
            "status": "skip",
            "reason": f"Executable not found: {argv[0]}",
            "exit_code": None,
            "expected_exit": expected_exit,
            "passed": False,
        }
    stdin_bytes = (
        base64.b64decode(case["stdin_base64"]) if case["stdin_base64"] else b""
    )
    try:
        process = subprocess.run(
            resolved,
            input=stdin_bytes,
            capture_output=True,
            timeout=30,
            env={**os.environ, **case["env"]},
            cwd=case_dir,
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
    except OSError as error:
        return {
            "case_id": case_id,
            "status": "error",
            "reason": f"OS error: {error}",
            "exit_code": None,
            "expected_exit": expected_exit,
            "passed": False,
        }

    stdout_bytes = process.stdout
    stderr_bytes = process.stderr
    _ = (case_dir / "stdout.bin").write_bytes(stdout_bytes)
    _ = (case_dir / "stderr.bin").write_bytes(stderr_bytes)
    exit_ok = process.returncode == expected_exit
    stderr_text = stderr_bytes.decode("utf-8", errors="replace")
    expected_diagnostic = case["expected_diagnostic"]
    diagnostic_ok = True
    actual_diagnostic = ""
    if expected_diagnostic:
        diagnostic_ok = expected_diagnostic in stderr_text
        match = re.search(r'"diagnostic_code"\s*:\s*"([^"]+)"', stderr_text)
        if match:
            actual_diagnostic = match.group(1)
            diagnostic_ok = actual_diagnostic == expected_diagnostic
    combined_text = stdout_bytes.decode("utf-8", errors="replace") + stderr_text
    missing_sentinels = [
        sentinel for sentinel in case["sentinels"] if sentinel not in combined_text
    ]
    sentinel_ok = not missing_sentinels
    passed = exit_ok and diagnostic_ok and sentinel_ok
    log: dict[str, str | int | bool | list[str]] = {
        "case_id": case_id,
        "driver": case["driver"],
        "argv": argv,
        "argv_resolved": resolved,
        "env": [f"{key}={value}" for key, value in sorted(case["env"].items())],
        "expected_exit": expected_exit,
        "actual_exit": process.returncode,
        "expected_diagnostic": expected_diagnostic,
        "actual_diagnostic": actual_diagnostic,
        "exit_ok": exit_ok,
        "diag_ok": diagnostic_ok,
        "sentinel_ok": sentinel_ok,
        "missing_sentinels": missing_sentinels,
        "passed": passed,
        "stdout_sha256": _sha256_hex(stdout_bytes),
        "stderr_sha256": _sha256_hex(stderr_bytes),
    }
    _ = (case_dir / "log.json").write_text(_format_json_bytes(log), encoding="utf-8")
    return {
        "case_id": case_id,
        "status": "run",
        "exit_code": process.returncode,
        "expected_exit": expected_exit,
        "actual_diag": actual_diagnostic,
        "missing_sentinels": missing_sentinels,
        "passed": passed,
        "exit_ok": exit_ok,
        "diag_ok": diagnostic_ok,
        "sentinel_ok": sentinel_ok,
    }
