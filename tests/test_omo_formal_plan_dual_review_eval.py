from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import tempfile
import unittest
from typing import cast, override


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "validate-omo-formal-plan-dual-review-eval.py"
FIXTURE_DIR = REPO_ROOT / "tests" / "omo-formal-plan-dual-review-eval"
SOURCE = REPO_ROOT / "skills" / "omo-formal-plan-dual-review" / "SKILL.md"
MATRIX = REPO_ROOT / "docs" / "omo-formal-plan-dual-review" / "eval-matrix.md"

CASE_CONTRACT = (
    (
        "a-valid-blocked-receipt",
        ("OMO-01",),
        "receipt",
        "blocked-receipt-complete",
        "blocked-receipt-complete",
        ("eligible-blocker-reconciled",),
        (),
        (),
    ),
    (
        "b-zero-blocker-completion",
        ("OMO-02",),
        "receipt",
        "receipt-completion-request",
        "receipt-completion-under-specified",
        ("single-same-identity-completion",),
        ("OMO-02",),
        ("single-same-identity-completion",),
    ),
    (
        "c-unresolved-completion",
        ("OMO-03",),
        "receipt",
        "recovery-after-unresolved-completion",
        "recovery-after-unresolved-completion",
        ("invalid-pair-bounded-recovery",),
        (),
        (),
    ),
    (
        "d-approved-benign-notes",
        ("OMO-04",),
        "receipt",
        "approved-with-benign-notes",
        "approved-with-benign-notes",
        ("benign-notes-approval-readback",),
        (),
        (),
    ),
    (
        "e-approved-conditional-notes",
        ("OMO-04",),
        "receipt",
        "approval-note-inconsistent",
        "approval-note-unclassified",
        ("conditional-note-invalidates-pair",),
        ("OMO-04",),
        ("conditional-note-invalidates-pair",),
    ),
    (
        "f-completion-to-blocked",
        ("OMO-02", "OMO-03"),
        "receipt",
        "completion-to-blocked",
        "completion-blocker-rejected",
        ("single-same-identity-completion", "completion-blocker-admitted"),
        ("OMO-02", "OMO-03"),
        ("single-same-identity-completion", "completion-blocker-admitted"),
    ),
    (
        "g-completion-to-approved",
        ("OMO-02", "OMO-04"),
        "receipt",
        "completion-to-approved",
        "completion-approval-under-specified",
        ("single-same-identity-completion", "completion-approval-admitted"),
        ("OMO-02", "OMO-04"),
        ("single-same-identity-completion", "completion-approval-admitted"),
    ),
    (
        "h-approved-blocker-substantive-notes",
        ("OMO-04",),
        "receipt",
        "approval-note-inconsistent",
        "approval-note-unclassified",
        ("substantive-note-invalidates-pair",),
        ("OMO-04",),
        ("substantive-note-invalidates-pair",),
    ),
    (
        "i-material-d10-external-contract",
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
    (
        "j-recipe-wording-demotion",
        ("OMO-07",),
        "demotion",
        "non-blocking-note",
        "non-blocking-note",
        ("recipes-demoted",),
        (),
        (),
    ),
    (
        "k-closure-unchanged-root-rediscovery",
        ("OMO-08",),
        "novelty",
        "non-blocking-note",
        "non-blocking-note",
        ("unchanged-root-rejected",),
        (),
        (),
    ),
    (
        "l-repair-caused-d10-compact-repair",
        ("OMO-05", "OMO-09"),
        "compact-repair",
        "compact-d10-repair",
        "compact-repair-under-specified",
        ("repair-caused-d10-preserved", "compact-repair-only"),
        ("OMO-09",),
        ("compact-repair-only",),
    ),
    (
        "m-budget-inflation-escalation",
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
)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class FormalPlanDualReviewEvalTests(unittest.TestCase):
    temp_dir: tempfile.TemporaryDirectory[str] = cast(
        tempfile.TemporaryDirectory[str], cast(object, None)
    )
    temp: pathlib.Path = pathlib.Path()
    source: pathlib.Path = pathlib.Path()
    manifest: pathlib.Path = pathlib.Path()
    prompts: pathlib.Path = pathlib.Path()

    @override
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp = pathlib.Path(self.temp_dir.name)
        self.source = self.temp / "SKILL.md"
        _ = self.source.write_text("unchanged source\n", encoding="utf-8")
        self.manifest = self.temp / "cases.json"
        self.prompts = self.temp / "prompts"
        self.prompts.mkdir()
        self.write_manifest()

    @override
    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_manifest(self) -> None:
        cases: list[dict[str, object]] = []
        for (
            case_id,
            criteria,
            behavior_class,
            outcome,
            red_outcome,
            observations,
            red_false,
            red_false_observations,
        ) in CASE_CONTRACT:
            prompt_path = self.prompts / f"{case_id}.md"
            _ = prompt_path.write_text(f"# {case_id}\n", encoding="utf-8")
            cases.append(
                {
                    "case_id": case_id,
                    "prompt_path": f"prompts/{case_id}.md",
                    "prompt_sha256": sha256_bytes(prompt_path.read_bytes()),
                    "blocking_criteria": list(criteria),
                    "behavior_class": behavior_class,
                    "expected_outcome": outcome,
                    "red_observed_outcome": red_outcome,
                    "required_observations": list(observations),
                    "red_false_criteria": list(red_false),
                    "red_false_observations": list(red_false_observations),
                }
            )
        _ = self.manifest.write_text(
            json.dumps({"schema_version": 2, "cases": cases}, indent=2) + "\n",
            encoding="utf-8",
        )
        _ = (self.temp / "rubric.md").write_text(
            "\n".join(f"| `{criterion}` | rule |" for criterion in self.criteria())
            + "\n",
            encoding="utf-8",
        )

    def criteria(self) -> list[str]:
        return [f"OMO-{number:02d}" for number in range(1, 11)]

    def cases(self) -> list[dict[str, object]]:
        manifest = cast(dict[str, object], json.loads(self.manifest.read_text()))
        return cast(list[dict[str, object]], manifest["cases"])

    def write_receipts(self, phase: str) -> pathlib.Path:
        receipts = self.temp / f"{phase}-receipts"
        receipts.mkdir()
        source_bytes = self.source.read_bytes()
        source_sha256 = sha256_bytes(source_bytes)
        for case in self.cases():
            case_id = cast(str, case["case_id"])
            outcome_key = (
                "red_observed_outcome" if phase == "red" else "expected_outcome"
            )
            observed_outcome = cast(str, case[outcome_key])
            criteria = cast(list[str], case["blocking_criteria"])
            failed: set[str] = (
                set(cast(list[str], case["red_false_criteria"]))
                if phase == "red"
                else set()
            )
            false_observations: set[str] = (
                set(cast(list[str], case["red_false_observations"]))
                if phase == "red"
                else set()
            )
            required_observations = cast(list[str], case["required_observations"])
            observations = {
                observation: observation not in false_observations
                for observation in required_observations
            }
            response_object: dict[str, object] = {
                "schema_version": 2,
                "case_id": case_id,
                "observed_outcome": observed_outcome,
                "observations": observations,
                "narrative": (
                    f"Producer described the {case_id} outcome for independent grading."
                ),
            }
            response = (json.dumps(response_object, sort_keys=True) + "\n").encode()
            response_path = receipts / f"{case_id}.response.md"
            _ = response_path.write_bytes(response)
            rubric = {criterion: criterion not in failed for criterion in criteria}
            grader_output: dict[str, object] = {
                "schema_version": 2,
                "phase": phase,
                "case_id": case_id,
                "grader_context_id": f"grader-{phase}-{case_id}",
                "prompt_sha256": case["prompt_sha256"],
                "response_sha256": sha256_bytes(response),
                "observed_outcome": observed_outcome,
                "observations": observations,
                "rubric": rubric,
                "evidence": {
                    criterion: {
                        "summary": (
                            f"Independent grader assessed {criterion} against "
                            + f"the {case_id} response."
                        ),
                        "observation_ids": required_observations,
                    }
                    for criterion in criteria
                },
            }
            grader_bytes = (json.dumps(grader_output, sort_keys=True) + "\n").encode()
            _ = (receipts / f"{case_id}.grader.json").write_bytes(grader_bytes)
            receipt: dict[str, object] = {
                "schema_version": 2,
                "phase": phase,
                "case_id": case_id,
                "source_sha256": source_sha256,
                "source_bytes": len(source_bytes),
                "producer_context_id": f"producer-{phase}-{case_id}",
                "grader_context_id": f"grader-{phase}-{case_id}",
                "prompt_sha256": case["prompt_sha256"],
                "response_sha256": sha256_bytes(response),
                "grader_output_sha256": sha256_bytes(grader_bytes),
                "observed_outcome": observed_outcome,
                "observations": observations,
                "rubric": rubric,
                "evidence": {
                    criterion: "Observed missing behavior in source response."
                    for criterion in failed
                },
            }
            _ = (receipts / f"{case_id}.receipt.json").write_text(
                json.dumps(receipt, sort_keys=True) + "\n", encoding="utf-8"
            )
        return receipts

    def run_validator(
        self,
        manifest: pathlib.Path,
        phase: str | None = None,
        receipts: pathlib.Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        arguments = [
            "python3",
            str(SCRIPT),
            "--manifest",
            str(manifest),
            "--source",
            str(self.source),
            "--results",
            str(self.temp / "results.md"),
        ]
        if phase is not None and receipts is not None:
            arguments.extend(["--phase", phase, "--receipts", str(receipts)])
        return subprocess.run(arguments, capture_output=True, text=True, check=False)

    def test_accepts_valid_red_and_green_receipts(self) -> None:
        red = self.run_validator(self.manifest, "red", self.write_receipts("red"))
        self.assertEqual(red.returncode, 0, red.stderr)
        self.assertIn('"phase":"red"', red.stdout)
        results = (self.temp / "results.md").read_text()
        self.assertIn("OMO-02=false", results)
        self.assertIn("Observed missing behavior in source response.", results)
        green = self.run_validator(self.manifest, "green", self.write_receipts("green"))
        self.assertEqual(green.returncode, 0, green.stderr)
        self.assertIn("## GREEN Evaluation", (self.temp / "results.md").read_text())

    def test_rejects_reused_producer_context(self) -> None:
        receipts = self.write_receipts("red")
        first_path = receipts / "a-valid-blocked-receipt.receipt.json"
        second_path = receipts / "b-zero-blocker-completion.receipt.json"
        first = cast(dict[str, object], json.loads(first_path.read_text()))
        second = cast(dict[str, object], json.loads(second_path.read_text()))
        second["producer_context_id"] = first["producer_context_id"]
        _ = second_path.write_text(json.dumps(second), encoding="utf-8")
        result = self.run_validator(self.manifest, "red", receipts)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("producer_context_id reused", result.stderr)

    def test_rejects_reused_grader_context(self) -> None:
        receipts = self.write_receipts("red")
        first_path = receipts / "a-valid-blocked-receipt.receipt.json"
        second_path = receipts / "b-zero-blocker-completion.receipt.json"
        first = cast(dict[str, object], json.loads(first_path.read_text()))
        second = cast(dict[str, object], json.loads(second_path.read_text()))
        second["grader_context_id"] = first["grader_context_id"]
        grader_path = receipts / "b-zero-blocker-completion.grader.json"
        grader = cast(dict[str, object], json.loads(grader_path.read_text()))
        grader["grader_context_id"] = first["grader_context_id"]
        grader_bytes = (json.dumps(grader, sort_keys=True) + "\n").encode()
        _ = grader_path.write_bytes(grader_bytes)
        second["grader_output_sha256"] = sha256_bytes(grader_bytes)
        _ = second_path.write_text(json.dumps(second), encoding="utf-8")
        result = self.run_validator(self.manifest, "red", receipts)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("grader_context_id reused", result.stderr)

    def test_rejects_tampered_prompt_hash(self) -> None:
        manifest = cast(dict[str, object], json.loads(self.manifest.read_text()))
        cases = cast(list[dict[str, object]], manifest["cases"])
        cases[0]["prompt_sha256"] = "0" * 64
        _ = self.manifest.write_text(json.dumps(manifest), encoding="utf-8")
        result = self.run_validator(self.manifest)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("prompt_sha256 mismatch", result.stderr)

    def test_rejects_manifest_schema_mismatch(self) -> None:
        manifest = cast(dict[str, object], json.loads(self.manifest.read_text()))
        manifest["schema_version"] = 1
        _ = self.manifest.write_text(json.dumps(manifest), encoding="utf-8")
        result = self.run_validator(self.manifest)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("manifest schema_version must be 2", result.stderr)

    def test_rejects_missing_case(self) -> None:
        manifest = cast(dict[str, object], json.loads(self.manifest.read_text()))
        cases = cast(list[dict[str, object]], manifest["cases"])
        _ = cases.pop()
        _ = self.manifest.write_text(json.dumps(manifest), encoding="utf-8")
        result = self.run_validator(self.manifest)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("case inventory mismatch", result.stderr)

    def test_rejects_extra_rubric_key(self) -> None:
        receipts = self.write_receipts("red")
        receipt_path = receipts / "a-valid-blocked-receipt.receipt.json"
        receipt = cast(dict[str, object], json.loads(receipt_path.read_text()))
        rubric = cast(dict[str, bool], receipt["rubric"])
        rubric["OMO-10"] = True
        _ = receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        result = self.run_validator(self.manifest, "red", receipts)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("rubric keys mismatch", result.stderr)

    def test_rejects_non_boolean_rubric_value(self) -> None:
        receipts = self.write_receipts("red")
        receipt_path = receipts / "a-valid-blocked-receipt.receipt.json"
        receipt = cast(dict[str, object], json.loads(receipt_path.read_text()))
        receipt["rubric"] = {"OMO-01": "true"}
        _ = receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        result = self.run_validator(self.manifest, "red", receipts)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("rubric values must be boolean", result.stderr)

    def test_rejects_source_hash_mismatch(self) -> None:
        receipts = self.write_receipts("red")
        receipt_path = receipts / "a-valid-blocked-receipt.receipt.json"
        receipt = cast(dict[str, object], json.loads(receipt_path.read_text()))
        receipt["source_sha256"] = "0" * 64
        _ = receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        result = self.run_validator(self.manifest, "red", receipts)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("source binding mismatch", result.stderr)

    def test_rejects_observed_outcome_mismatch(self) -> None:
        receipts = self.write_receipts("green")
        receipt_path = receipts / "a-valid-blocked-receipt.receipt.json"
        receipt = cast(dict[str, object], json.loads(receipt_path.read_text()))
        receipt["observed_outcome"] = "generic-success"
        _ = receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        result = self.run_validator(self.manifest, "green", receipts)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("observed_outcome mismatch", result.stderr)

    def test_rejects_missing_required_observation(self) -> None:
        receipts = self.write_receipts("green")
        receipt_path = receipts / "a-valid-blocked-receipt.receipt.json"
        receipt = cast(dict[str, object], json.loads(receipt_path.read_text()))
        receipt["observations"] = {}
        _ = receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        result = self.run_validator(self.manifest, "green", receipts)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("observation keys mismatch", result.stderr)

    def test_rejects_missing_grader_evidence(self) -> None:
        receipts = self.write_receipts("green")
        case_id = "a-valid-blocked-receipt"
        grader_path = receipts / f"{case_id}.grader.json"
        grader = cast(dict[str, object], json.loads(grader_path.read_text()))
        grader["evidence"] = {}
        grader_bytes = (json.dumps(grader, sort_keys=True) + "\n").encode()
        _ = grader_path.write_bytes(grader_bytes)
        receipt_path = receipts / f"{case_id}.receipt.json"
        receipt = cast(dict[str, object], json.loads(receipt_path.read_text()))
        receipt["grader_output_sha256"] = sha256_bytes(grader_bytes)
        _ = receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        result = self.run_validator(self.manifest, "green", receipts)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("grader evidence keys mismatch", result.stderr)

    def test_rejects_grader_evidence_unlinked_from_case_observations(self) -> None:
        receipts = self.write_receipts("green")
        case_id = "a-valid-blocked-receipt"
        grader_path = receipts / f"{case_id}.grader.json"
        grader = cast(dict[str, object], json.loads(grader_path.read_text()))
        evidence = cast(dict[str, dict[str, object]], grader["evidence"])
        evidence["OMO-01"]["observation_ids"] = ["generic-success"]
        grader_bytes = (json.dumps(grader, sort_keys=True) + "\n").encode()
        _ = grader_path.write_bytes(grader_bytes)
        receipt_path = receipts / f"{case_id}.receipt.json"
        receipt = cast(dict[str, object], json.loads(receipt_path.read_text()))
        receipt["grader_output_sha256"] = sha256_bytes(grader_bytes)
        _ = receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        result = self.run_validator(self.manifest, "green", receipts)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("grader evidence observations mismatch", result.stderr)

    def test_rejects_missing_false_evidence(self) -> None:
        receipts = self.write_receipts("red")
        receipt_path = receipts / "b-zero-blocker-completion.receipt.json"
        receipt = cast(dict[str, object], json.loads(receipt_path.read_text()))
        receipt["evidence"] = {}
        _ = receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        result = self.run_validator(self.manifest, "red", receipts)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("evidence keys mismatch", result.stderr)

    def test_rejects_green_receipt_with_failed_criterion(self) -> None:
        receipts = self.write_receipts("green")
        receipt_path = receipts / "a-valid-blocked-receipt.receipt.json"
        receipt = cast(dict[str, object], json.loads(receipt_path.read_text()))
        receipt["rubric"] = {"OMO-01": False}
        receipt["evidence"] = {"OMO-01": "Green cannot retain a failed criterion."}
        _ = receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        result = self.run_validator(self.manifest, "green", receipts)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("GREEN receipt failed criterion", result.stderr)

    def test_rejects_rehashed_generic_green_responses(self) -> None:
        receipts = self.write_receipts("green")
        generic_response = b"Generic response with no case-specific outcome.\n"
        for case in self.cases():
            case_id = cast(str, case["case_id"])
            response_path = receipts / f"{case_id}.response.md"
            _ = response_path.write_bytes(generic_response)
            receipt_path = receipts / f"{case_id}.receipt.json"
            receipt = cast(dict[str, object], json.loads(receipt_path.read_text()))
            receipt["response_sha256"] = sha256_bytes(generic_response)
            grader_path = receipts / f"{case_id}.grader.json"
            grader = cast(dict[str, object], json.loads(grader_path.read_text()))
            grader["response_sha256"] = sha256_bytes(generic_response)
            grader_bytes = (json.dumps(grader, sort_keys=True) + "\n").encode()
            _ = grader_path.write_bytes(grader_bytes)
            receipt["grader_output_sha256"] = sha256_bytes(grader_bytes)
            _ = receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        result = self.run_validator(self.manifest, "green", receipts)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid JSON raw response", result.stderr)

    def test_committed_contract_and_matrix_are_valid(self) -> None:
        result = self.run_validator(FIXTURE_DIR / "cases.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        matrix = MATRIX.read_text(encoding="utf-8")
        rubric = (FIXTURE_DIR / "rubric.md").read_text(encoding="utf-8")
        for case_id, criteria, _, _, _, observations, _, _ in CASE_CONTRACT:
            self.assertIn(case_id, matrix)
            for criterion in criteria:
                self.assertIn(criterion, rubric)
            for observation in observations:
                self.assertIn(observation, matrix)


if __name__ == "__main__":
    _ = unittest.main()
