#!/usr/bin/env python3
"""Artifact lifecycle helper for address-pr-comments-review.

POSIX-only. Atomic writes with fsync/read-back.
Commands: create, record, transition.
"""

from __future__ import annotations

import argparse
import base64
import datetime
import hashlib
import json
import os
import re
import sys
import uuid
from typing import NoReturn

# -- POSIX guard --
try:
    import fcntl
except ImportError:
    error_envelope = json.dumps(
        {
            "schema_version": 1,
            "operation": "init",
            "diagnostic_code": "platform-unsupported",
            "message": "POSIX required: fcntl module not available on this platform",
        },
        separators=(",", ":"),
        ensure_ascii=False,
    )
    print(error_envelope, flush=True)
    sys.exit(2)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA_VERSION = 1

DIAG_SCHEMA_INVALID = "schema-invalid"
DIAG_PLATFORM_UNSUPPORTED = "platform-unsupported"
DIAG_LOCK_BUSY = "lock-busy"
DIAG_CAS_MISMATCH = "cas-mismatch"
DIAG_IDENTITY_MISMATCH = "identity-mismatch"
DIAG_IO_ERROR = "io-error"
DIAG_ILLEGAL_TRANSITION = "illegal-transition"

VALID_STATES = frozenset({"pending", "in-progress", "blocked", "verified-complete"})

LEGAL_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending": frozenset({"in-progress", "blocked"}),
    "in-progress": frozenset({"blocked", "verified-complete"}),
    "blocked": frozenset({"in-progress"}),
    "verified-complete": frozenset(),
}

VALID_RECORD_KINDS = frozenset(
    {
        "task-status",
        "commit-intent",
        "modification-commit",
        "final-tip",
        "verification",
        "post-attempt",
        "thread-snapshot",
        "reply-disposition",
        "reply",
        "read-back",
        "remote-reachability",
        "push-receipt",
    }
)

STATUS_START = "<!-- artifact-execution-status:start -->"
STATUS_END = "<!-- artifact-execution-status:end -->"
INVENTORY_START = "<!-- artifact-execution-inventory:start -->"
INVENTORY_END = "<!-- artifact-execution-inventory:end -->"

# JSON section markers for inventory SHA computation
JSON_SECTION_MARKERS = {
    "context": ("<!-- context-json:start -->", "<!-- context-json:end -->"),
    "tasks": ("<!-- tasks-json:start -->", "<!-- tasks-json:end -->"),
    "verifications": (
        "<!-- verifications-json:start -->",
        "<!-- verifications-json:end -->",
    ),
    "reply_targets": (
        "<!-- reply-targets-json:start -->",
        "<!-- reply-targets-json:end -->",
    ),
}

SENTINEL_TEMPLATES = [
    "{{ARTIFACT_ID}}",
    "{{OPERATION_ID}}",
    "{{UPDATED_AT}}",
    "{{GENERATION_HEAD}}",
    "{{INVENTORY_SHA256}}",
]


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(obj: object) -> bytes:
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return (text + "\n").encode("utf-8")


def _format_json_bytes(obj: object) -> str:
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return text + "\n"


def _uuid4() -> str:
    return str(uuid.uuid4())


def _now_rfc3339() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _write_atomic(path: str, content: bytes, mode: int = 0o600) -> None:
    import pathlib as _pl

    p = _pl.Path(path)
    tmp = p.with_suffix(p.suffix + ".tmp")
    try:
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
        try:
            os.write(fd, content)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(str(tmp), str(p))
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def _read_file(path: str) -> bytes:
    import pathlib as _pl

    p = _pl.Path(path)
    if not p.exists():
        return b""
    return p.read_bytes()


def _file_sha256(path: str) -> str:
    return _sha256_hex(_read_file(path))


# ---------------------------------------------------------------------------
# Error & response envelopes
# ---------------------------------------------------------------------------


def _error(operation: str, code: str, message: str) -> str:
    return _format_json_bytes(
        {
            "schema_version": SCHEMA_VERSION,
            "operation": operation,
            "diagnostic_code": code,
            "message": message,
        }
    )


