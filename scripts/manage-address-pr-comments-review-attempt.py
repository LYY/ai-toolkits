#!/usr/bin/env python3
"""Attempt lifecycle manager for address-pr-comments-review.

POSIX-only. Uses fcntl.flock for concurrency-safe state management.
State stored under XDG_STATE_HOME (default ~/.local/state).
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import pathlib
import stat
import sys
import uuid
from typing import NoReturn

# -- POSIX guard: exit 2 before creating any state if fcntl unavailable --
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

APP_NAME = "ai-toolkits"
SUBDIR = "address-pr-comments-review-executor-neutral"

SCHEMA_VERSION = 1

DIAG_SCHEMA_INVALID = "schema-invalid"
DIAG_PLATFORM_UNSUPPORTED = "platform-unsupported"
DIAG_LOCK_BUSY = "lock-busy"
DIAG_CAS_MISMATCH = "cas-mismatch"
DIAG_IDENTITY_MISMATCH = "identity-mismatch"
DIAG_RECOVERY_REQUIRED = "recovery-required"
DIAG_IO_ERROR = "io-error"

STATE_BOOTSTRAPPING = "bootstrapping"
STATE_ACTIVE = "active"
STATE_COMPLETED = "completed"


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def _state_base() -> pathlib.Path:
    xdg = os.environ.get("XDG_STATE_HOME")
    if xdg:
        return pathlib.Path(xdg) / APP_NAME / SUBDIR
    return pathlib.Path.home() / ".local" / "state" / APP_NAME / SUBDIR


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _repo_root_sha256(repo_root: pathlib.Path) -> str:
    """SHA-256 of canonical absolute repo root path (UTF-8) plus LF."""
    canonical = str(repo_root.resolve()).encode("utf-8")
    return _sha256_hex(canonical + b"\n")


def _locks_dir() -> pathlib.Path:
    return _state_base() / "locks"


def _active_dir() -> pathlib.Path:
    return _state_base() / "active"


def _attempts_dir() -> pathlib.Path:
    return _state_base() / "attempts"


def _lock_path(repo_root_sha: str) -> pathlib.Path:
    return _locks_dir() / f"{repo_root_sha}.lock"


def _pointer_path(repo_root_sha: str) -> pathlib.Path:
    return _active_dir() / f"{repo_root_sha}.json"


def _attempt_base(repo_root_sha: str, attempt_id: str) -> pathlib.Path:
    return _attempts_dir() / repo_root_sha / attempt_id


def _attempt_json_path(repo_root_sha: str, attempt_id: str) -> pathlib.Path:
    return _attempt_base(repo_root_sha, attempt_id) / "attempt.json"


# ---------------------------------------------------------------------------
# Filesystem & ownership
# ---------------------------------------------------------------------------


def _ensure_dir(path: pathlib.Path, mode: int = 0o700) -> None:
    """Create directory with ownership enforcement. Fails on symlinks."""
    if path.exists():
        if path.is_symlink():
            raise OSError(f"Path is a symlink, refusing: {path}")
        if not path.is_dir():
            raise OSError(f"Path exists and is not a directory: {path}")
        return

    # Walk up to find first existing ancestor
    ancestors: list[pathlib.Path] = []
    p = path
    while p != p.parent:
        if p.exists():
            break
        ancestors.append(p)
        p = p.parent
    # Check that all existing ancestors are real non-symlink directories
    for ancestor_chain in reversed(list(path.parents)):
        if ancestor_chain == path:
            continue
        if not ancestor_chain.exists():
            continue
        if ancestor_chain.is_symlink():
            raise OSError(f"Ancestor is symlink, refusing: {ancestor_chain}")
        if not ancestor_chain.is_dir():
            raise OSError(f"Ancestor is not a directory: {ancestor_chain}")
        break  # found existing ancestor

    path.mkdir(mode=mode, parents=True, exist_ok=True)


def _write_atomic(path: pathlib.Path, content: bytes, mode: int = 0o600) -> None:
    """Write content to a temp file, fsync, then rename over target."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
        try:
            os.write(fd, content)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Canonical JSON
