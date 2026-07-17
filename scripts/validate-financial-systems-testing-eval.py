#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import NoReturn, cast


SCHEMA_VERSION = 1
CRITERIA = frozenset(
    {
        "FSE-01",
        "FSE-02",
        "FSE-03",
        "FSE-04",
        "FSE-05",
        "FSE-06",
        "FSE-07",
        "FSE-08",
    }
)
CASE_IDS = frozenset(
    {
        "money-rounding-source-missing",
        "ledger-transfer-conservation",
        "trade-partial-fill-cancel-race",
        "payment-timeout-unknown-outcome",
        "wallet-freeze-reversal",
        "risk-liquidation-price-source",
        "credit-decision-replay",
        "settlement-partial-dvp-calendar",
        "reconciliation-break-correction",
        "reference-data-effective-date",
        "generic-crud-tests",
        "generic-concurrency-test",
        "security-only-payment-api",
        "compliance-only-request",
    }
)
POSITIVE_GROUPS = frozenset(
    {
        "money-ledger",
        "transaction-lifecycle",
        "risk-settlement",
        "resilience-reference",
    }
)
NEGATIVE_GROUPS = frozenset({"generic", "security", "compliance"})
MANIFEST_FIELDS = frozenset(
    {
        "case_id",
        "prompt_path",
        "prompt_sha256",
        "expected_route",
        "applicable_references",
        "blocking_criteria",
        "branch_group",
    }
)
RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "run_id",
        "phase",
        "case_id",
        "producer_session_id",
        "producer_task_id",
        "grader_session_id",
        "grader_task_id",
        "grader_output_sha256",
        "prompt_sha256",
        "response_sha256",
        "rubric",
        "evidence",
    }
)
JsonObject = dict[str, object]


class ContractError(Exception):
    pass


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def load_json_object(path: Path, label: str) -> JsonObject:
    try:
        value = cast(object, json.loads(path.read_text(encoding="utf-8")))
    except OSError as error:
        raise ContractError(f"cannot read {label}: {error}") from error
    except json.JSONDecodeError as error:
        raise ContractError(f"invalid JSON {label}: {error}") from error
    if not isinstance(value, dict):
        raise ContractError(f"{label} must be a JSON object")
    return cast(JsonObject, value)