def _die(operation: str, code: str, message: str, exit_code: int) -> NoReturn:
    print(_error(operation, code, message), end="", flush=True)
    sys.exit(exit_code)


# ---------------------------------------------------------------------------
# Artifact parsing
# ---------------------------------------------------------------------------


def _extract_section(content: str, start_marker: str, end_marker: str) -> str | None:
    """Extract content between two markers. Returns None if markers not found."""
    si = content.find(start_marker)
    if si == -1:
        return None
    si += len(start_marker)
    ei = content.find(end_marker, si)
    if ei == -1:
        return None
    return content[si:ei]


def _parse_status_block(content: str) -> dict[str, str]:
    """Parse the status block table into a dict of field->value.

    Strips backtick wrapping from values (e.g. `uuid` → uuid).
    """
    section = _extract_section(content, STATUS_START, STATUS_END)
    if section is None:
        return {}

    fields: dict[str, str] = {}
    # Parse markdown table: | Field | Value |\n|-------|-------|\n| name | val |
    in_table = False
    for line in section.split("\n"):
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) < 2:
            continue
        if cells[0] in ("Field", "---", "-------"):
            in_table = True
            continue
        if in_table:
            val = cells[1] if len(cells) > 1 else ""
            # Strip backtick wrapping: `value` → value
            val = val.removeprefix("`").removesuffix("`")
            fields[cells[0]] = val
    return fields


def _find_json_sections(content: str) -> dict[str, object]:
    """Find JSON sections in artifact by scanning for markers and code blocks."""
    sections: dict[str, object] = {}

    # Try marker-delimited sections first
    for name, (start_m, end_m) in JSON_SECTION_MARKERS.items():
        section = _extract_section(content, start_m, end_m)
        if section is not None:
            try:
                sections[name] = json.loads(section.strip())
            except (json.JSONDecodeError, ValueError):
                pass

    # Fallback: try ```json code blocks
    if not sections:
        json_blocks = re.findall(r"```json\s*\n(.*?)```", content, re.DOTALL)
        parsed_blocks: list[dict | list[dict]] = []
        for block in json_blocks:
            try:
                parsed = json.loads(block.strip())
                if isinstance(parsed, (dict, list)):
                    parsed_blocks.append(parsed)
            except (json.JSONDecodeError, ValueError):
                continue

        for block in parsed_blocks:
            if isinstance(block, dict):
                if "repo" in block or "pr_number" in block:
                    sections.setdefault("context", block)
                elif "task_id" in block:
                    sections.setdefault("tasks", block)
                elif "verification_id" in block:
                    sections.setdefault("verifications", block)
                elif "reply_target_id" in block:
                    sections.setdefault("reply_targets", block)
            elif isinstance(block, list):
                if block and isinstance(block[0], dict):
                    sample = block[0]
                    if "task_id" in sample:
                        sections.setdefault("tasks", block)
                    elif "verification_id" in sample:
                        sections.setdefault("verifications", block)
                    elif "reply_target_id" in sample:
                        sections.setdefault("reply_targets", block)

    return sections


def _compute_inventory_sha(
    artifact_id: str,
    kind: str,
    generation_head: str,
    sections: dict[str, object],
) -> str:
    """Compute inventory SHA from create_metadata + context + tasks + verifications + reply_targets."""
    create_metadata = {
        "artifact_id": artifact_id,
        "kind": kind,
        "generation_head": generation_head,
    }

    parts: list[bytes] = [_canonical_json(create_metadata)]

    for key in ("context", "tasks", "verifications", "reply_targets"):
        if key in sections and sections[key] is not None:
            parts.append(_canonical_json(sections[key]))
        else:
            parts.append(_canonical_json(None))

    combined = b"".join(parts)
    return _sha256_hex(combined)


