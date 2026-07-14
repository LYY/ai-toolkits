#!/usr/bin/env python3
"""Final report validator for address-pr-comments-review eval.

Validates final reports against F1-F4 criteria. Supports the full wave
lifecycle: build manifest, open generation, seal generation, open wave,
close wave, record launch, build prompts, prepare final receipt,
validate report, aggregate, run commands, finalize wave, supersede generation.

Arguments:
  --build-manifest         Build report manifest from criteria
  --open-generation        Open a new generation
  --seal-generation        Seal current generation
  --open-wave              Open an evaluation wave
  --close-wave             Close current wave
  --record-launch          Record a launch event
  --build-prompts          Build neutral executor prompts
  --prepare-final-receipt  Prepare final receipt
  --validate-report        Validate a report file
  --aggregate              Aggregate wave results
  --run-commands           Run evaluation commands
  --finalize-wave          Finalize current wave
  --supersede-generation   Supersede current generation

stdlib only. No external dependencies.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import sys
import uuid
from pathlib import Path
from typing import NoReturn

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA_VERSION = 1
ATTEMPT_ID = "678a49cb-f4e9-4d72-9d53-f1730d607103"

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
REGRESSIONS_DIR = REPO_ROOT / "tests" / "address-pr-comments-review-regressions"
STATE_DIR = Path.home() / ".local" / "state" / "ai-toolkits" / "eval" / ATTEMPT_ID

VALID_FLAGS = frozenset(
    {
        "--build-manifest",
        "--open-generation",
        "--seal-generation",
        "--open-wave",
        "--close-wave",
        "--record-launch",
        "--build-prompts",
        "--prepare-final-receipt",
        "--validate-report",
        "--aggregate",
        "--run-commands",
        "--finalize-wave",
        "--supersede-generation",
    }
)

F1_CRITERIA_IDS = [
    "F1-MH-01",
    "F1-MH-02",
    "F1-MH-03",
    "F1-MH-04",
    "F1-MH-05",
    "F1-MH-06",
    "F1-MH-07",
    "F1-MH-08",
    "F1-MH-09",
    "F1-MH-10",
    "F1-MH-11",
    "F1-MN-01",
    "F1-MN-02",
    "F1-MN-03",
    "F1-MN-04",
    "F1-MN-05",
    "F1-MN-06",
    "F1-MN-07",
    "F1-T01",
    "F1-T02",
    "F1-T03",
    "F1-T04",
    "F1-T05",
    "F1-T06",
    "F1-T07",
    "F1-T08",
    "F1-T09",
    "F1-T10",
    "F1-T11",
    "F1-SC-01",
    "F1-SC-02",
    "F1-SC-03",
    "F1-SC-04",
    "F1-SC-05",
    "F1-SC-06",
]

F2_CRITERIA_IDS = [
    "F2-LIFECYCLE",
    "F2-IDEMPOTENCY",
    "F2-CLEANUP",
    "F2-REMOTE-SHA",
    "F2-ERROR-OBSERVABILITY",
    "F2-TEST-QUALITY",
]

F3_CRITERIA_IDS = [
    "F3-RED-20",
    "F3-GREEN-20",
    "F3-REGRESSION-20",
    "F3-HAPPY-FAMILIES",
    "F3-FAILURE-FAMILIES",
    "F3-SIDE-EFFECT-SENTINELS",
]

F4_CRITERIA_IDS = [
    "F4-WRITABLE-MANIFEST",
    "F4-DIRTY-BASELINE",
    "F4-FORBIDDEN-SCOPE",
    "F4-COLLECTOR-BODY",
    "F4-NO-COMMIT-PUSH-SYNC",
    "F4-SOURCE-MANIFEST-STABLE",
]

ALL_CRITERIA_IDS = F1_CRITERIA_IDS + F2_CRITERIA_IDS + F3_CRITERIA_IDS + F4_CRITERIA_IDS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _uuid4() -> str:
    return str(uuid.uuid4())


def _now_rfc3339() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _die(message: str, exit_code: int = 2) -> NoReturn:
    sys.stderr.write(message + "\n")
    sys.exit(exit_code)


def _load_criteria() -> dict:
    """Load final-criteria.json."""
    path = REGRESSIONS_DIR / "final-criteria.json"
    if not path.exists():
        _die(f"Criteria file not found: {path}", 2)
    with open(path, "rb") as fh:
        return json.loads(fh.read().decode("utf-8"))


def _load_manifest() -> dict:
    """Load cases.json manifest."""
    path = REGRESSIONS_DIR / "cases.json"
    if not path.exists():
        _die(f"Manifest not found: {path}", 2)
    with open(path, "rb") as fh:
        return json.loads(fh.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# State management
# ---------------------------------------------------------------------------


def _ensure_state_dir() -> Path:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    return STATE_DIR


def _read_state() -> dict:
    state_file = STATE_DIR / "state.json"
    if not state_file.exists():
        return {
            "schema_version": SCHEMA_VERSION,
            "attempt_id": ATTEMPT_ID,
            "generations": [],
            "waves": [],
            "current_generation": None,
            "current_wave": None,
        }
    with open(state_file, "rb") as fh:
        return json.loads(fh.read().decode("utf-8"))


def _write_state(state: dict) -> None:
    _ensure_state_dir()
    state_file = STATE_DIR / "state.json"
    state_bytes = _canonical_json_bytes(state)
    tmp = state_file.with_suffix(".tmp")
    tmp.write_bytes(state_bytes)
    tmp.rename(state_file)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def _cmd_build_manifest(args: argparse.Namespace) -> None:
    """Build a report manifest from criteria definitions."""
    criteria = _load_criteria()
    manifest = _load_manifest()

    report_manifest = {
        "schema_version": SCHEMA_VERSION,
        "attempt_id": ATTEMPT_ID,
        "built_at": _now_rfc3339(),
        "criteria_count": len(criteria.get("criteria", [])),
        "aggregate_count": len(criteria.get("aggregate_criteria", [])),
        "case_count": len(manifest.get("cases", [])),
        "entry_points": ["run_address_pr_comments_review_regressions.py"],
        "scripts": [
            "run_address_pr_comments_review_regressions.py",
            "validate-address-pr-comments-review-final.py",
        ],
        "required_flags": sorted(VALID_FLAGS),
    }

    output_path = STATE_DIR / "report-manifest.json"
    _ensure_state_dir()
    output_path.write_text(_format_json_bytes(report_manifest), encoding="utf-8")
    print(_format_json_bytes(report_manifest), end="", flush=True)


def _cmd_open_generation(args: argparse.Namespace) -> None:
    """Open a new generation."""
    state = _read_state()
    generation_id = _uuid4()
    generation = {
        "generation_id": generation_id,
        "opened_at": _now_rfc3339(),
        "sealed_at": None,
        "status": "open",
    }
    state["generations"].append(generation)
    state["current_generation"] = generation_id
    _write_state(state)

    result = {
        "schema_version": SCHEMA_VERSION,
        "operation": "open-generation",
        "generation_id": generation_id,
        "status": "opened",
    }
    print(_format_json_bytes(result), end="", flush=True)


def _cmd_seal_generation(args: argparse.Namespace) -> None:
    """Seal current generation."""
    state = _read_state()
    gen_id = state.get("current_generation")
    if not gen_id:
        _die("No open generation to seal", 2)

    for gen in state["generations"]:
        if gen["generation_id"] == gen_id:
            gen["sealed_at"] = _now_rfc3339()
            gen["status"] = "sealed"
            break

    state["current_generation"] = None
    _write_state(state)

    result = {
        "schema_version": SCHEMA_VERSION,
        "operation": "seal-generation",
        "generation_id": gen_id,
        "status": "sealed",
    }
    print(_format_json_bytes(result), end="", flush=True)


def _cmd_open_wave(args: argparse.Namespace) -> None:
    """Open an evaluation wave."""
    state = _read_state()
    wave_id = _uuid4()
    wave = {
        "wave_id": wave_id,
        "opened_at": _now_rfc3339(),
        "closed_at": None,
        "status": "open",
    }
    state["waves"].append(wave)
    state["current_wave"] = wave_id
    _write_state(state)

    result = {
        "schema_version": SCHEMA_VERSION,
        "operation": "open-wave",
        "wave_id": wave_id,
        "status": "opened",
    }
    print(_format_json_bytes(result), end="", flush=True)


def _cmd_close_wave(args: argparse.Namespace) -> None:
    """Close current wave."""
    state = _read_state()
    wave_id = state.get("current_wave")
    if not wave_id:
        _die("No open wave to close", 2)

    for wave in state["waves"]:
        if wave["wave_id"] == wave_id:
            wave["closed_at"] = _now_rfc3339()
            wave["status"] = "closed"
            break

    state["current_wave"] = None
    _write_state(state)

    result = {
        "schema_version": SCHEMA_VERSION,
        "operation": "close-wave",
        "wave_id": wave_id,
        "status": "closed",
    }
    print(_format_json_bytes(result), end="", flush=True)


def _cmd_record_launch(args: argparse.Namespace) -> None:
    """Record a launch event."""
    state = _read_state()
    launch_id = _uuid4()

    launch_record = {
        "launch_id": launch_id,
        "recorded_at": _now_rfc3339(),
        "generation_id": state.get("current_generation"),
        "wave_id": state.get("current_wave"),
    }
    output_path = STATE_DIR / "launches.jsonl"
    _ensure_state_dir()
    with open(output_path, "a") as fh:
        fh.write(
            json.dumps(launch_record, separators=(",", ":"), ensure_ascii=False) + "\n"
        )

    result = {
        "schema_version": SCHEMA_VERSION,
        "operation": "record-launch",
        "launch_id": launch_id,
        "status": "recorded",
    }
    print(_format_json_bytes(result), end="", flush=True)


def _cmd_build_prompts(args: argparse.Namespace) -> None:
    """Build neutral executor prompts from criteria."""
    criteria = _load_criteria()
    prompts: dict[str, str] = {}

    for crit in criteria.get("criteria", []):
        cid = crit.get("criterion_id", "")
        desc = crit.get("description", "")
        prompts[cid] = f"Verify criterion {cid}: {desc}"

    output_path = STATE_DIR / "prompts.json"
    _ensure_state_dir()
    output_path.write_text(_format_json_bytes(prompts), encoding="utf-8")

    result = {
        "schema_version": SCHEMA_VERSION,
        "operation": "build-prompts",
        "prompt_count": len(prompts),
        "status": "built",
    }
    print(_format_json_bytes(result), end="", flush=True)


def _cmd_prepare_final_receipt(args: argparse.Namespace) -> None:
    """Prepare final receipt for an evaluation run."""
    receipt_id = _uuid4()
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "receipt_id": receipt_id,
        "attempt_id": ATTEMPT_ID,
        "prepared_at": _now_rfc3339(),
        "state_snapshot": _read_state(),
    }
    output_path = STATE_DIR / "final-receipt.json"
    _ensure_state_dir()
    output_path.write_text(_format_json_bytes(receipt), encoding="utf-8")

    result = {
        "schema_version": SCHEMA_VERSION,
        "operation": "prepare-final-receipt",
        "receipt_id": receipt_id,
        "status": "prepared",
    }
    print(_format_json_bytes(result), end="", flush=True)


def _cmd_validate_report(args: argparse.Namespace) -> None:
    """Validate a report against criteria."""
    report_path = args.report if hasattr(args, "report") and args.report else None
    if not report_path:
        _die("--validate-report requires --report PATH", 2)

    try:
        with open(report_path, "rb") as fh:
            report = json.loads(fh.read().decode("utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        _die(f"Cannot read report: {e}", 2)

    errors: list[str] = []
    if report.get("schema_version") != SCHEMA_VERSION:
        errors.append(
            f"schema_version {report.get('schema_version')} != {SCHEMA_VERSION}"
        )

    criteria = _load_criteria()
    declared_cids = {c.get("criterion_id") for c in criteria.get("criteria", [])}
    reported_cids = set()
    if isinstance(report.get("results"), list):
        for r in report["results"]:
            if isinstance(r, dict) and "criterion_id" in r:
                reported_cids.add(r["criterion_id"])

    missing = declared_cids - reported_cids
    if missing:
        errors.append(f"Missing criteria in report: {missing}")

    if errors:
        result = {
            "schema_version": SCHEMA_VERSION,
            "operation": "validate-report",
            "status": "invalid",
            "errors": errors,
        }
        print(_format_json_bytes(result), end="", flush=True)
        sys.exit(1)
    else:
        result = {
            "schema_version": SCHEMA_VERSION,
            "operation": "validate-report",
            "status": "valid",
        }
        print(_format_json_bytes(result), end="", flush=True)


def _cmd_aggregate(args: argparse.Namespace) -> None:
    """Aggregate wave results."""
    criteria = _load_criteria()
    state = _read_state()

    aggregated = {
        "schema_version": SCHEMA_VERSION,
        "attempt_id": ATTEMPT_ID,
        "aggregated_at": _now_rfc3339(),
        "wave_id": state.get("current_wave"),
        "generation_id": state.get("current_generation"),
        "families": {
            "F1": {
                "total": len(F1_CRITERIA_IDS),
                "passed": 0,
                "failed": 0,
                "criteria": F1_CRITERIA_IDS,
            },
            "F2": {
                "total": len(F2_CRITERIA_IDS),
                "passed": 0,
                "failed": 0,
                "criteria": F2_CRITERIA_IDS,
            },
            "F3": {
                "total": len(F3_CRITERIA_IDS),
                "passed": 0,
                "failed": 0,
                "criteria": F3_CRITERIA_IDS,
            },
            "F4": {
                "total": len(F4_CRITERIA_IDS),
                "passed": 0,
                "failed": 0,
                "criteria": F4_CRITERIA_IDS,
            },
        },
    }

    output_path = STATE_DIR / "aggregated.json"
    _ensure_state_dir()
    output_path.write_text(_format_json_bytes(aggregated), encoding="utf-8")

    result = {
        "schema_version": SCHEMA_VERSION,
        "operation": "aggregate",
        "status": "aggregated",
    }
    print(_format_json_bytes(result), end="", flush=True)


def _cmd_run_commands(args: argparse.Namespace) -> None:
    """Run evaluation commands (dry-run listing)."""
    runner_path = REPO_ROOT / "tests" / "run_address_pr_comments_review_regressions.py"

    commands = [
        f"python3 {runner_path} --validate-manifest-only",
        f"python3 {runner_path}",
        f"python3 {runner_path} --resume route-review-dossier",
    ]

    result = {
        "schema_version": SCHEMA_VERSION,
        "operation": "run-commands",
        "commands": commands,
        "status": "listed",
    }
    print(_format_json_bytes(result), end="", flush=True)


def _cmd_finalize_wave(args: argparse.Namespace) -> None:
    """Finalize current wave with summary."""
    state = _read_state()
    wave_id = state.get("current_wave")
    if not wave_id:
        _die("No open wave to finalize", 2)

    result = {
        "schema_version": SCHEMA_VERSION,
        "operation": "finalize-wave",
        "wave_id": wave_id,
        "attempt_id": ATTEMPT_ID,
        "status": "finalized",
        "finalized_at": _now_rfc3339(),
    }
    print(_format_json_bytes(result), end="", flush=True)


def _cmd_supersede_generation(args: argparse.Namespace) -> None:
    """Supersede current generation with a new one."""
    state = _read_state()
    old_gen = state.get("current_generation")
    new_gen_id = _uuid4()

    generation = {
        "generation_id": new_gen_id,
        "opened_at": _now_rfc3339(),
        "sealed_at": None,
        "status": "open",
        "supersedes": old_gen,
    }
    state["generations"].append(generation)
    state["current_generation"] = new_gen_id
    _write_state(state)

    result = {
        "schema_version": SCHEMA_VERSION,
        "operation": "supersede-generation",
        "new_generation_id": new_gen_id,
        "superseded": old_gen,
        "status": "superseded",
    }
    print(_format_json_bytes(result), end="", flush=True)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def _dispatch(args: argparse.Namespace) -> None:
    """Route to the appropriate command handler."""
    flags = set(getattr(args, "flags", []) or [])

    if args.build_manifest or "--build-manifest" in flags:
        _cmd_build_manifest(args)
    elif args.open_generation or "--open-generation" in flags:
        _cmd_open_generation(args)
    elif args.seal_generation or "--seal-generation" in flags:
        _cmd_seal_generation(args)
    elif args.open_wave or "--open-wave" in flags:
        _cmd_open_wave(args)
    elif args.close_wave or "--close-wave" in flags:
        _cmd_close_wave(args)
    elif args.record_launch or "--record-launch" in flags:
        _cmd_record_launch(args)
    elif args.build_prompts or "--build-prompts" in flags:
        _cmd_build_prompts(args)
    elif args.prepare_final_receipt or "--prepare-final-receipt" in flags:
        _cmd_prepare_final_receipt(args)
    elif args.validate_report or "--validate-report" in flags:
        _cmd_validate_report(args)
    elif args.aggregate or "--aggregate" in flags:
        _cmd_aggregate(args)
    elif args.run_commands or "--run-commands" in flags:
        _cmd_run_commands(args)
    elif args.finalize_wave or "--finalize-wave" in flags:
        _cmd_finalize_wave(args)
    elif args.supersede_generation or "--supersede-generation" in flags:
        _cmd_supersede_generation(args)
    else:
        _die("No valid command flag specified. Use --help for usage.", 2)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Final report validator for address-pr-comments-review eval"
    )
    parser.add_argument(
        "--build-manifest",
        action="store_true",
        help="Build report manifest from criteria",
    )
    parser.add_argument(
        "--open-generation",
        action="store_true",
        help="Open a new generation",
    )
    parser.add_argument(
        "--seal-generation",
        action="store_true",
        help="Seal current generation",
    )
    parser.add_argument(
        "--open-wave",
        action="store_true",
        help="Open an evaluation wave",
    )
    parser.add_argument(
        "--close-wave",
        action="store_true",
        help="Close current wave",
    )
    parser.add_argument(
        "--record-launch",
        action="store_true",
        help="Record a launch event",
    )
    parser.add_argument(
        "--build-prompts",
        action="store_true",
        help="Build neutral executor prompts",
    )
    parser.add_argument(
        "--prepare-final-receipt",
        action="store_true",
        help="Prepare final receipt",
    )
    parser.add_argument(
        "--validate-report",
        action="store_true",
        help="Validate a report file",
    )
    parser.add_argument(
        "--report",
        type=str,
        default=None,
        help="Path to report JSON for --validate-report",
    )
    parser.add_argument(
        "--aggregate",
        action="store_true",
        help="Aggregate wave results",
    )
    parser.add_argument(
        "--run-commands",
        action="store_true",
        help="Run evaluation commands",
    )
    parser.add_argument(
        "--finalize-wave",
        action="store_true",
        help="Finalize current wave",
    )
    parser.add_argument(
        "--supersede-generation",
        action="store_true",
        help="Supersede current generation",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        _dispatch(args)
    except OSError as e:
        _die(f"I/O error: {e}", 4)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
