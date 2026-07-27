from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import NoReturn, TypeAlias, TypeGuard, TypedDict, cast


JsonValue: TypeAlias = (
    None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
)


SCRIPT_DIR = Path(__file__).resolve().parent
REGRESSIONS_DIR = SCRIPT_DIR / "address-pr-comments-review-regressions"
EXPECTED_CASE_IDS = (
    "route-review-dossier",
    "route-direct-fix",
    "route-reply-only",
    "route-no-action",
    "checkout-mismatch",
    "stale-evidence",
    "dirty-target",
    "index-nonempty",
    "lifecycle-legal",
    "lifecycle-illegal",
    "lifecycle-status-write-failure",
    "lifecycle-lock-cas",
    "commit-parent-path",
    "commit-fork-remote",
    "commit-push-resume",
    "reply-preexisting",
    "reply-marker-conflict",
    "reply-ambiguous",
    "cleanup-matrix",
    "cleanup-recovery",
)


class RegressionCase(TypedDict):
    case_id: str
    driver: str
    fixture_path: str
    fixture_sha256: str
    argv: list[str]
    stdin_base64: str
    env: dict[str, str]
    expected_exit: int
    expected_stdout: str
    expected_diagnostic: str
    sentinels: list[str]


class RegressionManifest(TypedDict):
    schema_version: int
    case_ids_sha256: str
    cases: list[RegressionCase]


class _DuplicateJSONKeyError(ValueError):
    pass


def _reject_duplicate_json_keys(
    pairs: list[tuple[str, JsonValue]],
) -> dict[str, JsonValue]:
    parsed: dict[str, JsonValue] = {}
    for key, value in pairs:
        if key in parsed:
            raise _DuplicateJSONKeyError(key)
        parsed[key] = value
    return parsed


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha256(path: Path) -> str:
    return _sha256_hex(path.read_bytes())


def _die(message: str, exit_code: int = 2) -> NoReturn:
    print(message, file=sys.stderr)
    raise SystemExit(exit_code)