def _count_inventory_records(content: str) -> int:
    """Count existing JSON records in the evidence inventory."""
    section = _extract_section(content, INVENTORY_START, INVENTORY_END)
    if section is None:
        return 0
    count = 0
    for line in section.strip().split("\n"):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                json.loads(line)
                count += 1
            except (json.JSONDecodeError, ValueError):
                pass
    return count


# ---------------------------------------------------------------------------
# CREATE command
# ---------------------------------------------------------------------------


def _do_create(args: argparse.Namespace) -> None:
    operation = "create"

    source_base64: str = args.source_base64
    artifact_path: str = args.artifact
    kind: str = args.kind
    artifact_id: str = args.artifact_id
    operation_id: str = args.operation_id
    generation_head: str = args.generation_head
    expected_absent: bool = args.expected_absent

    # Validate kind
    if kind not in ("review-dossier", "direct-fix"):
        _die(operation, DIAG_SCHEMA_INVALID, f"Invalid kind: {kind}", 2)

    # Validate generation_head is 40-char hex
    if len(generation_head) != 40 or not all(
        c in "0123456789abcdef" for c in generation_head.lower()
    ):
        _die(
            operation,
            DIAG_SCHEMA_INVALID,
            f"Invalid generation_head: {generation_head}",
            2,
        )

    # Decode source from base64 (in memory only)
    try:
        source_bytes = base64.b64decode(source_base64)
        source_text = source_bytes.decode("utf-8")
    except Exception as e:
        if not isinstance(e, (UnicodeDecodeError, ValueError)):
            if (
                type(e).__name__ != "Error"
                or getattr(e, "__module__", "") != "binascii"
            ):
                raise
        _die(operation, DIAG_SCHEMA_INVALID, f"Invalid base64 source: {e}", 2)

    # Check expected-absent
    import pathlib as _pl

    ap = _pl.Path(artifact_path)
    if ap.exists():
        if expected_absent:
            _die(
                operation,
                DIAG_CAS_MISMATCH,
                f"Artifact already exists and --expected-absent set: {artifact_path}",
                3,
            )
        # Read existing, check if unchanged via artifact identity
        existing_bytes = _read_file(artifact_path)
        existing_text = existing_bytes.decode("utf-8")

        existing_status = _parse_status_block(existing_text)
        existing_aid = existing_status.get("Artifact ID", "")

        if existing_aid == artifact_id:
            existing_sha = _sha256_hex(existing_bytes)
            print(
                _format_json_bytes(
                    {
                        "schema_version": SCHEMA_VERSION,
                        "operation": operation,
                        "status": "unchanged",
                        "artifact_sha256": existing_sha,
                        "state": "pending",
                    }
                ),
                end="",
                flush=True,
            )
            return
        _die(operation, DIAG_CAS_MISMATCH, "Artifact exists with different content", 3)

    # Find JSON sections and compute inventory SHA
    sections = _find_json_sections(source_text)
    inventory_sha = _compute_inventory_sha(artifact_id, kind, generation_head, sections)
    updated_at = _now_rfc3339()

    # Apply sentinel replacements
    result = source_text
    result = result.replace("{{ARTIFACT_ID}}", artifact_id)
    result = result.replace("{{OPERATION_ID}}", operation_id)
    result = result.replace("{{UPDATED_AT}}", updated_at)
    result = result.replace("{{GENERATION_HEAD}}", generation_head)
    result = result.replace("{{INVENTORY_SHA256}}", inventory_sha)

    # Verify no unresolved sentinels remain
    for sentinel in SENTINEL_TEMPLATES:
        if sentinel in result:
            _die(
                operation,
                DIAG_SCHEMA_INVALID,
                f"Unresolved sentinel {sentinel} in artifact",
                2,
            )

    result_bytes = result.encode("utf-8")

    # Ensure parent directory exists
    parent = ap.parent
    if not parent.exists():
        parent.mkdir(mode=0o700, parents=True, exist_ok=True)

    # Write atomically with fsync
    _write_atomic(artifact_path, result_bytes)

    # Read-back verification
    written_content = _read_file(artifact_path)
    if written_content != result_bytes:
        _die(operation, DIAG_CAS_MISMATCH, "Read-back mismatch after atomic write", 3)

    artifact_sha = _sha256_hex(result_bytes)

    print(
        _format_json_bytes(
            {
                "schema_version": SCHEMA_VERSION,
                "operation": operation,
                "status": "created",
                "artifact_sha256": artifact_sha,
                "state": "pending",
            }
        ),
        end="",
        flush=True,
    )


