#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import NoReturn, cast


SCHEMA_VERSION = 2
RUBRIC_IDS = frozenset(f"OMO-{number:02d}" for number in range(1, 11))
MANIFEST_FIELDS = frozenset(
    {
        "case_id",
        "prompt_path",
        "prompt_sha256",
        "blocking_criteria",
        "behavior_class",
        "expected_outcome",
        "red_observed_outcome",
        "required_observations",
        "red_false_criteria",
        "red_false_observations",
    }
)
RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "phase",
        "case_id",
        "source_sha256",
        "source_bytes",
        "producer_context_id",
        "grader_context_id",
        "prompt_sha256",
        "response_sha256",
        "grader_output_sha256",
        "observed_outcome",
        "observations",
        "rubric",
        "evidence",
    }
)
GRADER_OUTPUT_FIELDS = frozenset(
    {
        "schema_version",
        "phase",
        "case_id",
        "grader_context_id",
        "prompt_sha256",
        "response_sha256",
        "observed_outcome",
        "observations",
        "rubric",
        "evidence",
    }
)
RESPONSE_FIELDS = frozenset(
    {
        "schema_version",
        "case_id",
        "observed_outcome",
        "observations",
        "narrative",
    }
)
CASE_CONTRACT = {
    "a-valid-blocked-receipt": (
        ("OMO-01",),
        "receipt",
        "blocked-receipt-complete",
        "blocked-receipt-complete",
        ("eligible-blocker-reconciled",),
        (),
        (),
    ),
    "b-zero-blocker-completion": (
        ("OMO-02",),
        "receipt",
        "receipt-completion-request",
        "receipt-completion-under-specified",
        ("single-same-identity-completion",),
        ("OMO-02",),
        ("single-same-identity-completion",),
    ),
    "c-unresolved-completion": (
        ("OMO-03",),
        "receipt",
        "recovery-after-unresolved-completion",
        "recovery-after-unresolved-completion",
        ("invalid-pair-bounded-recovery",),
        (),
        (),
    ),
    "d-approved-benign-notes": (
        ("OMO-04",),
        "receipt",
        "approved-with-benign-notes",
        "approved-with-benign-notes",
        ("benign-notes-approval-readback",),
        (),
        (),
    ),
    "e-approved-conditional-notes": (
        ("OMO-04",),
        "receipt",
        "approval-note-inconsistent",
        "approval-note-unclassified",
        ("conditional-note-invalidates-pair",),
        ("OMO-04",),
        ("conditional-note-invalidates-pair",),
    ),
    "f-completion-to-blocked": (
        ("OMO-02", "OMO-03"),
        "receipt",
        "completion-to-blocked",
        "completion-blocker-rejected",
        ("single-same-identity-completion", "completion-blocker-admitted"),
        ("OMO-02", "OMO-03"),
        ("single-same-identity-completion", "completion-blocker-admitted"),
    ),
    "g-completion-to-approved": (
        ("OMO-02", "OMO-04"),
        "receipt",
        "completion-to-approved",
        "completion-approval-under-specified",
        ("single-same-identity-completion", "completion-approval-admitted"),
        ("OMO-02", "OMO-04"),
        ("single-same-identity-completion", "completion-approval-admitted"),
    ),
    "h-approved-blocker-substantive-notes": (
        ("OMO-04",),
        "receipt",
        "approval-note-inconsistent",
        "approval-note-unclassified",
        ("substantive-note-invalidates-pair",),
        ("OMO-04",),
        ("substantive-note-invalidates-pair",),
    ),
    "i-material-d10-external-contract": (
        ("OMO-05", "OMO-06"),
        "materiality",
        "material-d10-blocker",
        "materiality-gate-under-specified",
        (
            "material-d10-preserved",
            "material-plan-necessity-proved",
            "review-mechanism-stripped",
        ),
        ("OMO-06",),
        ("material-plan-necessity-proved", "review-mechanism-stripped"),
    ),
    "j-recipe-wording-demotion": (
        ("OMO-07",),
        "demotion",
        "non-blocking-note",
        "non-blocking-note",
        ("recipes-demoted",),
        (),
        (),
    ),
    "k-closure-unchanged-root-rediscovery": (
        ("OMO-08",),
        "novelty",
        "non-blocking-note",
        "non-blocking-note",
        ("unchanged-root-rejected",),
        (),
        (),
    ),
    "l-repair-caused-d10-compact-repair": (
        ("OMO-05", "OMO-09"),
        "compact-repair",
        "compact-d10-repair",
        "compact-repair-under-specified",
        ("repair-caused-d10-preserved", "compact-repair-only"),
        ("OMO-09",),
        ("compact-repair-only",),
    ),
    "m-budget-inflation-escalation": (
        ("OMO-10",),
        "escalation",
        "inconclusive-user-routes",
        "inflation-escalation-absent",
        (
            "eligible-blocker-preserved",
            "automatic-edits-paused",
            "three-user-routes-offered",
        ),
        ("OMO-10",),
        ("automatic-edits-paused", "three-user-routes-offered"),
    ),
}
JsonObject = dict[str, object]