def validate_manifest(value: JsonValue) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["Manifest is not a JSON object"]
    manifest = cast(dict[str, JsonValue], value)

    required_manifest_fields = {"schema_version", "case_ids_sha256", "cases"}
    missing_manifest_fields = required_manifest_fields - set(manifest)
    unexpected_manifest_fields = set(manifest) - required_manifest_fields
    if missing_manifest_fields:
        errors.append(f"Manifest missing fields: {sorted(missing_manifest_fields)}")
    if unexpected_manifest_fields:
        errors.append(
            f"Manifest unexpected fields: {sorted(unexpected_manifest_fields)}"
        )
    schema_version = manifest.get("schema_version")
    if type(schema_version) is not int or schema_version != 1:
        errors.append("schema_version must be integer 1")

    cases_value = manifest.get("cases")
    if not isinstance(cases_value, list):
        errors.append("'cases' must be an array")
        return errors
    cases = cast(list[JsonValue], cases_value)
    if len(cases) != len(EXPECTED_CASE_IDS):
        errors.append(f"Expected {len(EXPECTED_CASE_IDS)} cases, got {len(cases)}")

    required_fields = set(RegressionCase.__required_keys__)
    seen_ids: set[str] = set()
    actual_ids: list[str] = []
    for index, case_value in enumerate(cases):
        if not isinstance(case_value, dict):
            errors.append(f"Case {index}: not a JSON object")
            continue
        case = cast(dict[str, JsonValue], case_value)
        missing = required_fields - set(case)
        unexpected = set(case) - required_fields
        if missing:
            errors.append(f"Case {index}: missing fields: {sorted(missing)}")
        if unexpected:
            errors.append(f"Case {index}: unexpected fields: {sorted(unexpected)}")

        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            errors.append(f"Case {index}: case_id must be a non-empty string")
            case_label = str(index)
        else:
            case_label = case_id
            actual_ids.append(case_id)
            if case_id in seen_ids:
                errors.append(f"Duplicate case_id: {case_id}")
            seen_ids.add(case_id)

        driver = case.get("driver")
        if driver not in ("contract", "helper"):
            errors.append(f"Case '{case_label}': invalid driver '{driver}'")
        argv_value = case.get("argv")
        if (
            not isinstance(argv_value, list)
            or not argv_value
            or not all(
                isinstance(item, str) for item in cast(list[JsonValue], argv_value)
            )
        ):
            errors.append(f"Case '{case_label}': argv must be a non-empty string list")
        env_value = case.get("env")
        if not isinstance(env_value, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in cast(dict[str, JsonValue], env_value).items()
        ):
            errors.append(f"Case '{case_label}': env must map strings to strings")
        if type(case.get("expected_exit")) is not int:
            errors.append(f"Case '{case_label}': expected_exit must be an integer")
        sentinels_value = case.get("sentinels")
        if not isinstance(sentinels_value, list) or not all(
            isinstance(item, str) for item in cast(list[JsonValue], sentinels_value)
        ):
            errors.append(f"Case '{case_label}': sentinels must be a string list")
        for field in ("stdin_base64", "expected_stdout", "expected_diagnostic"):
            if not isinstance(case.get(field), str):
                errors.append(f"Case '{case_label}': {field} must be a string")

        fixture_path = case.get("fixture_path")
        fixture_sha256 = case.get("fixture_sha256")
        if not isinstance(fixture_path, str) or not isinstance(fixture_sha256, str):
            errors.append(
                f"Case '{case_label}': fixture path and SHA-256 must be strings"
            )
            continue
        fixture = (REGRESSIONS_DIR / fixture_path).resolve()
        if not fixture.is_relative_to(REGRESSIONS_DIR.resolve()):
            errors.append(
                f"Case '{case_label}': fixture_path escapes regressions directory"
            )
        elif not fixture.is_file():
            errors.append(f"Case '{case_label}': fixture not found: {fixture_path}")
        elif len(fixture_sha256) != 64 or any(
            char not in "0123456789abcdef" for char in fixture_sha256
        ):
            errors.append(f"Case '{case_label}': fixture_sha256 must be lowercase hex")
        elif _file_sha256(fixture) != fixture_sha256:
            errors.append(f"Case '{case_label}': fixture_sha256 mismatch")

    if tuple(actual_ids) != EXPECTED_CASE_IDS:
        errors.append("case_id inventory mismatch")

    expected_ids_path = REGRESSIONS_DIR / "case-ids.txt"
    if not expected_ids_path.is_file():
        errors.append("case ID catalog not found")
        return errors
    try:
        ids_text = expected_ids_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        errors.append(f"case ID catalog unreadable: {error}")
        return errors
    if tuple(ids_text.splitlines()) != EXPECTED_CASE_IDS:
        errors.append("case ID catalog mismatch")
    computed_sha = _sha256_hex(ids_text.encode("utf-8"))
    declared_sha = manifest.get("case_ids_sha256")
    if not isinstance(declared_sha, str):
        errors.append("case_ids_sha256 must be a string")
    elif declared_sha != computed_sha:
        errors.append(
            f"case_ids_sha256 mismatch: declared={declared_sha}, computed={computed_sha}"
        )
    return errors


def is_regression_manifest(value: JsonValue) -> TypeGuard[RegressionManifest]:
    return not validate_manifest(value)


def load_manifest() -> JsonValue:
    manifest_path = REGRESSIONS_DIR / "cases.json"
    if not manifest_path.exists():
        _die(f"Manifest not found: {manifest_path}")
    try:
        manifest_raw = manifest_path.read_bytes()
    except OSError as error:
        _die(f"Failed to load manifest: {error}")
    try:
        manifest_text = manifest_raw.decode("utf-8")
    except UnicodeDecodeError:
        _die("Failed to load manifest: invalid UTF-8")
    try:
        return cast(
            JsonValue,
            json.loads(
                manifest_text,
                object_pairs_hook=_reject_duplicate_json_keys,
            ),
        )
    except _DuplicateJSONKeyError as error:
        _die(f"Failed to load manifest: duplicate JSON key: {error}")
    except json.JSONDecodeError as error:
        _die(f"Failed to load manifest: {error}")