# ---------------------------------------------------------------------------
# RECORD command
# ---------------------------------------------------------------------------


def _do_record(args: argparse.Namespace) -> None:
    operation = "record"

    artifact_path: str = args.artifact
    artifact_id: str = args.artifact_id
    operation_id: str = args.operation_id
    record_id: str = args.record_id
    expected_state: str = args.expected_state
    expected_sha256: str = args.expected_sha256
    record_kind: str = args.record_kind
    record_json_str: str = args.record_json

    # Validate expected_state
    if expected_state not in VALID_STATES:
        _die(
            operation,
            DIAG_SCHEMA_INVALID,
            f"Invalid expected_state: {expected_state}",
            2,
        )

    # Validate record kind
    if record_kind not in VALID_RECORD_KINDS:
        _die(operation, DIAG_SCHEMA_INVALID, f"Invalid record_kind: {record_kind}", 2)

    # Read artifact
    content_bytes = _read_file(artifact_path)
    if not content_bytes:
        _die(operation, DIAG_IO_ERROR, f"Artifact not found: {artifact_path}", 4)

    # Validate artifact SHA
    actual_sha = _sha256_hex(content_bytes)
    if actual_sha != expected_sha256:
        _die(
            operation,
            DIAG_CAS_MISMATCH,
            f"Artifact SHA mismatch: expected {expected_sha256}, got {actual_sha}",
            3,
        )

    content = content_bytes.decode("utf-8")

    # Parse status block
    status_fields = _parse_status_block(content)
    actual_artifact_id = status_fields.get("Artifact ID", "")
    actual_state = status_fields.get("State", "")

    if actual_artifact_id != artifact_id:
        _die(
            operation,
            DIAG_IDENTITY_MISMATCH,
            f"Artifact ID mismatch: expected {artifact_id}, got {actual_artifact_id}",
            2,
        )

    if actual_state != expected_state:
        _die(
            operation,
            DIAG_IDENTITY_MISMATCH,
            f"State mismatch: expected {expected_state}, got {actual_state}",
            2,
        )

    # Parse record JSON
    try:
        record_payload = json.loads(record_json_str)
    except (json.JSONDecodeError, ValueError) as e:
        _die(operation, DIAG_SCHEMA_INVALID, f"Invalid record-json: {e}", 2)

    # Count current records for sequence
    current_sequence = _count_inventory_records(content)
    new_sequence = current_sequence + 1

    # Build evidence envelope
    envelope = {
        "record_id": record_id,
        "kind": record_kind,
        "key": record_kind,
        "version": 1,
        "sequence": new_sequence,
        "operation_id": operation_id,
        "recorded_at": _now_rfc3339(),
        "payload": record_payload,
    }
    envelope_json = json.dumps(
        envelope, separators=(",", ":"), sort_keys=True, ensure_ascii=False
    )

    # Find evidence inventory section
    inv_start_idx = content.find(INVENTORY_START)
    inv_end_idx = content.find(INVENTORY_END)

    if inv_start_idx == -1 or inv_end_idx == -1:
        _die(
            operation,
            DIAG_SCHEMA_INVALID,
            "Evidence inventory markers not found in artifact",
            2,
        )

    insert_pos = inv_end_idx

    # Build new content with record inserted before INVENTORY_END
    new_content = content[:insert_pos] + envelope_json + "\n" + content[insert_pos:]

    # Update Evidence Sequence in status block
    new_content = _update_status_field(
        new_content, "Evidence Sequence", str(new_sequence)
    )
    new_content = _update_status_field(new_content, "Updated At", _now_rfc3339())

    new_bytes = new_content.encode("utf-8")

    # Write atomically
    _write_atomic(artifact_path, new_bytes)

    # Read-back verification
    written = _read_file(artifact_path)
    if written != new_bytes:
        _die(operation, DIAG_CAS_MISMATCH, "Read-back mismatch after record write", 3)

    new_artifact_sha = _sha256_hex(new_bytes)

    print(
        _format_json_bytes(
            {
                "schema_version": SCHEMA_VERSION,
                "operation": operation,
                "status": "recorded",
                "artifact_sha256": new_artifact_sha,
                "state": actual_state,
                "record_id": record_id,
                "version": 1,
                "sequence": new_sequence,
            }
        ),
        end="",
        flush=True,
    )


