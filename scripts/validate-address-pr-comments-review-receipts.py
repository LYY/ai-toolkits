#!/usr/bin/env python3
"""Receipt validator for address-pr-comments-review executor-neutral eval.

Validates receipt files against manifest case definitions and phase-specific
quorum requirements. Writes durable content-addressed receipt copies.

Arguments:
  --phase red|green         Evaluation phase
  --manifest PATH           cases.json with case definitions and score expectations
  --receipts PATH           Directory containing receipt JSON files
  --durable-output PATH     Directory for content-addressed durable copies

stdlib only. No external dependencies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from typing import NoReturn


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA_VERSION = 1

RECEIPT_REQUIRED_FIELDS: set[str] = {
    "schema_version",
    "transcript_format",
    "adapter_contract_version",
    "description",
    "run_id",
    "phase",
    "case_id",
    "ordinal",
    "task_id",
    "session_id",
    "prompt_raw_sha256",
    "prompt_canonical_sha256",
    "delivered_user_sha256",
    "response_raw_sha256",
    "response_canonical_sha256",
    "tool_events_sha256",
    "transcript_raw_sha256",
    "started_at",
    "finished_at",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha256(path: str) -> str:
    with open(path, "rb") as fh:
        return _sha256_hex(fh.read())


def _format_json_bytes(obj: object) -> str:
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return text + "\n"


def _canonical_json_bytes(obj: object) -> bytes:
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return (text + "\n").encode("utf-8")


def _die(message: str, exit_code: int = 2) -> NoReturn:
    sys.stderr.write(message + "\n")
    sys.exit(exit_code)


# ---------------------------------------------------------------------------
# Receipt validation
# ---------------------------------------------------------------------------


def _validate_receipt(receipt: dict, path: str) -> list[str]:
    """Validate a single receipt object. Returns list of error messages."""
    errors: list[str] = []

    if not isinstance(receipt, dict):
        errors.append(f"{path}: not a JSON object")
        return errors

    # Check required fields
    for field in RECEIPT_REQUIRED_FIELDS:
        if field not in receipt:
            errors.append(f"{path}: missing required field '{field}'")

    if errors:
        return errors

    # Validate schema_version
    if receipt.get("schema_version") != SCHEMA_VERSION:
        errors.append(
            f"{path}: schema_version {receipt.get('schema_version')} != {SCHEMA_VERSION}"
        )

    # Validate phase
    phase = receipt.get("phase")
    if phase not in ("probe", "red", "green"):
        errors.append(f"{path}: invalid phase '{phase}'")

    # Type checks for string fields
    string_fields = [
        "transcript_format",
        "adapter_contract_version",
        "description",
        "run_id",
        "phase",
        "case_id",
        "task_id",
        "session_id",
        "prompt_raw_sha256",
        "prompt_canonical_sha256",
        "delivered_user_sha256",
        "response_raw_sha256",
        "response_canonical_sha256",
        "tool_events_sha256",
        "transcript_raw_sha256",
        "started_at",
        "finished_at",
    ]
    for field in string_fields:
        val = receipt.get(field)
        if not isinstance(val, str):
            errors.append(
                f"{path}: field '{field}' must be a string, got {type(val).__name__}"
            )

    # Validate hex SHA lengths
    sha_fields = [
        "prompt_raw_sha256",
        "prompt_canonical_sha256",
        "delivered_user_sha256",
        "response_raw_sha256",
        "response_canonical_sha256",
        "tool_events_sha256",
        "transcript_raw_sha256",
    ]
    for field in sha_fields:
        val = receipt.get(field, "")
        if isinstance(val, str) and len(val) != 64:
            errors.append(
                f"{path}: field '{field}' must be 64 hex chars, got {len(val)}"
            )

    # Validate ordinal is an integer
    ordinal = receipt.get("ordinal")
    if not isinstance(ordinal, int):
        errors.append(
            f"{path}: 'ordinal' must be an integer, got {type(ordinal).__name__}"
        )

    return errors


# ---------------------------------------------------------------------------
# Manifest loading
# ---------------------------------------------------------------------------


def _load_manifest(path: str) -> dict:
    """Load and validate manifest (cases.json)."""
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError as e:
        _die(f"Cannot read manifest: {e}", 2)

    try:
        obj = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        _die(f"Invalid JSON in manifest: {e}", 2)

    if not isinstance(obj, dict):
        _die("Manifest is not a JSON object", 2)

    cases_list = obj.get("cases")
    if not isinstance(cases_list, list):
        _die("Manifest missing 'cases' array", 2)

    return obj


# ---------------------------------------------------------------------------
# Receipt loading
# ---------------------------------------------------------------------------


def _load_receipts(receipts_dir: str) -> list[tuple[str, dict, bytes]]:
    """Load all receipt JSON files from directory.

    Returns list of (filename, parsed, raw_bytes).
    """
    if not os.path.isdir(receipts_dir):
        _die(f"Receipts directory not found: {receipts_dir}", 2)

    receipts: list[tuple[str, dict, bytes]] = []

    for entry in sorted(os.listdir(receipts_dir)):
        if not entry.endswith(".json"):
            continue
        fpath = os.path.join(receipts_dir, entry)
        try:
            with open(fpath, "rb") as fh:
                raw = fh.read()
        except OSError as e:
            _die(f"Cannot read receipt {entry}: {e}", 2)

        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            _die(f"Invalid JSON in receipt {entry}: {e}", 2)

        if not isinstance(parsed, dict):
            _die(f"Receipt {entry} is not a JSON object", 2)

        receipts.append((entry, parsed, raw))

    return receipts


# ---------------------------------------------------------------------------
# Class grouping
# ---------------------------------------------------------------------------


def _build_case_class_map(manifest: dict) -> dict[str, str]:
    """Build mapping from case_id to class name."""
    class_map: dict[str, str] = {}
    case_set: dict[str, list[int]] = {}

    for case in manifest.get("cases", []):
        if not isinstance(case, dict):
            continue
        cid = case.get("case_id")
        cls = case.get("class")
        ordinal = case.get("ordinal")
        if not isinstance(cid, str) or not isinstance(cls, str):
            continue
        class_map[cid] = cls
        if isinstance(ordinal, int):
            case_set.setdefault(cid, []).append(ordinal)

    return class_map


def _build_manifest_expectations(
    manifest: dict,
) -> dict[str, dict]:
    """Build per-case expectations from manifest.

    Returns: {case_id: {"red_en01_fail": bool, "green_all_pass": bool}}
    """
    exps: dict[str, dict] = {}
    for case in manifest.get("cases", []):
        if not isinstance(case, dict):
            continue
        cid = case.get("case_id")
        if not isinstance(cid, str):
            continue
        exps[cid] = {
            "red_en01_fail": case.get("red_en01_fail", False),
            "green_all_pass": case.get("green_all_pass", False),
        }
    return exps


# ---------------------------------------------------------------------------
# Main validation
# ---------------------------------------------------------------------------


def _do_validate(args: argparse.Namespace) -> None:
    phase: str = args.phase
    manifest_path: str = args.manifest
    receipts_dir: str = args.receipts
    durable_output: str = args.durable_output

    if phase not in ("red", "green"):
        _die(f"Invalid phase: {phase}", 2)

    # Load manifest
    manifest = _load_manifest(manifest_path)
    class_map = _build_case_class_map(manifest)
    expectations = _build_manifest_expectations(manifest)

    # Load receipts
    receipt_entries = _load_receipts(receipts_dir)

    # Validate each receipt
    all_errors: list[str] = []
    for filename, parsed, _raw in receipt_entries:
        errors = _validate_receipt(parsed, filename)
        all_errors.extend(errors)

    if all_errors:
        for err in all_errors:
            sys.stderr.write(err + "\n")
        _die(f"Receipt validation failed with {len(all_errors)} error(s)", 2)

    total = len(receipt_entries)

    # Group by class
    class_receipts: dict[str, list[tuple[str, dict, bytes]]] = {}
    for entry in receipt_entries:
        _fn, parsed, raw = entry
        cid: str = parsed.get("case_id", "")
        cls_name: str = class_map.get(cid, cid)
        class_receipts.setdefault(cls_name, []).append(entry)

    num_classes = len(class_receipts)

    # Session uniqueness check
    for cls_name, entries in class_receipts.items():
        sessions: set[str] = set()
        for _fn, parsed, _raw in entries:
            sid = parsed.get("session_id", "")
            if sid:
                sessions.add(sid)
        if len(sessions) < 5:
            _die(
                f"Class '{cls_name}' has {len(sessions)} unique sessions (need 5 for phase={phase})",
                2,
            )

    # Quorum check
    quorum = True
    for cls_name, entries in class_receipts.items():
        if phase == "red":
            # RED: >=3 EN-01 failures per class
            en01_fails = 0
            for _fn, parsed, _raw in entries:
                cid = parsed.get("case_id", "")
                exp = expectations.get(cid, {})
                if exp.get("red_en01_fail"):
                    en01_fails += 1
            if en01_fails < 3:
                sys.stderr.write(
                    f"RED quorum failure: class '{cls_name}' has {en01_fails} EN-01 failures (need >=3)\n"
                )
                quorum = False
        else:
            # GREEN: >=4 all-pass per class
            all_pass_count = 0
            for _fn, parsed, _raw in entries:
                cid = parsed.get("case_id", "")
                exp = expectations.get(cid, {})
                if exp.get("green_all_pass"):
                    all_pass_count += 1
            if all_pass_count < 4:
                sys.stderr.write(
                    f"GREEN quorum failure: class '{cls_name}' has {all_pass_count} all-pass (need >=4)\n"
                )
                quorum = False

    # Write durable content-addressed copies
    os.makedirs(durable_output, exist_ok=True)
    written = 0
    durable_hashes: list[str] = []

    for _fn, parsed, raw_bytes in receipt_entries:
        # Write canonical receipt as durable copy
        canonical = _canonical_json_bytes(parsed)
        sha = _sha256_hex(canonical)
        out_path = os.path.join(durable_output, f"{sha}.json")

        # Only write if not already present (idempotent)
        if not os.path.exists(out_path):
            with open(out_path, "wb") as fh:
                fh.write(canonical)

        durable_hashes.append(sha)
        written += 1

    # Build durable manifest
    durable_hashes.sort()
    durable_manifest = {
        "schema_version": SCHEMA_VERSION,
        "phase": phase,
        "total": total,
        "written": written,
        "receipt_sha256s": durable_hashes,
    }
    manifest_bytes = _canonical_json_bytes(durable_manifest)
    durable_output_sha = _sha256_hex(manifest_bytes)

    # Write manifest to durable output
    manifest_out = os.path.join(durable_output, "manifest.json")
    with open(manifest_out, "wb") as fh:
        fh.write(manifest_bytes)

    # Output result
    result = {
        "schema_version": SCHEMA_VERSION,
        "phase": phase,
        "total": total,
        "classes": num_classes,
        "quorum": quorum,
        "written": written,
        "durable_output_sha256": durable_output_sha,
    }

    print(_format_json_bytes(result), end="", flush=True)

    if not quorum:
        sys.exit(1)


# ---------------------------------------------------------------------------
# CLI setup
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Receipt validator for address-pr-comments-review eval"
    )
    parser.add_argument(
        "--phase",
        required=True,
        choices=["red", "green"],
        help="Evaluation phase",
    )
    parser.add_argument(
        "--manifest",
        required=True,
        type=str,
        help="Path to cases.json manifest",
    )
    parser.add_argument(
        "--receipts",
        required=True,
        type=str,
        help="Directory containing receipt JSON files",
    )
    parser.add_argument(
        "--durable-output",
        required=True,
        type=str,
        dest="durable_output",
        help="Directory for durable content-addressed copies",
    )
    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        _do_validate(args)
    except OSError as e:
        _die(f"I/O error: {e}", 4)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