class ContractError(Exception):
    pass


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_object(path: Path, label: str) -> JsonObject:
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


def required_strings(value: JsonObject, key: str, label: str) -> tuple[str, ...]:
    result = value.get(key)
    if not isinstance(result, list):
        raise ContractError(f"{label} field {key} must be a non-empty string list")
    items = cast(list[object], result)
    if not all(isinstance(item, str) and item for item in items):
        raise ContractError(f"{label} field {key} must be a non-empty string list")
    return tuple(cast(str, item) for item in items)


def require_sha256(value: str, label: str) -> None:
    if len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise ContractError(f"{label} must be 64 lowercase hex characters")


def validate_rubric(path: Path) -> None:
    try:
        ids = {
            line.split("`")[1]
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.startswith("| `OMO-") and "`" in line
        }
    except OSError as error:
        raise ContractError(f"cannot read rubric: {error}") from error
    if ids != set(RUBRIC_IDS):
        raise ContractError("rubric key inventory mismatch")


def validate_manifest(path: Path) -> dict[str, JsonObject]:
    manifest = load_object(path, "manifest")
    if set(manifest) != {"schema_version", "cases"}:
        raise ContractError("manifest fields mismatch")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ContractError("manifest schema_version must be 2")
    raw_cases = manifest.get("cases")
    if not isinstance(raw_cases, list):
        raise ContractError("manifest cases must be an array")
    cases: dict[str, JsonObject] = {}
    for raw_case in cast(list[object], raw_cases):
        if not isinstance(raw_case, dict):
            raise ContractError("manifest case must be an object")
        case = cast(JsonObject, raw_case)
        if set(case) != set(MANIFEST_FIELDS):
            raise ContractError("manifest case fields mismatch")
        case_id = required_string(case, "case_id", "manifest case")
        if case_id in cases:
            raise ContractError(f"duplicate case_id: {case_id}")
        expected = CASE_CONTRACT.get(case_id)
        if expected is None:
            raise ContractError(f"unexpected case_id: {case_id}")
        (
            criteria,
            behavior_class,
            outcome,
            red_outcome,
            observations,
            red_false,
            red_false_observations,
        ) = expected
        if required_strings(case, "blocking_criteria", case_id) != criteria:
            raise ContractError(f"blocking_criteria mismatch: {case_id}")
        if required_strings(case, "red_false_criteria", case_id) != red_false:
            raise ContractError(f"red_false_criteria mismatch: {case_id}")
        if required_strings(case, "required_observations", case_id) != observations:
            raise ContractError(f"required_observations mismatch: {case_id}")
        if (
            required_strings(case, "red_false_observations", case_id)
            != red_false_observations
        ):
            raise ContractError(f"red_false_observations mismatch: {case_id}")
        if case.get("behavior_class") != behavior_class:
            raise ContractError(f"behavior_class mismatch: {case_id}")
        if case.get("expected_outcome") != outcome:
            raise ContractError(f"expected_outcome mismatch: {case_id}")
        if case.get("red_observed_outcome") != red_outcome:
            raise ContractError(f"red_observed_outcome mismatch: {case_id}")
        prompt_path = Path(required_string(case, "prompt_path", case_id))
        if prompt_path.is_absolute() or ".." in prompt_path.parts:
            raise ContractError(f"invalid prompt_path: {case_id}")
        prompt_sha256 = required_string(case, "prompt_sha256", case_id)
        require_sha256(prompt_sha256, f"prompt_sha256 for {case_id}")
        prompt_file = path.parent / prompt_path
        if not prompt_file.is_file():
            raise ContractError(f"prompt missing: {case_id}")
        if sha256_file(prompt_file) != prompt_sha256:
            raise ContractError(f"prompt_sha256 mismatch: {case_id}")
        cases[case_id] = case
    if set(cases) != set(CASE_CONTRACT):
        raise ContractError("case inventory mismatch")
    validate_rubric(path.parent / "rubric.md")
    return cases