# ---------------------------------------------------------------------------


def _canonical_json(obj: object) -> bytes:
    """Sorted keys, compact separators, no trailing whitespace, one trailing LF."""
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return (text + "\n").encode("utf-8")


def _format_json_bytes(obj: object) -> str:
    """Return canonical JSON as decoded string (for stdout)."""
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return text + "\n"


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
# Lock helper
# ---------------------------------------------------------------------------


def _acquire_lock(lock_path: pathlib.Path) -> int:
    """Acquire exclusive flock on lock file. Returns fd. Exits on busy."""
    _ensure_dir(lock_path.parent, mode=0o700)

    # Create lock file if absent (mode 0600, never unlink)
    if not lock_path.exists():
        fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.close(fd)

    fd = os.open(lock_path, os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        _die("open", DIAG_LOCK_BUSY, f"Lock busy: {lock_path}", 3)
    except OSError:
        os.close(fd)
        _die("open", DIAG_LOCK_BUSY, f"Lock busy: {lock_path}", 3)
    return fd


def _release_lock(fd: int, lock_path: pathlib.Path) -> None:
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    except OSError:
        pass
    try:
        os.close(fd)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Plan normalization
# ---------------------------------------------------------------------------


def _normalize_plan(plan_path: pathlib.Path) -> bytes:
    """Normalize plan file: newline-normalize, strip line-end space/tab, trim outer blanks, append LF."""
    raw = plan_path.read_bytes().decode("utf-8")
    # Normalize line endings to LF
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    # Strip trailing space/tab from each line
    lines = raw.split("\n")
    lines = [line.rstrip(" \t") for line in lines]
    # Trim outer blank lines
    while lines and lines[0] == "":
        lines.pop(0)
    while lines and lines[-1] == "":
        lines.pop()
    normalized = "\n".join(lines)
    if normalized:
        normalized += "\n"
    return normalized.encode("utf-8")


# ---------------------------------------------------------------------------
# UUID generation
# ---------------------------------------------------------------------------


def _uuid4() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Timestamp
# ---------------------------------------------------------------------------


def _now_rfc3339() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# SHA-256 of file content
# ---------------------------------------------------------------------------


def _file_sha256(path: pathlib.Path) -> str:
    return _sha256_hex(path.read_bytes())


# ---------------------------------------------------------------------------
# Pointer read/write
# ---------------------------------------------------------------------------


def _read_pointer(repo_root_sha: str, operation: str) -> tuple[dict | None, bytes]:
    """Read pointer file. Returns (parsed, raw_bytes)."""
    p = _pointer_path(repo_root_sha)
    if not p.exists():
        return None, b""
    raw = p.read_bytes()
    try:
        obj: object = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        _die(operation, DIAG_SCHEMA_INVALID, f"Invalid JSON in pointer: {p}", 2)
    if not (isinstance(obj, dict) and obj.get("schema_version") == SCHEMA_VERSION):
        _die(operation, DIAG_SCHEMA_INVALID, f"Invalid schema in pointer: {p}", 2)
    return obj, raw  # type: ignore[return-value]


def _write_pointer(repo_root_sha: str, pointer: dict) -> bytes:
    """Write pointer atomically. Returns canonical bytes written."""
    _ensure_dir(_active_dir(), mode=0o700)
    p = _pointer_path(repo_root_sha)
    data = _canonical_json(pointer)
    _write_atomic(p, data, mode=0o600)
    return data


def _pointer_sha256(pointer: dict) -> str:
    return _sha256_hex(_canonical_json(pointer))


# ---------------------------------------------------------------------------
# Attempt helpers
# ---------------------------------------------------------------------------


def _read_attempt_json(
    repo_root_sha: str, attempt_id: str, operation: str
) -> tuple[dict, bytes]:
    p = _attempt_json_path(repo_root_sha, attempt_id)
    if not p.exists():
        _die(operation, DIAG_IO_ERROR, f"attempt.json missing: {p}", 4)
    raw = p.read_bytes()
    try:
        obj: object = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        _die(operation, DIAG_SCHEMA_INVALID, f"Invalid JSON in attempt.json: {p}", 2)
    if not (isinstance(obj, dict) and obj.get("schema_version") == SCHEMA_VERSION):
        _die(operation, DIAG_SCHEMA_INVALID, f"Invalid schema in attempt.json: {p}", 2)
    return obj, raw  # type: ignore[return-value]


def _write_attempt_json(repo_root_sha: str, attempt_id: str, obj: dict) -> bytes:
    _ensure_dir(_attempts_dir() / repo_root_sha / attempt_id, mode=0o700)
    p = _attempt_json_path(repo_root_sha, attempt_id)
    data = _canonical_json(obj)
    _write_atomic(p, data, mode=0o600)
    return data


# ---------------------------------------------------------------------------
# OPEN command
# ---------------------------------------------------------------------------


def _do_open(args: argparse.Namespace) -> None:
    operation = "open"

    repo_root = pathlib.Path(args.repo_root).resolve()
    generation_head = args.generation_head
    plan_path = pathlib.Path(args.plan)

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

    repo_root_sha = _repo_root_sha256(repo_root)
    plan_normalized = _normalize_plan(plan_path)
    plan_normalized_sha256 = _sha256_hex(plan_normalized)
    lock_p = _lock_path(repo_root_sha)

    fd = _acquire_lock(lock_p)
    try:
        pointer, _ = _read_pointer(repo_root_sha, operation)

        now = _now_rfc3339()

        if pointer is None:
            # Fresh: create bootstrapping pointer
            attempt_id = _uuid4()
            attempt_base = _attempt_base(repo_root_sha, attempt_id)

            # Create attempt dir and write attempt.json
            _ensure_dir(attempt_base, mode=0o700)
            attempt_obj = {
                "schema_version": SCHEMA_VERSION,
                "attempt_id": attempt_id,
                "repo_root_sha256": repo_root_sha,
                "generation_head": generation_head,
                "plan_normalized_sha256": plan_normalized_sha256,
                "created_at": now,
            }
            _write_attempt_json(repo_root_sha, attempt_id, attempt_obj)

            # Write bootstrapping pointer
            new_pointer = {
                "schema_version": SCHEMA_VERSION,
                "repo_root_sha256": repo_root_sha,
                "attempt_id": attempt_id,
                "attempt_path": str(attempt_base),
                "state": STATE_BOOTSTRAPPING,
                "generation_head": generation_head,
                "plan_normalized_sha256": plan_normalized_sha256,
                "aggregate_sha256": None,
                "updated_at": now,
            }
            _write_pointer(repo_root_sha, new_pointer)

            # CAS: read back and verify
            read_back, _ = _read_pointer(repo_root_sha, operation)
            if read_back is None or read_back.get("attempt_id") != attempt_id:
                _die(
                    operation, DIAG_CAS_MISMATCH, "CAS read-back failed after create", 3
                )

            # Transition to active and read-back
            new_pointer["state"] = STATE_ACTIVE
            new_pointer["updated_at"] = _now_rfc3339()
            _write_pointer(repo_root_sha, new_pointer)

            read_back, _ = _read_pointer(repo_root_sha, operation)
            if read_back is None or read_back.get("state") != STATE_ACTIVE:
                _die(
                    operation,
                    DIAG_CAS_MISMATCH,
                    "CAS read-back failed after active transition",
                    3,
                )

            pointer_sha = _pointer_sha256(new_pointer)
            print(
                _format_json_bytes(
                    {
                        "schema_version": SCHEMA_VERSION,
                        "operation": operation,
                        "status": "created",
                        "attempt_id": attempt_id,
                        "attempt_path": str(attempt_base),
                        "pointer_sha256": pointer_sha,
                    }
                ),
                end="",
                flush=True,
            )

        elif pointer.get("state") == STATE_BOOTSTRAPPING:
            # Resume bootstrapping
            attempt_id = pointer["attempt_id"]
            attempt_dir = pathlib.Path(pointer["attempt_path"])

            # Verify directory absent or empty dir + attempt.json
            if attempt_dir.exists():
                if attempt_dir.is_symlink():
                    _die(operation, DIAG_RECOVERY_REQUIRED, "Attempt dir is symlink", 3)
                if not attempt_dir.is_dir():
                    _die(
                        operation,
                        DIAG_RECOVERY_REQUIRED,
                        "Attempt dir is not a directory",
                        3,
                    )
                entries = list(attempt_dir.iterdir())
                aj = _attempt_json_path(repo_root_sha, attempt_id)
                # Allowed: empty dir, or exactly attempt.json (no other files)
                ok_empty = len(entries) == 0
                ok_aj_only = len(entries) == 1 and entries[0] == aj
                if not (ok_empty or ok_aj_only):
                    _die(
                        operation,
                        DIAG_RECOVERY_REQUIRED,
                        "Bootstrapping dir has unexpected content",
                        3,
                    )

            # Write attempt.json if missing
            if not _attempt_json_path(repo_root_sha, attempt_id).exists():
                attempt_obj = {
                    "schema_version": SCHEMA_VERSION,
                    "attempt_id": attempt_id,
                    "repo_root_sha256": repo_root_sha,
                    "generation_head": generation_head,
                    "plan_normalized_sha256": plan_normalized_sha256,
                    "created_at": pointer.get("updated_at", now),
                }
                _write_attempt_json(repo_root_sha, attempt_id, attempt_obj)

            # Transition to active
            pointer["state"] = STATE_ACTIVE
            pointer["generation_head"] = generation_head
            pointer["plan_normalized_sha256"] = plan_normalized_sha256
            pointer["updated_at"] = _now_rfc3339()
            _write_pointer(repo_root_sha, pointer)

            read_back, _ = _read_pointer(repo_root_sha, operation)
            if read_back is None or read_back.get("state") != STATE_ACTIVE:
                _die(
                    operation, DIAG_CAS_MISMATCH, "CAS read-back failed after resume", 3
                )

            pointer_sha = _pointer_sha256(pointer)
            print(
                _format_json_bytes(
                    {
                        "schema_version": SCHEMA_VERSION,
                        "operation": operation,
                        "status": "resumed",
                        "attempt_id": attempt_id,
                        "attempt_path": pointer["attempt_path"],
                        "pointer_sha256": pointer_sha,
                    }
                ),
                end="",
                flush=True,
            )

        elif pointer.get("state") == STATE_ACTIVE:
            # Resume active: validate identity
            if pointer["repo_root_sha256"] != repo_root_sha:
                _die(operation, DIAG_IDENTITY_MISMATCH, "repo_root mismatch", 2)
            if pointer["generation_head"] != generation_head:
                _die(
                    operation,
                    DIAG_IDENTITY_MISMATCH,
                    f"generation_head mismatch: got {generation_head}, expected {pointer['generation_head']}",
                    2,
                )
            if pointer["plan_normalized_sha256"] != plan_normalized_sha256:
                _die(operation, DIAG_IDENTITY_MISMATCH, "plan mismatch", 2)

            pointer["updated_at"] = now
            _write_pointer(repo_root_sha, pointer)

            pointer_sha = _pointer_sha256(pointer)
            print(
                _format_json_bytes(
                    {
                        "schema_version": SCHEMA_VERSION,
                        "operation": operation,
                        "status": "resumed",
                        "attempt_id": pointer["attempt_id"],
                        "attempt_path": pointer["attempt_path"],
                        "pointer_sha256": pointer_sha,
                    }
                ),
                end="",
                flush=True,
            )

        elif pointer.get("state") == STATE_COMPLETED:
            # Completed: validate, read-back, then start new UUID without scanning
            # Validate identity matches
            if pointer["repo_root_sha256"] != repo_root_sha:
                _die(operation, DIAG_IDENTITY_MISMATCH, "repo_root mismatch", 2)
            if pointer["generation_head"] != generation_head:
                _die(
                    operation,
                    DIAG_IDENTITY_MISMATCH,
                    f"generation_head mismatch: got {generation_head}, expected {pointer['generation_head']}",
                    2,
                )
            if pointer["plan_normalized_sha256"] != plan_normalized_sha256:
                _die(operation, DIAG_IDENTITY_MISMATCH, "plan mismatch", 2)

            # Verify pointer still on disk matches
            read_back, raw_back = _read_pointer(repo_root_sha, operation)
            if read_back is None or read_back.get("state") != STATE_COMPLETED:
                _die(
                    operation, DIAG_CAS_MISMATCH, "Pointer changed during read-back", 3
                )

            # Start new attempt
            attempt_id = _uuid4()
            attempt_base = _attempt_base(repo_root_sha, attempt_id)

            _ensure_dir(attempt_base, mode=0o700)
            attempt_obj = {
                "schema_version": SCHEMA_VERSION,
                "attempt_id": attempt_id,
                "repo_root_sha256": repo_root_sha,
                "generation_head": generation_head,
                "plan_normalized_sha256": plan_normalized_sha256,
                "created_at": now,
            }
            _write_attempt_json(repo_root_sha, attempt_id, attempt_obj)

            new_pointer = {
                "schema_version": SCHEMA_VERSION,
                "repo_root_sha256": repo_root_sha,
                "attempt_id": attempt_id,
                "attempt_path": str(attempt_base),
                "state": STATE_BOOTSTRAPPING,
                "generation_head": generation_head,
                "plan_normalized_sha256": plan_normalized_sha256,
                "aggregate_sha256": None,
                "updated_at": now,
            }
            _write_pointer(repo_root_sha, new_pointer)

            read_back, _ = _read_pointer(repo_root_sha, operation)
            if read_back is None or read_back.get("attempt_id") != attempt_id:
                _die(
                    operation,
                    DIAG_CAS_MISMATCH,
                    "CAS read-back failed after new create",
                    3,
                )

            new_pointer["state"] = STATE_ACTIVE
            new_pointer["updated_at"] = _now_rfc3339()
            _write_pointer(repo_root_sha, new_pointer)

            read_back, _ = _read_pointer(repo_root_sha, operation)
            if read_back is None or read_back.get("state") != STATE_ACTIVE:
                _die(
                    operation,
                    DIAG_CAS_MISMATCH,
                    "CAS read-back failed after active transition",
                    3,
                )

            pointer_sha = _pointer_sha256(new_pointer)
            print(
                _format_json_bytes(
                    {
                        "schema_version": SCHEMA_VERSION,
                        "operation": operation,
                        "status": "created",
                        "attempt_id": attempt_id,
                        "attempt_path": str(attempt_base),
                        "pointer_sha256": pointer_sha,
                    }
                ),
                end="",
                flush=True,
            )

        else:
            _die(
                operation,
                DIAG_SCHEMA_INVALID,
                f"Unknown pointer state: {pointer.get('state')}",
                2,
            )

    finally:
        _release_lock(fd, lock_p)


# ---------------------------------------------------------------------------
# COMPLETE command
# ---------------------------------------------------------------------------


def _do_complete(args: argparse.Namespace) -> None:
    operation = "complete"

    repo_root = pathlib.Path(args.repo_root).resolve()
    attempt_id = args.attempt_id
    pointer_sha_input = args.pointer_sha256
    aggregate_path = pathlib.Path(args.aggregate)

    repo_root_sha = _repo_root_sha256(repo_root)
    lock_p = _lock_path(repo_root_sha)

    fd = _acquire_lock(lock_p)
    try:
        pointer, _ = _read_pointer(repo_root_sha, operation)

        if pointer is None:
            _die(operation, DIAG_IO_ERROR, "No active pointer found", 4)

        # Validate pointer SHA matches
        actual_sha = _pointer_sha256(pointer)
        if actual_sha != pointer_sha_input:
            _die(
                operation,
                DIAG_CAS_MISMATCH,
                f"Pointer SHA mismatch: got {pointer_sha_input}, expected {actual_sha}",
                3,
            )

        if pointer["attempt_id"] != attempt_id:
            _die(
                operation,
                DIAG_IDENTITY_MISMATCH,
                f"attempt_id mismatch: got {attempt_id}, expected {pointer['attempt_id']}",
                2,
            )

        if pointer.get("state") not in (STATE_ACTIVE, STATE_COMPLETED):
            _die(
                operation,
                DIAG_SCHEMA_INVALID,
                f"Cannot complete from state: {pointer.get('state')}",
                2,
            )

        attempt_dir = pathlib.Path(pointer["attempt_path"])

        # Read review-wave.json
        wave_path = attempt_dir / "final" / "review-wave.json"
        if not wave_path.exists():
            _die(
                operation, DIAG_IO_ERROR, f"review-wave.json not found: {wave_path}", 4
            )
        try:
            wave = json.loads(wave_path.read_bytes().decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            _die(
                operation,
                DIAG_SCHEMA_INVALID,
                f"Invalid JSON in review-wave.json: {wave_path}",
                2,
            )

        if wave.get("state") != "approved":
            _die(
                operation,
                DIAG_SCHEMA_INVALID,
                f"review-wave state must be 'approved', got: {wave.get('state')}",
                2,
            )

        # Derive aggregate.json path and validate
        derived_aggregate = wave_path.parent / "aggregate.json"
        if derived_aggregate.resolve() != aggregate_path.resolve():
            _die(
                operation,
                DIAG_IO_ERROR,
                f"Aggregate path mismatch: expected {derived_aggregate}",
                4,
            )

        if not aggregate_path.exists():
            _die(
                operation,
                DIAG_IO_ERROR,
                f"aggregate.json not found: {aggregate_path}",
                4,
            )

        # Compute aggregate SHA-256
        aggregate_sha256 = _file_sha256(aggregate_path)

        # If already completed with same aggregate, idempotent
        if pointer.get("state") == STATE_COMPLETED:
            if pointer.get("aggregate_sha256") == aggregate_sha256:
                print(
                    _format_json_bytes(
                        {
                            "schema_version": SCHEMA_VERSION,
                            "operation": operation,
                            "status": "already-completed",
                            "attempt_id": attempt_id,
                            "pointer_sha256": actual_sha,
                        }
                    ),
                    end="",
                    flush=True,
                )
                return
            # Different aggregate = mismatch
            _die(
                operation,
                DIAG_CAS_MISMATCH,
                "State already completed with different aggregate",
                3,
            )

        # CAS active → completed
        pointer["state"] = STATE_COMPLETED
        pointer["aggregate_sha256"] = aggregate_sha256
        pointer["updated_at"] = _now_rfc3339()
        _write_pointer(repo_root_sha, pointer)

        read_back, _ = _read_pointer(repo_root_sha, operation)
        if read_back is None or read_back.get("state") != STATE_COMPLETED:
            _die(operation, DIAG_CAS_MISMATCH, "CAS read-back failed after complete", 3)
        if read_back.get("aggregate_sha256") != aggregate_sha256:
            _die(
                operation,
                DIAG_CAS_MISMATCH,
                "Aggregate SHA mismatch after read-back",
                3,
            )

        pointer_sha = _pointer_sha256(read_back)
        print(
            _format_json_bytes(
                {
                    "schema_version": SCHEMA_VERSION,
                    "operation": operation,
                    "status": "completed",
                    "attempt_id": attempt_id,
                    "pointer_sha256": pointer_sha,
                }
            ),
            end="",
            flush=True,
        )

    finally:
        _release_lock(fd, lock_p)


# ---------------------------------------------------------------------------
# STATUS command
# ---------------------------------------------------------------------------


def _do_status(args: argparse.Namespace) -> None:
    operation = "status"

    repo_root = pathlib.Path(args.repo_root).resolve()
    repo_root_sha = _repo_root_sha256(repo_root)
    lock_p = _lock_path(repo_root_sha)

    fd = _acquire_lock(lock_p)
    try:
        pointer, _ = _read_pointer(repo_root_sha, operation)
        ptr_sha = _pointer_sha256(pointer) if pointer else ""

        print(
            _format_json_bytes(
                {
                    "schema_version": SCHEMA_VERSION,
                    "operation": operation,
                    "pointer": pointer or None,
                    "pointer_sha256": ptr_sha,
                }
            ),
            end="",
            flush=True,
        )
    finally:
        _release_lock(fd, lock_p)


# ---------------------------------------------------------------------------
# SNAPSHOT-TREE command
# ---------------------------------------------------------------------------


def _do_snapshot_tree(args: argparse.Namespace) -> None:
    operation = "snapshot-tree"

    attempt_root = pathlib.Path(args.attempt_root).resolve()
    attempt_id = args.attempt_id
    root_path = pathlib.Path(args.root).resolve()
    includes = args.include_relative  # list of str
    output_path = pathlib.Path(args.output)

    # Validate attempt identity
    attempt_json_path = attempt_root / "attempt.json"
    try:
        aj_raw = attempt_json_path.read_bytes()
    except OSError as e:
        _die(operation, DIAG_IO_ERROR, f"Cannot read attempt.json: {e}", 4)
    try:
        aj = json.loads(aj_raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        _die(
            operation,
            DIAG_SCHEMA_INVALID,
            f"Invalid JSON in attempt.json: {attempt_json_path}",
            2,
        )

    if aj.get("attempt_id") != attempt_id:
        _die(
            operation,
            DIAG_IDENTITY_MISMATCH,
            f"attempt_id mismatch: expected {aj.get('attempt_id')}, got {attempt_id}",
            2,
        )

    # Verify plan_normalized_sha256 matches
    plan_path = attempt_root / "plan.normalized"
    if plan_path.exists():
        plan_content = plan_path.read_bytes()
        plan_sha = _sha256_hex(plan_content)
        if plan_sha != aj.get("plan_normalized_sha256"):
            _die(
                operation, DIAG_IDENTITY_MISMATCH, "plan_normalized_sha256 mismatch", 2
            )

    # generation_head should match
    if aj.get("generation_head"):
        # generation_head is in attempt JSON; we don't verify against git here
        # (this is independent of checked out state)
        pass

    # Validate output parent is real directory
    output_parent = output_path.parent.resolve()
    if not output_parent.exists():
        _die(
            operation,
            DIAG_IO_ERROR,
            f"Output parent does not exist: {output_parent}",
            4,
        )
    if output_parent.is_symlink():
        _die(operation, DIAG_IO_ERROR, f"Output parent is symlink: {output_parent}", 4)
    if not output_parent.is_dir():
        _die(
            operation,
            DIAG_IO_ERROR,
            f"Output parent is not a directory: {output_parent}",
            4,
        )

    # Verify output is a descendant of the same attempt root
    try:
        output_path.resolve().relative_to(attempt_root.resolve())
    except ValueError:
        _die(
            operation,
            DIAG_IO_ERROR,
            f"Output path {output_path} is not under attempt root {attempt_root}",
            4,
        )

    # Build entries for each included path
    entries: list[dict] = []
    for rel in includes:
        candidate = root_path / rel
        # Only include existing candidates
        if not candidate.exists():
            continue
        if candidate.is_symlink():
            # Do not follow
            st = candidate.lstat()
            target = os.readlink(str(candidate))
            entries.append(
                {
                    "relative_path": rel,
                    "type": "symlink",
                    "mode": oct(stat.S_IMODE(st.st_mode))[2:],
                    "sha256": None,
                    "link_target": target,
                }
            )
        elif candidate.is_file():
            st = candidate.lstat()
            entries.append(
                {
                    "relative_path": rel,
                    "type": "file",
                    "mode": oct(stat.S_IMODE(st.st_mode))[2:],
                    "sha256": _file_sha256(candidate),
                    "link_target": None,
                }
            )
        elif candidate.is_dir():
            st = candidate.lstat()
            entries.append(
                {
                    "relative_path": rel,
                    "type": "directory",
                    "mode": oct(stat.S_IMODE(st.st_mode))[2:],
                    "sha256": None,
                    "link_target": None,
                }
            )

    # Sort by POSIX relative-path UTF-8 bytes
    entries.sort(key=lambda e: e["relative_path"].encode("utf-8"))

    root_sha = _sha256_hex(root_path.resolve().as_posix().encode("utf-8") + b"\n")

    snapshot = {
        "schema_version": SCHEMA_VERSION,
        "attempt_id": attempt_id,
        "root_sha256": root_sha,
        "includes": list(includes),
        "entries": entries,
    }

    snapshot_bytes = _canonical_json(snapshot)
    snapshot_sha = _sha256_hex(snapshot_bytes)

    # Check if output already exists and is identical
    if output_path.exists():
        existing = output_path.read_bytes()
        if existing == snapshot_bytes:
            print(
                _format_json_bytes(
                    {
                        "schema_version": SCHEMA_VERSION,
                        "operation": operation,
                        "status": "unchanged",
                        "output_sha256": snapshot_sha,
                    }
                ),
                end="",
                flush=True,
            )
            return
        # Different content = mismatch
        _die(operation, DIAG_CAS_MISMATCH, "Output exists with different content", 3)

    _write_atomic(output_path, snapshot_bytes, mode=0o600)

    print(
        _format_json_bytes(
            {
                "schema_version": SCHEMA_VERSION,
                "operation": operation,
                "status": "created",
                "output_sha256": snapshot_sha,
            }
        ),
        end="",
        flush=True,
    )


# ---------------------------------------------------------------------------
# CLI setup
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Attempt lifecycle manager for address-pr-comments-review"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # open
    open_p = sub.add_parser("open", help="Open or resume an attempt")
    open_p.add_argument(
        "--repo-root", required=True, type=str, help="Repository root path"
    )
    open_p.add_argument(
        "--generation-head", required=True, type=str, help="40-char hex commit SHA"
    )
    open_p.add_argument("--plan", required=True, type=str, help="Path to plan file")

    # complete
    complete_p = sub.add_parser("complete", help="Complete an attempt")
    complete_p.add_argument(
        "--repo-root", required=True, type=str, help="Repository root path"
    )
    complete_p.add_argument(
        "--attempt-id", required=True, type=str, help="Attempt UUID"
    )
    complete_p.add_argument(
        "--pointer-sha256",
        required=True,
        type=str,
        dest="pointer_sha256",
        help="SHA-256 of current pointer (for CAS)",
    )
    complete_p.add_argument(
        "--aggregate", required=True, type=str, help="Path to aggregate.json"
    )

    # status
    status_p = sub.add_parser("status", help="Read pointer status")
    status_p.add_argument(
        "--repo-root", required=True, type=str, help="Repository root path"
    )

    # snapshot-tree
    snapshot_p = sub.add_parser("snapshot-tree", help="Create tree snapshot")
    snapshot_p.add_argument(
        "--attempt-root", required=True, type=str, help="Attempt directory"
    )
    snapshot_p.add_argument(
        "--attempt-id", required=True, type=str, help="Attempt UUID"
    )
    snapshot_p.add_argument("--root", required=True, type=str, help="Source tree root")
    snapshot_p.add_argument(
        "--include-relative",
        required=True,
        nargs="+",
        dest="include_relative",
        type=str,
        help="Relative paths to include",
    )
    snapshot_p.add_argument("--output", required=True, type=str, help="Output path")

    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        if args.command == "open":
            _do_open(args)
        elif args.command == "complete":
            _do_complete(args)
        elif args.command == "status":
            _do_status(args)
        elif args.command == "snapshot-tree":
            _do_snapshot_tree(args)
    except OSError as e:
        # Catch I/O errors that weren't explicitly handled
        print(_error(args.command, DIAG_IO_ERROR, str(e)), end="", flush=True)
        return 4

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