def _update_status_field(content: str, field_name: str, new_value: str) -> str:
    """Update a field in the status block table."""
    ss = content.find(STATUS_START)
    se = content.find(STATUS_END)
    if ss == -1 or se == -1:
        return content

    status_section = content[ss : se + len(STATUS_END)]
    # Replace the field value in the table row: | Field Name | old_value |
    pattern = re.compile(
        r"(\|\s*" + re.escape(field_name) + r"\s*\|)\s*[^|\n]*(\s*\|)",
        re.IGNORECASE,
    )
    new_status = pattern.sub(r"\1 " + new_value + r" \2", status_section)
    return content[:ss] + new_status + content[se + len(STATUS_END) :]


# ---------------------------------------------------------------------------
# TRANSITION command
# ---------------------------------------------------------------------------


def _do_transition(args: argparse.Namespace) -> None:
    operation = "transition"

    artifact_path: str = args.artifact
    artifact_id: str = args.artifact_id
    expected_operation_id: str = args.expected_operation_id
    expected_state: str = args.expected_state
    to_state: str = args.to_state
    expected_sha256: str = args.expected_sha256
    reason_json_str: str = args.reason_json
    next_operation_id: str | None = args.next_operation_id
    started_head: str | None = args.started_head
    evidence_json_str: str | None = args.evidence_json

    # Validate states
    if expected_state not in VALID_STATES:
        _die(
            operation,
            DIAG_SCHEMA_INVALID,
            f"Invalid expected_state: {expected_state}",
            2,
        )
    if to_state not in VALID_STATES:
        _die(operation, DIAG_SCHEMA_INVALID, f"Invalid to_state: {to_state}", 2)

    # Validate transition is legal
    allowed = LEGAL_TRANSITIONS.get(expected_state, frozenset())
    if to_state not in allowed:
        _die(
            operation,
            DIAG_ILLEGAL_TRANSITION,
            f"Illegal transition: {expected_state} → {to_state}",
            2,
        )

    # Read artifact
    content_bytes = _read_file(artifact_path)
    if not content_bytes:
        _die(operation, DIAG_IO_ERROR, f"Artifact not found: {artifact_path}", 4)

    # Validate artifact SHA
    actual_sha = _sha256_hex(content_bytes)
    if actual_sha != expected_sha256:
        _die(
            operation,
            DIAG_CAS_MISMATCH,
            f"Artifact SHA mismatch: expected {expected_sha256}, got {actual_sha}",
            3,
        )

    content = content_bytes.decode("utf-8")

    # Parse status block
    status_fields = _parse_status_block(content)
    actual_artifact_id = status_fields.get("Artifact ID", "")
    actual_state = status_fields.get("State", "")
    actual_op_id = status_fields.get("Operation ID", "")

    if actual_artifact_id != artifact_id:
        _die(
            operation,
            DIAG_IDENTITY_MISMATCH,
            f"Artifact ID mismatch: expected {artifact_id}, got {actual_artifact_id}",
            2,
        )

    if actual_state != expected_state:
        _die(
            operation,
            DIAG_IDENTITY_MISMATCH,
            f"State mismatch: expected {expected_state}, got {actual_state}",
            2,
        )

    if actual_op_id != expected_operation_id:
        _die(
            operation,
            DIAG_IDENTITY_MISMATCH,
            f"Operation ID mismatch: expected {expected_operation_id}, got {actual_op_id}",
            2,
        )

    # Parse reason JSON
    try:
        reason_data = json.loads(reason_json_str)
    except (json.JSONDecodeError, ValueError) as e:
        _die(operation, DIAG_SCHEMA_INVALID, f"Invalid reason-json: {e}", 2)

    # verified-complete requires evidence-json with record_ids
    if to_state == "verified-complete":
        if not evidence_json_str:
            _die(
                operation,
                DIAG_SCHEMA_INVALID,
                "verified-complete requires --evidence-json",
                2,
            )
        try:
            evidence_data = json.loads(evidence_json_str)
        except (json.JSONDecodeError, ValueError) as e:
            _die(operation, DIAG_SCHEMA_INVALID, f"Invalid evidence-json: {e}", 2)
        if "record_ids" not in evidence_data or not isinstance(
            evidence_data["record_ids"], list
        ):
            _die(
                operation,
                DIAG_SCHEMA_INVALID,
                "evidence-json must contain 'record_ids' array",
                2,
            )

    now = _now_rfc3339()

    # Update status block fields
    new_content = _update_status_field(content, "State", to_state)
    new_content = _update_status_field(new_content, "Updated At", now)

    if next_operation_id:
        new_content = _update_status_field(
            new_content, "Operation ID", next_operation_id
        )

    if started_head and expected_state == "pending" and to_state == "in-progress":
        new_content = _update_status_field(new_content, "Started HEAD", started_head)

    # Update transition preimages
    preimage = _build_preimage(status_fields)
    preimage_json = json.dumps(
        {f"{expected_state}→{to_state}": preimage},
        separators=(",", ":"),
        ensure_ascii=False,
    )
    new_content = _update_status_field(
        new_content, "Transition Preimages", preimage_json
    )

    # Append to transition history
    existing_history = status_fields.get("Transition History", "")
    new_entry = f"{expected_state}→{to_state}@{now}"
    updated_history = (
        f"{existing_history},{new_entry}" if existing_history else new_entry
    )
    new_content = _update_status_field(
        new_content, "Transition History", updated_history
    )

    # Update blocked reason if transitioning to blocked
    if to_state == "blocked":
        reason_text = reason_data.get("reason", "Blocked")
        new_content = _update_status_field(new_content, "Blocked Reason", reason_text)

    new_bytes = new_content.encode("utf-8")

    # Write atomically
    _write_atomic(artifact_path, new_bytes)

    # Read-back verification
    written = _read_file(artifact_path)
    if written != new_bytes:
        _die(operation, DIAG_CAS_MISMATCH, "Read-back mismatch after transition", 3)

    new_artifact_sha = _sha256_hex(new_bytes)

    print(
        _format_json_bytes(
            {
                "schema_version": SCHEMA_VERSION,
                "operation": operation,
                "status": "transitioned",
                "artifact_sha256": new_artifact_sha,
                "state": to_state,
            }
        ),
        end="",
        flush=True,
    )