def validate_receipt(
    path: Path, case: JsonObject, phase: str, source: bytes
) -> JsonObject:
    receipt = load_object(path, f"receipt {path.name}")
    label = path.name
    if set(receipt) != set(RECEIPT_FIELDS):
        raise ContractError(f"receipt fields mismatch: {label}")
    if receipt.get("schema_version") != SCHEMA_VERSION:
        raise ContractError(f"receipt schema_version mismatch: {label}")
    case_id = required_string(receipt, "case_id", label)
    if case_id != case["case_id"] or receipt.get("phase") != phase:
        raise ContractError(f"receipt identity mismatch: {label}")
    source_sha256 = required_string(receipt, "source_sha256", label)
    response_sha256 = required_string(receipt, "response_sha256", label)
    grader_output_sha256 = required_string(receipt, "grader_output_sha256", label)
    prompt_sha256 = required_string(receipt, "prompt_sha256", label)
    require_sha256(source_sha256, f"source_sha256: {label}")
    require_sha256(response_sha256, f"response_sha256: {label}")
    require_sha256(grader_output_sha256, f"grader_output_sha256: {label}")
    if source_sha256 != sha256_bytes(source) or receipt.get("source_bytes") != len(
        source
    ):
        raise ContractError(f"source binding mismatch: {label}")
    if prompt_sha256 != case["prompt_sha256"]:
        raise ContractError(f"receipt prompt_sha256 mismatch: {label}")
    producer = required_string(receipt, "producer_context_id", label)
    grader = required_string(receipt, "grader_context_id", label)
    if producer == grader:
        raise ContractError(f"producer and grader contexts must differ: {label}")
    response_path = path.parent / f"{case_id}.response.md"
    if not response_path.is_file() or sha256_file(response_path) != response_sha256:
        raise ContractError(f"response_sha256 mismatch: {label}")
    expected_outcome_key = (
        "red_observed_outcome" if phase == "red" else "expected_outcome"
    )
    observed_outcome = required_string(receipt, "observed_outcome", label)
    if observed_outcome != case[expected_outcome_key]:
        raise ContractError(f"observed_outcome mismatch: {label}")
    observations = receipt.get("observations")
    if not isinstance(observations, dict):
        raise ContractError(f"receipt observations must be an object: {label}")
    observation_values = cast(JsonObject, observations)
    required_observations = set(required_strings(case, "required_observations", label))
    if set(observation_values) != required_observations:
        raise ContractError(f"observation keys mismatch: {label}")
    if not all(isinstance(value, bool) for value in observation_values.values()):
        raise ContractError(f"observation values must be boolean: {label}")
    false_observations = {
        key for key, value in observation_values.items() if value is False
    }
    expected_false_observations: set[str] = (
        set(required_strings(case, "red_false_observations", label))
        if phase == "red"
        else set()
    )
    if false_observations != expected_false_observations:
        raise ContractError(f"observation verdict mismatch: {label}")
    response = load_object(response_path, f"raw response {response_path.name}")
    if set(response) != set(RESPONSE_FIELDS):
        raise ContractError(f"raw response fields mismatch: {label}")
    if response.get("schema_version") != SCHEMA_VERSION:
        raise ContractError(f"raw response schema_version mismatch: {label}")
    for field, expected_value in (
        ("case_id", case_id),
        ("observed_outcome", observed_outcome),
        ("observations", observation_values),
    ):
        if response.get(field) != expected_value:
            raise ContractError(f"raw response {field} mismatch: {label}")
    _ = required_string(response, "narrative", f"raw response {label}")
    rubric = receipt.get("rubric")
    evidence = receipt.get("evidence")
    if not isinstance(rubric, dict) or not isinstance(evidence, dict):
        raise ContractError(f"receipt rubric and evidence must be objects: {label}")
    rubric_values = cast(JsonObject, rubric)
    evidence_values = cast(JsonObject, evidence)
    criteria = set(required_strings(case, "blocking_criteria", label))
    if set(rubric_values) != criteria:
        raise ContractError(f"rubric keys mismatch: {label}")
    if not all(isinstance(value, bool) for value in rubric_values.values()):
        raise ContractError(f"rubric values must be boolean: {label}")
    false_keys = {key for key, value in rubric_values.items() if value is False}
    if set(evidence_values) != false_keys or not all(
        isinstance(value, str) and value for value in evidence_values.values()
    ):
        raise ContractError(f"evidence keys mismatch: {label}")
    if phase == "red" and false_keys != set(
        required_strings(case, "red_false_criteria", label)
    ):
        raise ContractError(f"RED criteria mismatch: {label}")
    if phase == "green" and false_keys:
        raise ContractError(f"GREEN receipt failed criterion: {label}")
    grader_path = path.parent / f"{case_id}.grader.json"
    if not grader_path.is_file():
        raise ContractError(f"grader output missing: {label}")
    if sha256_file(grader_path) != grader_output_sha256:
        raise ContractError(f"grader_output_sha256 mismatch: {label}")
    grader_output = load_object(grader_path, f"grader output {grader_path.name}")
    if set(grader_output) != set(GRADER_OUTPUT_FIELDS):
        raise ContractError(f"grader output fields mismatch: {label}")
    if grader_output.get("schema_version") != SCHEMA_VERSION:
        raise ContractError(f"grader output schema_version mismatch: {label}")
    for field, expected_value in (
        ("phase", phase),
        ("case_id", case_id),
        ("grader_context_id", grader),
        ("prompt_sha256", prompt_sha256),
        ("response_sha256", response_sha256),
        ("observed_outcome", observed_outcome),
        ("observations", observation_values),
        ("rubric", rubric_values),
    ):
        if grader_output.get(field) != expected_value:
            raise ContractError(f"grader output {field} mismatch: {label}")
    grader_evidence = grader_output.get("evidence")
    if not isinstance(grader_evidence, dict):
        raise ContractError(f"grader evidence must be an object: {label}")
    grader_evidence_values = cast(JsonObject, grader_evidence)
    if set(grader_evidence_values) != criteria:
        raise ContractError(f"grader evidence keys mismatch: {label}")
    covered_observations: set[str] = set()
    for criterion, raw_evidence in grader_evidence_values.items():
        if not isinstance(raw_evidence, dict):
            raise ContractError(f"grader evidence fields mismatch: {label}")
        criterion_evidence = cast(JsonObject, raw_evidence)
        if set(criterion_evidence) != {
            "summary",
            "observation_ids",
        }:
            raise ContractError(f"grader evidence fields mismatch: {label}")
        _ = required_string(criterion_evidence, "summary", f"{label} {criterion}")
        observation_ids = set(
            required_strings(
                criterion_evidence, "observation_ids", f"{label} {criterion}"
            )
        )
        if not observation_ids or not observation_ids.issubset(required_observations):
            raise ContractError(f"grader evidence observations mismatch: {label}")
        covered_observations.update(observation_ids)
    if covered_observations != required_observations:
        raise ContractError(f"grader evidence coverage mismatch: {label}")
    return receipt


