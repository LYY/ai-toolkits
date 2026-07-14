#!/usr/bin/env python3
"""Sanitizer for address-pr-comments-review eval outputs.

RED summary mode: reads Score JSON, outputs canonical sorted-key compact JSON to
  content-addressed path (<output-dir>/<sha256>.json).
GREEN output mode: reads response text, canonicalizes, outputs to content-addressed
  path (<output-dir>/<sha256>.md).

Rejects: NUL bytes, absolute paths, forbidden tokens, file:// URIs.
stdlib only. No external dependencies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from typing import NoReturn


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA_VERSION = 1

# ---------------------------------------------------------------------------
# Forbidden pattern sets
# ---------------------------------------------------------------------------

# Casefold words checked with ASCII identifier boundaries
_FORBIDDEN_CASEFOLD_RE = re.compile(
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

# Absolute path patterns to reject (anywhere in content)
_PATH_REJECT_RE = re.compile(
    r"(?:^|\s)(/Users/|/home/)|(?:^|\s)([A-Za-z]:[\\/])|file://",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _die(message: str, exit_code: int = 2) -> NoReturn:
    sys.stderr.write(message + "\n")
    sys.exit(exit_code)


def _format_json_bytes(obj: object) -> str:
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return text + "\n"


# ---------------------------------------------------------------------------
# Canonicalization
# ---------------------------------------------------------------------------


def _canonicalize_text(raw: str) -> bytes:
    """CRLF/CR→LF, strip trailing space/tab per line, trim outer blanks, append LF."""
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


def _canonical_json_bytes(obj: object) -> bytes:
    """Sorted keys, compact separators, no trailing whitespace, one trailing LF."""
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return (text + "\n").encode("utf-8")


# ---------------------------------------------------------------------------
# Validation (shared between modes)
# ---------------------------------------------------------------------------


def _validate_text(text: str) -> None:
    """Reject NUL, absolute paths, forbidden tokens, file:// URIs."""
    # NUL bytes
    if "\x00" in text:
        _die("Content contains NUL byte", 2)

    # Absolute path patterns
    for line in text.split("\n"):
        if _PATH_REJECT_RE.search(line):
            _die(f"Absolute path rejected: {line[:120]}", 2)

    # Casefold forbidden words
    cf_match = _FORBIDDEN_CASEFOLD_RE.search(text)
    if cf_match:
        _die(f"Forbidden casefold word found: {cf_match.group(0)}", 2)

    # Case-sensitive forbidden substrings
    for sub in _FORBIDDEN_SUBSTRINGS:
        if sub in text:
            _die(f"Forbidden substring found: {sub}", 2)


# ---------------------------------------------------------------------------
# RED summary mode
# ---------------------------------------------------------------------------


def _do_red_summary(
    response_path: str,
    score_path: str,
    receipt_path: str,
    output_dir: str,
) -> str:
    """Sanitize RED summary: read score JSON, validate, write content-addressed."""
    # Read score file
    try:
        with open(score_path, "rb") as fh:
            score_raw = fh.read()
    except OSError as e:
        _die(f"Cannot read score file: {e}", 2)

    # Validate UTF-8
    try:
        score_text = score_raw.decode("utf-8")
    except UnicodeDecodeError as e:
        _die(f"Score file is not valid UTF-8: {e}", 2)

    # Parse JSON to validate structure
    try:
        score_obj = json.loads(score_text)
    except (json.JSONDecodeError, ValueError) as e:
        _die(f"Score file is not valid JSON: {e}", 2)

    if not isinstance(score_obj, dict):
        _die("Score file is not a JSON object", 2)

    # Validate score content against forbidden patterns
    _validate_text(score_text)

    # Write canonical JSON (sorted keys, compact)
    output_bytes = _canonical_json_bytes(score_obj)

    # Content-addressed write
    sha = _sha256_hex(output_bytes)
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, f"{sha}.json")

    with open(out_path, "wb") as fh:
        fh.write(output_bytes)

    return sha


# ---------------------------------------------------------------------------
# GREEN output mode
# ---------------------------------------------------------------------------


def _do_green_output(
    response_path: str,
    score_path: str,
    receipt_path: str,
    output_dir: str,
) -> str:
    """Sanitize GREEN output: canonicalize response text, validate, write content-addressed."""
    # Read response file
    try:
        with open(response_path, "rb") as fh:
            response_raw = fh.read()
    except OSError as e:
        _die(f"Cannot read response file: {e}", 2)

    # Validate UTF-8
    try:
        response_text = response_raw.decode("utf-8")
    except UnicodeDecodeError as e:
        _die(f"Response file is not valid UTF-8: {e}", 2)

    # Canonicalize text
    output_bytes = _canonicalize_text(response_text)

    # Validate canonicalized content
    _validate_text(output_bytes.decode("utf-8"))

    # Content-addressed write
    sha = _sha256_hex(output_bytes)
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, f"{sha}.md")

    with open(out_path, "wb") as fh:
        fh.write(output_bytes)

    return sha


# ---------------------------------------------------------------------------
# CLI setup
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sanitizer for address-pr-comments-review eval outputs"
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=["red-summary", "green-output"],
        help="Sanitization mode",
    )
    parser.add_argument(
        "--response",
        type=str,
        default="",
        help="Path to response file (GREEN mode source)",
    )
    parser.add_argument(
        "--score",
        type=str,
        default="",
        help="Path to score JSON file (RED mode source)",
    )
    parser.add_argument(
        "--receipt",
        type=str,
        default="",
        help="Path to receipt JSON file (for context, not directly consumed)",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=str,
        dest="output_dir",
        help="Directory for content-addressed output files",
    )
    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    mode: str = args.mode
    response_path: str = args.response
    score_path: str = args.score
    receipt_path: str = args.receipt
    output_dir: str = args.output_dir

    try:
        if mode == "red-summary":
            sha = _do_red_summary(response_path, score_path, receipt_path, output_dir)
        elif mode == "green-output":
            sha = _do_green_output(response_path, score_path, receipt_path, output_dir)
        else:
            _die(f"Unknown mode: {mode}", 2)

        output_obj = {
            "schema_version": SCHEMA_VERSION,
            "operation": "sanitize",
            "mode": mode,
            "output_sha256": sha,
            "output_path": os.path.join(
                output_dir, f"{sha}.{'json' if mode == 'red-summary' else 'md'}"
            ),
        }

        print(_format_json_bytes(output_obj), end="", flush=True)

    except OSError as e:
        _die(f"I/O error: {e}", 4)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