def required_string(value: JsonObject, key: str, label: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result:
        raise ContractError(f"{label} field {key} must be a non-empty string")
    return result


def required_strings(value: JsonObject, key: str, label: str) -> list[str]:
    result = value.get(key)
    if not isinstance(result, list):
        raise ContractError(f"{label} field {key} must be a string list")
    items = cast(list[object], result)
    if not all(isinstance(item, str) and item for item in items):
        raise ContractError(f"{label} field {key} must be a string list")
    return [cast(str, item) for item in items]


def require_sha256(value: str, label: str) -> None:
    if len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise ContractError(f"{label} must be 64 lowercase hex characters")


def validate_manifest(manifest_path: Path) -> list[JsonObject]:
    manifest = load_json_object(manifest_path, "manifest")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ContractError("manifest schema_version must be 1")
    raw_cases = manifest.get("cases")
    if not isinstance(raw_cases, list):
        raise ContractError("manifest cases must be an array")
    cases: list[JsonObject] = []
    seen_ids: set[str] = set()
    for raw_case in cast(list[object], raw_cases):
        if not isinstance(raw_case, dict):
            raise ContractError("manifest case must be an object")
        case = cast(JsonObject, raw_case)
        missing_fields = MANIFEST_FIELDS.difference(case)
        if missing_fields:
            raise ContractError(
                f"manifest case missing fields: {sorted(missing_fields)}"
            )
        case_id = required_string(case, "case_id", "manifest case")
        if case_id in seen_ids:
            raise ContractError(f"duplicate case_id: {case_id}")
        seen_ids.add(case_id)
        prompt_path = Path(required_string(case, "prompt_path", case_id))
        if prompt_path.is_absolute() or ".." in prompt_path.parts:
            raise ContractError(f"invalid prompt_path: {case_id}")
        prompt_sha256 = required_string(case, "prompt_sha256", case_id)
        require_sha256(prompt_sha256, f"prompt_sha256 for {case_id}")
        prompt_file = manifest_path.parent / prompt_path
        if not prompt_file.is_file():
            raise ContractError(f"prompt missing: {case_id}")
        if sha256_file(prompt_file) != prompt_sha256:
            raise ContractError(f"prompt_sha256 mismatch: {case_id}")
        _ = required_string(case, "expected_route", case_id)
        _ = required_strings(case, "applicable_references", case_id)
        criteria = required_strings(case, "blocking_criteria", case_id)
        if (
            not criteria
            or set(criteria).difference(CRITERIA)
            or len(criteria) != len(set(criteria))
        ):
            raise ContractError(f"invalid blocking_criteria: {case_id}")
        group = required_string(case, "branch_group", case_id)
        if group not in POSITIVE_GROUPS | NEGATIVE_GROUPS:
            raise ContractError(f"invalid branch_group: {case_id}")
        cases.append(case)
    if seen_ids != set(CASE_IDS):
        missing = sorted(CASE_IDS.difference(seen_ids))
        unexpected = sorted(seen_ids.difference(CASE_IDS))
        raise ContractError(
            f"case_id set mismatch: missing={missing} unexpected={unexpected}"
        )
    return cases


def validate_receipt(
    receipt: JsonObject, case: JsonObject, phase: str, receipt_path: Path
) -> None:
    label = receipt_path.name
    if set(receipt) != set(RECEIPT_FIELDS):
        raise ContractError(f"receipt fields mismatch: {label}")
    if receipt.get("schema_version") != SCHEMA_VERSION:
        raise ContractError(f"receipt schema_version must be 1: {label}")
    for field in (
        "run_id",
        "phase",
        "case_id",
        "producer_session_id",
        "producer_task_id",
        "grader_session_id",
        "grader_task_id",
        "grader_output_sha256",
        "prompt_sha256",
        "response_sha256",
    ):
        _ = required_string(receipt, field, label)
    if receipt["phase"] != phase:
        raise ContractError(f"receipt phase mismatch: {label}")
    if receipt["case_id"] != case["case_id"]:
        raise ContractError(f"receipt case_id mismatch: {label}")
    prompt_sha256 = required_string(receipt, "prompt_sha256", label)
    response_sha256 = required_string(receipt, "response_sha256", label)
    grader_output_sha256 = required_string(receipt, "grader_output_sha256", label)
    require_sha256(prompt_sha256, f"receipt prompt_sha256: {label}")
    require_sha256(response_sha256, f"receipt response_sha256: {label}")
    require_sha256(grader_output_sha256, f"grader_output_sha256: {label}")
    if prompt_sha256 != case["prompt_sha256"]:
        raise ContractError(f"receipt prompt_sha256 mismatch: {label}")
    producer_session_id = required_string(receipt, "producer_session_id", label)
    grader_session_id = required_string(receipt, "grader_session_id", label)
    producer_task_id = required_string(receipt, "producer_task_id", label)
    grader_task_id = required_string(receipt, "grader_task_id", label)
    if producer_session_id == grader_session_id:
        raise ContractError(f"grader_session_id must differ: {label}")
    if producer_task_id == grader_task_id:
        raise ContractError(f"grader_task_id must differ: {label}")
    response_path = receipt_path.parent / f"{case['case_id']}.response.md"
    if not response_path.is_file():
        raise ContractError(f"raw response missing: {label}")
    if sha256_file(response_path) != response_sha256:
        raise ContractError(f"response_sha256 mismatch: {label}")
    rubric = receipt.get("rubric")
    if not isinstance(rubric, dict):
        raise ContractError(f"receipt rubric must be an object: {label}")
    rubric_values = cast(JsonObject, rubric)
    criteria = set(required_strings(case, "blocking_criteria", label))
    if set(rubric_values) != criteria:
        raise ContractError(f"rubric keys mismatch: {label}")
    if not all(isinstance(result, bool) for result in rubric_values.values()):
        raise ContractError(f"rubric values must be boolean: {label}")
    evidence = receipt.get("evidence")
    if not isinstance(evidence, dict):
        raise ContractError(f"receipt evidence must be an object: {label}")
    evidence_values = cast(JsonObject, evidence)
    false_criteria = {
        criterion for criterion, result in rubric_values.items() if result is False
    }
    if set(evidence_values) != false_criteria:
        raise ContractError(f"evidence keys mismatch: {label}")
    if not all(isinstance(item, str) and item for item in evidence_values.values()):
        raise ContractError(f"evidence values must be non-empty strings: {label}")
    grader_path = receipt_path.parent / f"{case['case_id']}.grader.json"
    if not grader_path.is_file():
        raise ContractError(f"raw grader output missing: {label}")
    if sha256_file(grader_path) != grader_output_sha256:
        raise ContractError(f"grader_output_sha256 mismatch: {label}")
    grader_output = load_json_object(grader_path, f"grader output {grader_path.name}")
    if set(grader_output) != {"rubric", "evidence"}:
        raise ContractError(f"grader output fields mismatch: {label}")
    if (
        grader_output.get("rubric") != rubric_values
        or grader_output.get("evidence") != evidence_values
    ):
        raise ContractError(f"grader output verdict mismatch: {label}")


def load_receipts(
    receipts_path: Path, cases: list[JsonObject], phase: str
) -> dict[str, JsonObject]:
    if not receipts_path.is_dir():
        raise ContractError(f"receipts directory not found: {receipts_path}")
    case_by_id = {
        required_string(case, "case_id", "manifest case"): case for case in cases
    }
    receipts: dict[str, JsonObject] = {}
    seen_identity: set[tuple[str, str]] = set()
    for receipt_path in sorted(receipts_path.glob("*.receipt.json")):
        receipt = load_json_object(receipt_path, f"receipt {receipt_path.name}")
        case_id = required_string(receipt, "case_id", receipt_path.name)
        receipt_phase = required_string(receipt, "phase", receipt_path.name)
        identity = (receipt_phase, case_id)
        if identity in seen_identity:
            raise ContractError(
                f"duplicate receipt case/phase: {case_id}/{receipt_phase}"
            )
        seen_identity.add(identity)
        case = case_by_id.get(case_id)
        if case is None:
            raise ContractError(f"receipt case_id not in manifest: {case_id}")
        validate_receipt(receipt, case, phase, receipt_path)
        receipts[case_id] = receipt
    if set(receipts) != set(case_by_id):
        raise ContractError("receipt set mismatch")
    return receipts


def validate_phase(
    phase: str, cases: list[JsonObject], receipts: dict[str, JsonObject]
) -> None:
    if phase == "green":
        for case in cases:
            case_id = required_string(case, "case_id", "manifest case")
            rubric = cast(JsonObject, receipts[case_id]["rubric"])
            for criterion, passed in rubric.items():
                if passed is False:
                    raise ContractError(
                        f"GREEN receipt failed blocking criterion {criterion}: {case_id}"
                    )
        return
    for group in POSITIVE_GROUPS:
        group_cases = [
            case
            for case in cases
            if required_string(case, "branch_group", "manifest case") == group
        ]
        if not any(
            cast(
                JsonObject,
                receipts[required_string(case, "case_id", "manifest case")]["rubric"],
            ).get(criterion)
            is False
            for case in group_cases
            for criterion in ("FSE-02", "FSE-03", "FSE-04")
        ):
            raise ContractError(f"RED missing branch-level miss: {group}")
    negative_receipts = [
        receipts[required_string(case, "case_id", "manifest case")]
        for case in cases
        if required_string(case, "branch_group", "manifest case") in NEGATIVE_GROUPS
    ]
    if not any(
        cast(JsonObject, receipt["rubric"]).get(criterion) is False
        for receipt in negative_receipts
        for criterion in ("FSE-01", "FSE-07")
    ):
        raise ContractError("RED missing branch-level miss: negative-routes")


def results_text(
    manifest_path: Path,
    phase: str,
    cases: list[JsonObject],
    receipts: dict[str, JsonObject],
) -> str:
    lines = [
        "# Financial Systems Testing Evaluation Results",
        "",
        "## Frozen Inputs",
        "",
        "| Input | SHA-256 |",
        "|---|---|",
        f"| `cases.json` | `{sha256_file(manifest_path)}` |",
        f"| `tests/financial-systems-testing-eval/rubric.md` | `{sha256_file(manifest_path.parent / 'rubric.md')}` |",
    ]
    for case in cases:
        case_id = required_string(case, "case_id", "manifest case")
        lines.append(
            f"| `tests/financial-systems-testing-eval/{case['prompt_path']}` | `{case['prompt_sha256']}` |"
        )
    lines.extend(["", "## RED Baseline", ""])
    if phase == "red":
        lines.extend(
            [
                "| Case ID | Group | Missed criteria | Producer session | Grader session |",
                "|---|---|---|---|---|",
            ]
        )
        for case in cases:
            case_id = required_string(case, "case_id", "manifest case")
            receipt = receipts[case_id]
            rubric = cast(JsonObject, receipt["rubric"])
            missed = ", ".join(
                criterion for criterion, passed in rubric.items() if passed is False
            )
            row = f"| `{case_id}` | `{case['branch_group']}` | {missed or 'None'} | `{receipt['producer_session_id']}` | `{receipt['grader_session_id']}` |"
            lines.append(row)
    else:
        lines.append("Pending until T1 RED validation is recorded.")
    lines.extend(["", "## GREEN Evaluation", "", "Pending until T6.", ""])
    return "\n".join(lines)


def parse_args(argv: list[str] | None) -> tuple[str, Path, Path, Path]:
    parser = argparse.ArgumentParser()
    _ = parser.add_argument("--phase", choices=("red", "green"), required=True)
    _ = parser.add_argument("--manifest", required=True)
    _ = parser.add_argument("--receipts", required=True)
    _ = parser.add_argument("--results", required=True)
    args = parser.parse_args(argv)
    return (
        cast(str, args.phase),
        Path(cast(str, args.manifest)),
        Path(cast(str, args.receipts)),
        Path(cast(str, args.results)),
    )


def fail(error: ContractError) -> NoReturn:
    _ = sys.stderr.write(f"{error}\n")
    raise SystemExit(2)


def main(argv: list[str] | None = None) -> int:
    phase, manifest_path, receipts_path, results_path = parse_args(argv)
    try:
        cases = validate_manifest(manifest_path)
        receipts = load_receipts(receipts_path, cases, phase)
        validate_phase(phase, cases, receipts)
        content = results_text(manifest_path, phase, cases, receipts)
        _ = results_path.write_text(content, encoding="utf-8")
    except ContractError as error:
        fail(error)
    output = {
        "cases": len(cases),
        "manifest_sha256": sha256_file(manifest_path),
        "phase": phase,
        "results_sha256": sha256_bytes(content.encode("utf-8")),
    }
    print(canonical_json(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