def validate_receipts(
    receipts_path: Path, cases: dict[str, JsonObject], phase: str, source: bytes
) -> dict[str, JsonObject]:
    if not receipts_path.is_dir():
        raise ContractError("receipts directory not found")
    receipts: dict[str, JsonObject] = {}
    producer_contexts: set[str] = set()
    grader_contexts: set[str] = set()
    for path in sorted(receipts_path.glob("*.receipt.json")):
        receipt = load_object(path, f"receipt {path.name}")
        case_id = required_string(receipt, "case_id", path.name)
        if case_id in receipts or case_id not in cases:
            raise ContractError("receipt set mismatch")
        validated = validate_receipt(path, cases[case_id], phase, source)
        producer = required_string(validated, "producer_context_id", path.name)
        grader = required_string(validated, "grader_context_id", path.name)
        if producer in producer_contexts:
            raise ContractError(f"producer_context_id reused: {path.name}")
        if grader in grader_contexts:
            raise ContractError(f"grader_context_id reused: {path.name}")
        producer_contexts.add(producer)
        grader_contexts.add(grader)
        receipts[case_id] = validated
    if set(receipts) != set(cases):
        raise ContractError("receipt set mismatch")
    return receipts


def results_text(
    manifest: Path,
    source: Path,
    phase: str | None,
    receipts: dict[str, JsonObject] | None = None,
) -> str:
    heading = "Contract" if phase is None else phase.upper() + " Evaluation"
    lines = [
        "# Formal Plan Dual Review Evaluation Results",
        "",
        f"## {heading}",
        "",
        f"- Manifest SHA-256: `{sha256_file(manifest)}`",
        f"- Source SHA-256: `{sha256_file(source)}`",
        f"- Cases: `{len(CASE_CONTRACT)}`",
    ]
    if receipts is not None:
        lines.extend(
            [
                "",
                "| Case ID | Observed outcome | Structured observations | Rubric verdicts | False evidence |",
                "|---|---|---|---|---|",
            ]
        )
        for case_id in CASE_CONTRACT:
            receipt = receipts[case_id]
            observations = cast(JsonObject, receipt["observations"])
            rubric = cast(JsonObject, receipt["rubric"])
            evidence = cast(JsonObject, receipt["evidence"])
            observation_verdicts = ", ".join(
                f"{observation}={str(passed).lower()}"
                for observation, passed in observations.items()
            )
            verdicts = ", ".join(
                f"{criterion}={str(passed).lower()}"
                for criterion, passed in rubric.items()
            )
            false_evidence = "; ".join(
                f"{criterion}: {observation}"
                for criterion, observation in evidence.items()
            )
            lines.append(
                f"| `{case_id}` | `{receipt['observed_outcome']}` | "
                + f"{observation_verdicts} | {verdicts} | "
                + f"{false_evidence or 'none'} |"
            )
    lines.append("")
    return "\n".join(lines)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    _ = parser.add_argument("--manifest", required=True)
    _ = parser.add_argument("--source", required=True)
    _ = parser.add_argument("--results", required=True)
    _ = parser.add_argument("--phase", choices=("red", "green"))
    _ = parser.add_argument("--receipts")
    args = parser.parse_args(argv)
    phase = cast(str | None, args.phase)
    receipts = cast(str | None, args.receipts)
    if (phase is None) != (receipts is None):
        parser.error("--phase and --receipts must be supplied together")
    return args


def fail(error: ContractError) -> NoReturn:
    _ = sys.stderr.write(f"{error}\n")
    raise SystemExit(2)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    manifest = Path(cast(str, args.manifest))
    source = Path(cast(str, args.source))
    phase = cast(str | None, args.phase)
    receipts_path = cast(str | None, args.receipts)
    results = Path(cast(str, args.results))
    try:
        cases = validate_manifest(manifest)
        source_bytes = source.read_bytes()
        receipts = None
        if phase is not None and receipts_path is not None:
            receipts = validate_receipts(
                Path(receipts_path), cases, phase, source_bytes
            )
        content = results_text(manifest, source, phase, receipts)
        _ = results.write_text(content, encoding="utf-8")
    except (ContractError, OSError) as error:
        fail(ContractError(str(error)))
    print(
        json.dumps(
            {"cases": len(cases), "phase": phase or "contract"},
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