def _build_preimage(status_fields: dict[str, str]) -> dict[str, str]:
    """Build a preimage snapshot of key status fields."""
    return {
        "state": status_fields.get("State", ""),
        "operation_id": status_fields.get("Operation ID", ""),
        "evidence_sequence": status_fields.get("Evidence Sequence", "0"),
        "artifact_id": status_fields.get("Artifact ID", ""),
    }


# ---------------------------------------------------------------------------
# CLI setup
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Artifact lifecycle helper for address-pr-comments-review"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # create
    create_p = sub.add_parser(
        "create", help="Create a new artifact from source template"
    )
    create_p.add_argument(
        "--source-base64",
        required=True,
        type=str,
        dest="source_base64",
        help="Base64-encoded artifact source template",
    )
    create_p.add_argument(
        "--artifact", required=True, type=str, help="Output artifact file path"
    )
    create_p.add_argument(
        "--kind",
        required=True,
        type=str,
        choices=["review-dossier", "direct-fix"],
        help="Artifact kind",
    )
    create_p.add_argument(
        "--artifact-id",
        required=True,
        type=str,
        dest="artifact_id",
        help="UUID for the artifact",
    )
    create_p.add_argument(
        "--operation-id",
        required=True,
        type=str,
        dest="operation_id",
        help="UUID for the initial operation",
    )
    create_p.add_argument(
        "--generation-head",
        required=True,
        type=str,
        dest="generation_head",
        help="40-char hex commit SHA",
    )
    create_p.add_argument(
        "--expected-absent",
        action="store_true",
        dest="expected_absent",
        help="Fail if artifact already exists",
    )

    # record
    record_p = sub.add_parser("record", help="Append evidence record to artifact")
    record_p.add_argument(
        "--artifact", required=True, type=str, help="Artifact file path"
    )
    record_p.add_argument(
        "--artifact-id",
        required=True,
        type=str,
        dest="artifact_id",
        help="Expected artifact UUID",
    )
    record_p.add_argument(
        "--operation-id",
        required=True,
        type=str,
        dest="operation_id",
        help="Current operation UUID",
    )
    record_p.add_argument(
        "--record-id",
        required=True,
        type=str,
        dest="record_id",
        help="UUID for this record",
    )
    record_p.add_argument(
        "--expected-state",
        required=True,
        type=str,
        dest="expected_state",
        choices=["pending", "in-progress", "blocked"],
        help="Expected current artifact state",
    )
    record_p.add_argument(
        "--expected-sha256",
        required=True,
        type=str,
        dest="expected_sha256",
        help="Expected artifact SHA-256",
    )
    record_p.add_argument(
        "--record-kind",
        required=True,
        type=str,
        dest="record_kind",
        help="Evidence record kind",
    )
    record_p.add_argument(
        "--record-json",
        required=True,
        type=str,
        dest="record_json",
        help="JSON payload for the record",
    )

    # transition
    transition_p = sub.add_parser("transition", help="Transition artifact to new state")
    transition_p.add_argument(
        "--artifact", required=True, type=str, help="Artifact file path"
    )
    transition_p.add_argument(
        "--artifact-id",
        required=True,
        type=str,
        dest="artifact_id",
        help="Expected artifact UUID",
    )
    transition_p.add_argument(
        "--expected-operation-id",
        required=True,
        type=str,
        dest="expected_operation_id",
        help="Expected current operation UUID",
    )
    transition_p.add_argument(
        "--expected-state",
        required=True,
        type=str,
        dest="expected_state",
        choices=["pending", "in-progress", "blocked"],
        help="Expected current artifact state",
    )
    transition_p.add_argument(
        "--to-state",
        required=True,
        type=str,
        dest="to_state",
        choices=["in-progress", "blocked", "verified-complete"],
        help="Target state",
    )
    transition_p.add_argument(
        "--expected-sha256",
        required=True,
        type=str,
        dest="expected_sha256",
        help="Expected artifact SHA-256",
    )
    transition_p.add_argument(
        "--reason-json",
        required=True,
        type=str,
        dest="reason_json",
        help="JSON reason for transition",
    )
    transition_p.add_argument(
        "--next-operation-id",
        type=str,
        dest="next_operation_id",
        help="New operation UUID for next attempt",
    )
    transition_p.add_argument(
        "--started-head",
        type=str,
        dest="started_head",
        help="40-char commit SHA at execution start",
    )
    transition_p.add_argument(
        "--evidence-json",
        type=str,
        dest="evidence_json",
        help="JSON evidence (required for verified-complete)",
    )

    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        if args.command == "create":
            _do_create(args)
        elif args.command == "record":
            _do_record(args)
        elif args.command == "transition":
            _do_transition(args)
    except OSError as e:
        print(_error(args.command, DIAG_IO_ERROR, str(e)), end="", flush=True)
        return 4

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
