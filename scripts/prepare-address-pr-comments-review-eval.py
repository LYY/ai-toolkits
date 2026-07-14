#!/usr/bin/env python3
"""Receipt and Score CLIs for address-pr-comments-review executor-neutral eval.

Receipt CLI (--receipt):
  Parses a session-read-v2 transcript and emits a Local Receipt.

Score CLI (--score):
  Reads a task() response JSON and emits mechanical Score verdicts (EN-01–EN-05).

stdlib only. No external dependencies.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import sys
import uuid
from typing import NoReturn


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA_VERSION = 1
TRANSCRIPT_FORMAT = "session-read-v2"
ADAPTER_CONTRACT = "task-explore-v1"

ALLOWED_TOOL_NAMES: set[str] = {
    "read",
    "grep",
    "glob",
    "lsp_diagnostics",
    "lsp_symbols",
    "lsp_goto_definition",
    "lsp_find_references",
    "codegraph_codegraph_explore",
    "code-review-graph_get_minimal_context_tool",
    "code-review-graph_semantic_search_nodes_tool",
    "code-review-graph_query_graph_tool",
}

# ---------------------------------------------------------------------------
# Hashing helpers
# ---------------------------------------------------------------------------


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha256(path: str) -> str:
    with open(path, "rb") as fh:
        return _sha256_hex(fh.read())


# ---------------------------------------------------------------------------
# Canonical JSON
# ---------------------------------------------------------------------------


def _canonical_json(obj: object) -> bytes:
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return (text + "\n").encode("utf-8")


def _format_json_bytes(obj: object) -> str:
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return text + "\n"


# ---------------------------------------------------------------------------
# Error helpers
# ---------------------------------------------------------------------------


def _die(message: str, exit_code: int = 2) -> NoReturn:
    sys.stderr.write(message + "\n")
    sys.exit(exit_code)


# ---------------------------------------------------------------------------
# Text normalization (same algorithm as plan normalization in attempt mgr)
# ---------------------------------------------------------------------------


def _canonicalize_text(raw: str) -> bytes:
    """Normalize: CRLF→LF, CR→LF, strip trailing space/tab per line,
    trim outer blank lines, append one LF."""
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    lines = [line.rstrip(" \t") for line in lines]
    while lines and lines[0] == "":
        lines.pop(0)
    while lines and lines[-1] == "":
        lines.pop()
    result = "\n".join(lines)
    if result:
        result += "\n"
    return result.encode("utf-8")


# ---------------------------------------------------------------------------
# Transcript parsing: session-read-v2 grammar
# ---------------------------------------------------------------------------

_ROLE_RE = re.compile(r"^\[(user|assistant) \(([^\]]+)\)\] ([^\n]*)$")
_TOOL_RE = re.compile(r"^\[tool: ([A-Za-z0-9_.-]+)\][ \t]*$")

# Ordered events from transcript
_Event = tuple[str, str | None]  # (kind, data)
# kind: "user_header" | "assistant_header" | "tool_header" | "body_line"
# data: role/toolname + timestamp | body text


def _parse_transcript(path: str) -> list[dict]:
    """Parse session-read-v2 transcript into ordered sections.

    Returns list of sections, each:
      {"kind": "user"|"assistant"|"tool", "timestamp": str|None,
       "body_lines": [str], "tool_name": str|None}
    """
    with open(path, "rb") as fh:
        raw = fh.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        _die(f"Transcript is not valid UTF-8: {e}", 2)

    lines = text.split("\n")
    sections: list[dict] = []
    current: dict | None = None

    for line in lines:
        # Check role header
        rm = _ROLE_RE.match(line)
        if rm:
            if current is not None:
                sections.append(current)
            role = rm.group(1)
            ts = rm.group(2)
            msg = rm.group(3)
            body: list[str] = []
            if msg:
                body.append(msg)
            current = {
                "kind": role,
                "timestamp": ts,
                "body_lines": body,
                "tool_name": None,
            }
            continue

        # Check tool header
        tm = _TOOL_RE.match(line)
        if tm:
            if current is not None:
                sections.append(current)
            tool_name = tm.group(1)
            current = {
                "kind": "tool",
                "timestamp": None,
                "body_lines": [],
                "tool_name": tool_name,
            }
            continue

        # Body line
        if current is not None:
            current["body_lines"].append(line)
        # else: leading lines before first header — ignore

    if current is not None:
        sections.append(current)

    return sections


def _build_tool_events(sections: list[dict]) -> list[dict]:
    """Build tool_events list from sections: [{ordinal, name}] for each tool invocation."""
    events: list[dict] = []
    ordinal = 0
    for sec in sections:
        if sec["kind"] == "tool":
            ordinal += 1
            if sec["tool_name"] not in ALLOWED_TOOL_NAMES:
                _die(
                    f"Disallowed tool name at ordinal {ordinal}: {sec['tool_name']}", 2
                )
            events.append({"ordinal": ordinal, "name": sec["tool_name"]})
    return events


# ---------------------------------------------------------------------------
# Receipt CLI
# ---------------------------------------------------------------------------


def _do_receipt(args: argparse.Namespace) -> None:
    phase: str = args.phase
    case_id: str = args.case_id
    ordinal: int = args.ordinal
    description: str = args.description
    task_id: str = args.task_id
    session_id: str = args.session_id
    prompt_path: str = (
        args.prompt
    )  # kept for CLI compat, not used (we parse transcript)
    response_path: str = args.response  # kept for CLI compat
    transcript_path: str = args.transcript
    output_path: str = args.output

    # Parse transcript
    sections = _parse_transcript(transcript_path)

    # Extract user bodies and assistant bodies
    user_bodies: list[str] = []
    assistant_bodies: list[str] = []
    for sec in sections:
        body = "\n".join(sec["body_lines"])
        if sec["kind"] == "user":
            user_bodies.append(body)
        elif sec["kind"] == "assistant":
            assistant_bodies.append(body)

    if not user_bodies:
        _die("No user message found in transcript", 2)
    if not assistant_bodies:
        _die("No assistant message found in transcript", 2)

    prompt_raw = user_bodies[0]
    response_raw = assistant_bodies[-1]

    # Tool events
    tool_events = _build_tool_events(sections)

    # Probe phase guards
    if phase == "probe":
        if ordinal == 1 and len(tool_events) != 0:
            _die("P1 (ordinal=1, probe) requires zero tool events", 2)
        if ordinal == 2:
            read_events = [e for e in tool_events if e["name"] == "read"]
            if not read_events:
                _die("P2 (ordinal=2, probe) requires at least one 'read' tool", 2)

    # Hashes
    prompt_raw_sha = _sha256_hex(prompt_raw.encode("utf-8"))
    prompt_canonical = _canonicalize_text(prompt_raw)
    prompt_canonical_sha = _sha256_hex(prompt_canonical)
    delivered_user_sha = (
        prompt_canonical_sha  # executor-neutral: same as prompt canonical
    )

    response_raw_sha = _sha256_hex(response_raw.encode("utf-8"))
    response_canonical = _canonicalize_text(response_raw)
    response_canonical_sha = _sha256_hex(response_canonical)

    tool_events_sha = _sha256_hex(_canonical_json(tool_events))

    transcript_raw_sha = _file_sha256(transcript_path)

    # Timestamps
    started_at: str | None = None
    finished_at: str | None = None
    for sec in sections:
        ts = sec.get("timestamp")
        if ts:
            if started_at is None:
                started_at = ts
            finished_at = ts
    # Also check for tool sections (they don't have timestamps) — use adjacent timestamps
    # Section order is preserved, so first timestamp is earliest, last is latest
    if started_at is None:
        _die("No timestamp found in transcript", 2)
    # Normalize to RFC3339: session-read-v2 timestamps are already RFC3339-ish
    # If missing timezone, assume UTC
    if finished_at is None:
        finished_at = started_at

    receipt = {
        "schema_version": SCHEMA_VERSION,
        "transcript_format": TRANSCRIPT_FORMAT,
        "adapter_contract_version": ADAPTER_CONTRACT,
        "description": description,
        "run_id": str(uuid.uuid4()),
        "phase": phase,
        "case_id": case_id,
        "ordinal": ordinal,
        "task_id": task_id,
        "session_id": session_id,
        "prompt_raw_sha256": prompt_raw_sha,
        "prompt_canonical_sha256": prompt_canonical_sha,
        "delivered_user_sha256": delivered_user_sha,
        "response_raw_sha256": response_raw_sha,
        "response_canonical_sha256": response_canonical_sha,
        "tool_events_sha256": tool_events_sha,
        "transcript_raw_sha256": transcript_raw_sha,
        "started_at": started_at,
        "finished_at": finished_at,
    }

    receipt_bytes = _canonical_json(receipt)

    # Ensure output directory exists
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(output_path, "wb") as fh:
        fh.write(receipt_bytes)

    # stdout: canonical JSON of receipt
    sys.stdout.buffer.write(receipt_bytes)
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# Score CLI
# ---------------------------------------------------------------------------

# Forbidden casefold words checked with ASCII identifier boundaries
_FORBIDDEN_CASEFOLD_WORDS = re.compile(
    r"\b(opencode|omo|prometheus|sisyphus)\b", re.IGNORECASE
)

# Case-sensitive forbidden substrings
_FORBIDDEN_SUBSTRINGS: list[str] = [
    "/start-work",
    ".omo/",
    ".sisyphus/",
    "platform.md",
    "generated plan",
    "planner prompt",
    "task-explore-v1",
    "subagent_type",
    "task_id",
    "session_id",
    "model_id",
    "provider_id",
    "harness_version",
]

_EN_EXPECTED: dict[str, tuple[list[str], list[str]]] = {
    "complex-dossier": (["review-dossier"], ["review-dossier"]),
    "direct-fix-fallback": (["review-dossier"], ["review-dossier"]),
    "interrupted-recovery": (["review-dossier"], ["review-dossier"]),
    "neutral-handoff": (
        sorted(["direct-fix", "no-action", "reply-only", "review-dossier"]),
        sorted(["direct-fix-brief", "review-dossier"]),
    ),
}

_EN03_ORDER = ["edit", "verify", "commit", "remote-reachability", "reply", "read-back"]


def _check_en01(runtime_specific_terms: list, response_text: str) -> tuple[str, str]:
    """EN-01: Check runtime_specific_terms is empty and no forbidden tokens."""
    if runtime_specific_terms != []:
        return ("FAIL", "forbidden-term")

    # Casefold word check
    cf_match = _FORBIDDEN_CASEFOLD_WORDS.search(response_text)
    if cf_match:
        return ("FAIL", "forbidden-term")

    # Case-sensitive substring check
    for sub in _FORBIDDEN_SUBSTRINGS:
        if sub in response_text:
            return ("FAIL", "forbidden-term")

    return ("PASS", "ok")


def _check_en02(case_id: str, routes: list, artifacts: list) -> tuple[str | None, str]:
    """EN-02: Check routes and artifacts match expected for case_id."""
    expected = _EN_EXPECTED.get(case_id)
    if expected is None:
        return (None, "ok")  # skip if case_id not in expected set

    exp_routes, exp_artifacts = expected

    # For neutral-handoff, we sort and compare; for others, exact match
    if case_id == "neutral-handoff":
        actual_routes = sorted(routes)
        actual_artifacts = sorted(artifacts)
    else:
        actual_routes = routes
        actual_artifacts = artifacts

    if actual_routes != exp_routes:
        return ("FAIL", "route-mismatch")
    if actual_artifacts != exp_artifacts:
        return ("FAIL", "artifact-mismatch")

    return ("PASS", "ok")


def _check_en03(section_a_order: list, push_authorized: bool) -> tuple[str, str]:
    """EN-03: Check section_a_order and push_authorized."""
    if section_a_order != _EN03_ORDER:
        return ("FAIL", "order-mismatch")
    if push_authorized is not False:
        return ("FAIL", "push-authorized")
    return ("PASS", "ok")


def _check_en04(recovery: dict) -> tuple[str, str]:
    """EN-04: Check recovery fields: stable_ids, cas, read_back, cleanup_blocks_incomplete."""
    stable_ids = recovery.get("stable_ids")
    cas = recovery.get("cas")
    read_back = recovery.get("read_back")
    cleanup = recovery.get("cleanup_blocks_incomplete")

    if stable_ids is not True:
        return ("FAIL", "recovery-mismatch")
    if cas is not True:
        return ("FAIL", "recovery-mismatch")
    if read_back is not True:
        return ("FAIL", "recovery-mismatch")
    if cleanup is not True:
        return ("FAIL", "recovery-mismatch")
    return ("PASS", "ok")


def _check_en05(handoff_complete: bool) -> tuple[str, str]:
    """EN-05: handoff_complete must be true."""
    if handoff_complete is not True:
        return ("FAIL", "handoff-mismatch")
    return ("PASS", "ok")


def _do_score(args: argparse.Namespace) -> None:
    phase: str = args.phase
    case_id: str = args.case_id
    response_path: str = args.response
    output_path: str = args.output

    # Read response file
    try:
        with open(response_path, "rb") as fh:
            response_raw = fh.read()
    except OSError as e:
        _die(f"Cannot read response file: {e}", 2)

    output_sha256 = _sha256_hex(response_raw)
    response_text = response_raw.decode("utf-8")

    # Parse JSON
    try:
        response_obj = json.loads(response_text)
    except (json.JSONDecodeError, ValueError) as e:
        # Parse failure → all parse-error
        verdicts = [
            {"criterion_id": cid, "status": "FAIL", "reason_code": "parse-error"}
            for cid in ["EN-01", "EN-02", "EN-03", "EN-04", "EN-05"]
        ]
        _write_score_output(output_sha256, phase, case_id, verdicts, output_path)
        return

    # Schema check: must be dict with required fields
    if not isinstance(response_obj, dict):
        verdicts = [
            {"criterion_id": cid, "status": "FAIL", "reason_code": "schema-error"}
            for cid in ["EN-01", "EN-02", "EN-03", "EN-04", "EN-05"]
        ]
        _write_score_output(output_sha256, phase, case_id, verdicts, output_path)
        return

    # Extract fields with defaults for missing
    try:
        routes: list = response_obj.get("routes", [])
        artifacts: list = response_obj.get("persisted_artifacts", [])
        section_a_order: list = response_obj.get("section_a_order", [])
        push_authorized = response_obj.get("push_authorized")
        recovery: dict = response_obj.get("recovery", {})
        runtime_specific_terms: list = response_obj.get("runtime_specific_terms", [])
        handoff_complete = response_obj.get("handoff_complete")
    except Exception:
        verdicts = [
            {"criterion_id": cid, "status": "FAIL", "reason_code": "schema-error"}
            for cid in ["EN-01", "EN-02", "EN-03", "EN-04", "EN-05"]
        ]
        _write_score_output(output_sha256, phase, case_id, verdicts, output_path)
        return

    # Check for missing required fields (None values for critical fields)
    if (
        push_authorized is None
        or not isinstance(recovery, dict)
        or handoff_complete is None
    ):
        verdicts = [
            {"criterion_id": cid, "status": "FAIL", "reason_code": "schema-error"}
            for cid in ["EN-01", "EN-02", "EN-03", "EN-04", "EN-05"]
        ]
        _write_score_output(output_sha256, phase, case_id, verdicts, output_path)
        return

    verdicts: list[dict] = []

    # EN-01: forbidden tokens
    en01_status, en01_reason = _check_en01(runtime_specific_terms, response_text)
    verdicts.append(
        {"criterion_id": "EN-01", "status": en01_status, "reason_code": en01_reason}
    )

    # If EN-01 failed, skip remaining checks
    if en01_status == "PASS":
        # EN-02: route/artifact matching
        en02_status, en02_reason = _check_en02(case_id, routes, artifacts)
        verdicts.append(
            {
                "criterion_id": "EN-02",
                "status": en02_status if en02_status else "PASS",
                "reason_code": en02_reason,
            }
        )

        # EN-03: section_a_order and push_authorized
        en03_status, en03_reason = _check_en03(section_a_order, push_authorized)
        verdicts.append(
            {"criterion_id": "EN-03", "status": en03_status, "reason_code": en03_reason}
        )

        # EN-04: recovery
        en04_status, en04_reason = _check_en04(recovery)
        verdicts.append(
            {"criterion_id": "EN-04", "status": en04_status, "reason_code": en04_reason}
        )

        # EN-05: handoff_complete
        en05_status, en05_reason = _check_en05(handoff_complete)
        verdicts.append(
            {"criterion_id": "EN-05", "status": en05_status, "reason_code": en05_reason}
        )
    else:
        # EN-01 failed: remaining criteria not evaluated
        verdicts.append(
            {"criterion_id": "EN-02", "status": "FAIL", "reason_code": "forbidden-term"}
        )
        verdicts.append(
            {"criterion_id": "EN-03", "status": "FAIL", "reason_code": "forbidden-term"}
        )
        verdicts.append(
            {"criterion_id": "EN-04", "status": "FAIL", "reason_code": "forbidden-term"}
        )
        verdicts.append(
            {"criterion_id": "EN-05", "status": "FAIL", "reason_code": "forbidden-term"}
        )

    # Sort verdicts by criterion_id
    verdicts.sort(key=lambda v: v["criterion_id"])

    _write_score_output(output_sha256, phase, case_id, verdicts, output_path)


def _write_score_output(
    output_sha256: str,
    phase: str,
    case_id: str,
    verdicts: list[dict],
    output_path: str,
) -> None:
    all_pass = all(v["status"] == "PASS" for v in verdicts)

    score = {
        "schema_version": SCHEMA_VERSION,
        "phase": phase,
        "case_id": case_id,
        "output_sha256": output_sha256,
        "verdicts": verdicts,
        "all_pass": all_pass,
    }

    score_bytes = _canonical_json(score)

    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(output_path, "wb") as fh:
        fh.write(score_bytes)

    sys.stdout.buffer.write(score_bytes)
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# CLI setup
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Receipt and Score CLIs for address-pr-comments-review eval"
    )

    # Mutually exclusive: --receipt or --score
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--receipt", action="store_true", help="Run Receipt CLI")
    group.add_argument("--score", action="store_true", help="Run Score CLI")

    # Shared args (needed by receipt)
    parser.add_argument("--phase", type=str, help="Phase: probe, red, or green")
    parser.add_argument("--case-id", type=str, dest="case_id", help="Case identifier")
    parser.add_argument("--ordinal", type=int, help="Case ordinal (receipt only)")
    parser.add_argument(
        "--description", type=str, help="Human-readable description (receipt only)"
    )
    parser.add_argument("--task-id", type=str, dest="task_id", help="Task ID")
    parser.add_argument("--session-id", type=str, dest="session_id", help="Session ID")
    parser.add_argument("--prompt", type=str, help="Path to prompt file")
    parser.add_argument(
        "--response",
        type=str,
        help="Path to response file (receipt) or task output (score)",
    )
    parser.add_argument(
        "--transcript", type=str, help="Path to transcript file (receipt only)"
    )
    parser.add_argument(
        "--output", type=str, help="Output path for receipt or score JSON"
    )

    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        if args.receipt:
            _do_receipt(args)
        elif args.score:
            _do_score(args)
        else:
            _die("Must specify --receipt or --score", 2)
    except OSError as e:
        _die(f"I/O error: {e}", 4)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
