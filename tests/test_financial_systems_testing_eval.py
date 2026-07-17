from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import subprocess
import tempfile
import unittest
from typing import cast, override


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "validate-financial-systems-testing-eval.py"
FIXTURE_DIR = REPO_ROOT / "tests" / "financial-systems-testing-eval"
Case = dict[str, object]


def load_json_object(path: pathlib.Path) -> dict[str, object]:
    value = cast(object, json.loads(path.read_text()))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return cast(dict[str, object], value)


def required_str(value: dict[str, object], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str):
        raise ValueError(f"Expected string {key}")
    return result


def required_str_list(value: dict[str, object], key: str) -> list[str]:
    result = value.get(key)
    items = cast(list[object], result)
    if not isinstance(result, list) or not all(isinstance(item, str) for item in items):
        raise ValueError(f"Expected string list {key}")
    return [cast(str, item) for item in items]


class FinancialSystemsTestingEvalTests(unittest.TestCase):
    temp_dir: tempfile.TemporaryDirectory[str] = cast(
        tempfile.TemporaryDirectory[str], cast(object, None)
    )
    temp: pathlib.Path = pathlib.Path()
    manifest_path: pathlib.Path = pathlib.Path()
    prompts_dir: pathlib.Path = pathlib.Path()
    manifest: dict[str, object] = {}

    @override
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp = pathlib.Path(self.temp_dir.name)
        self.manifest_path = self.temp / "cases.json"
        self.prompts_dir = self.temp / "prompts"
        _ = shutil.copytree(FIXTURE_DIR / "prompts", self.prompts_dir)
        _ = shutil.copy2(FIXTURE_DIR / "rubric.md", self.temp / "rubric.md")
        self.manifest = load_json_object(FIXTURE_DIR / "cases.json")
        self.write_manifest()

    @override
    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_manifest(self) -> None:
        _ = self.manifest_path.write_text(json.dumps(self.manifest, indent=2) + "\n")

    def cases(self) -> list[Case]:
        cases = self.manifest.get("cases")
        if not isinstance(cases, list):
            raise ValueError("Expected cases list")
        return cast(list[Case], cases)

    def receipt(
        self, case: Case, phase: str, failed: set[str] | None = None
    ) -> dict[str, object]:
        failed = failed or set()
        case_id = required_str(case, "case_id")
        prompt_sha256 = required_str(case, "prompt_sha256")
        criteria = required_str_list(case, "blocking_criteria")
        rubric = {criterion: criterion not in failed for criterion in criteria}
        return {
            "schema_version": 1,
            "run_id": "20260717T162345Z",
            "phase": phase,
            "case_id": case_id,
            "producer_session_id": f"producer-{case_id}",
            "producer_task_id": f"producer-task-{case_id}",
            "prompt_sha256": prompt_sha256,
            "response_sha256": hashlib.sha256(case_id.encode()).hexdigest(),
            "rubric": rubric,
            "evidence": {
                criterion: "Observed evaluation miss." for criterion in failed
            },
        }

    def write_receipts(
        self, phase: str, misses: dict[str, set[str]] | None = None
    ) -> pathlib.Path:
        receipts_dir = self.temp / f"{phase}-receipts"
        receipts_dir.mkdir()
        misses = misses or {}
        bindings: list[dict[str, object]] = []
        for case in self.cases():
            case_id = required_str(case, "case_id")
            receipt = self.receipt(case, phase, misses.get(case_id, set()))
            _ = (receipts_dir / f"{case_id}.response.md").write_text(case_id)
            _ = (receipts_dir / f"{case_id}.receipt.json").write_text(
                json.dumps(receipt, sort_keys=True) + "\n"
            )
            bindings.append(self.add_grader_artifact(receipts_dir, case_id))
        self.write_provenance(receipts_dir, phase, bindings)
        return receipts_dir

    def add_grader_artifact(
        self, receipts_dir: pathlib.Path, case_id: str
    ) -> dict[str, object]:
        receipt_path = receipts_dir / f"{case_id}.receipt.json"
        receipt = load_json_object(receipt_path)
        grader_output = {
            "schema_version": 1,
            "run_id": receipt["run_id"],
            "phase": receipt["phase"],
            "case_id": case_id,
            "producer_session_id": receipt["producer_session_id"],
            "producer_task_id": receipt["producer_task_id"],
            "grader_session_id": f"self-reported-{case_id}",
            "grader_task_id": f"self-reported-task-{case_id}",
            "grader_output_sha256": "0" * 64,
            "prompt_sha256": receipt["prompt_sha256"],
            "response_sha256": receipt["response_sha256"],
            "rubric": receipt["rubric"],
            "evidence": receipt["evidence"],
        }
        grader_path = receipts_dir / f"{case_id}.grader.json"
        raw_output = (
            json.dumps(grader_output, sort_keys=True, separators=(",", ":")) + "\n"
        )
        _ = grader_path.write_text(raw_output)
        binding = {
            "case_id": case_id,
            "grader_session_id": f"grader-{case_id}",
            "grader_task_id": f"grader-task-{case_id}",
            "grader_output_sha256": hashlib.sha256(raw_output.encode()).hexdigest(),
            "response_sha256": receipt["response_sha256"],
        }
        receipt.update(binding)
        _ = receipt_path.write_text(json.dumps(receipt, sort_keys=True) + "\n")
        return binding

    def write_provenance(
        self,
        receipts_dir: pathlib.Path,
        phase: str,
        bindings: list[dict[str, object]],
    ) -> None:
        provenance = {
            "schema_version": 1,
            "run_id": "20260717T162345Z",
            "phase": phase,
            "bindings": sorted(bindings, key=lambda binding: str(binding["case_id"])),
        }
        _ = (receipts_dir / "grader-provenance.json").write_text(
            json.dumps(provenance, sort_keys=True) + "\n"
        )

    def refresh_grader_binding(
        self,
        receipts_dir: pathlib.Path,
        case_id: str,
        grader_output: dict[str, object],
    ) -> None:
        raw_output = (
            json.dumps(grader_output, sort_keys=True, separators=(",", ":")) + "\n"
        )
        _ = (receipts_dir / f"{case_id}.grader.json").write_text(raw_output)
        grader_output_sha256 = hashlib.sha256(raw_output.encode()).hexdigest()
        receipt_path = receipts_dir / f"{case_id}.receipt.json"
        receipt = load_json_object(receipt_path)
        receipt["grader_output_sha256"] = grader_output_sha256
        _ = receipt_path.write_text(json.dumps(receipt, sort_keys=True) + "\n")
        provenance_path = receipts_dir / "grader-provenance.json"
        provenance = load_json_object(provenance_path)
        bindings = provenance.get("bindings")
        if not isinstance(bindings, list):
            self.fail("Expected provenance bindings")
        for raw_binding in cast(list[object], bindings):
            if not isinstance(raw_binding, dict):
                self.fail("Expected provenance binding object")
            binding = cast(dict[str, object], raw_binding)
            if binding.get("case_id") == case_id:
                binding["grader_output_sha256"] = grader_output_sha256
                break
        _ = provenance_path.write_text(json.dumps(provenance, sort_keys=True) + "\n")

    def run_validator(
        self, phase: str, receipts_dir: pathlib.Path
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                "python3",
                str(SCRIPT),
                "--phase",
                phase,
                "--manifest",
                str(self.manifest_path),
                "--receipts",
                str(receipts_dir),
                "--results",
                str(self.temp / "eval-results.md"),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    def red_misses(self) -> dict[str, set[str]]:
        return {
            "money-rounding-source-missing": {"FSE-03"},
            "trade-partial-fill-cancel-race": {"FSE-04"},
            "risk-liquidation-price-source": {"FSE-02"},
            "reconciliation-break-correction": {"FSE-03"},
            "generic-crud-tests": {"FSE-01"},
        }

    def test_valid_manifest_and_red_receipts_write_results(self) -> None:
        result = self.run_validator(
            "red", self.write_receipts("red", self.red_misses())
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"phase":"red"', result.stdout)
        results = (self.temp / "eval-results.md").read_text()
        self.assertIn("## RED Baseline", results)
        self.assertIn("`tests/financial-systems-testing-eval/rubric.md`", results)
        self.assertIn(
            "`tests/financial-systems-testing-eval/prompts/money-rounding-source-missing.md`",
            results,
        )

    def test_rejects_duplicate_case_id(self) -> None:
        self.cases().append(dict(self.cases()[0]))
        self.write_manifest()
        result = self.run_validator(
            "red", self.write_receipts("red", self.red_misses())
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate case_id", result.stderr)

    def test_rejects_prompt_hash_mismatch(self) -> None:
        self.cases()[0]["prompt_sha256"] = "0" * 64
        self.write_manifest()
        result = self.run_validator(
            "red", self.write_receipts("red", self.red_misses())
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("prompt_sha256 mismatch", result.stderr)

    def test_rejects_missing_rubric_key(self) -> None:
        receipts_dir = self.write_receipts("red", self.red_misses())
        receipt_path = receipts_dir / "money-rounding-source-missing.receipt.json"
        receipt = load_json_object(receipt_path)
        rubric = receipt.get("rubric")
        if not isinstance(rubric, dict):
            self.fail("Expected rubric object")
        del cast(dict[str, object], rubric)["FSE-04"]
        _ = receipt_path.write_text(json.dumps(receipt) + "\n")
        result = self.run_validator("red", receipts_dir)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("rubric keys", result.stderr)

    def test_rejects_invalid_phase(self) -> None:
        result = self.run_validator(
            "invalid", self.write_receipts("red", self.red_misses())
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid choice", result.stderr)

    def test_rejects_red_without_branch_level_miss(self) -> None:
        result = self.run_validator("red", self.write_receipts("red"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("RED missing branch-level miss", result.stderr)

    def test_rejects_incomplete_receipt_set(self) -> None:
        receipts_dir = self.write_receipts("red", self.red_misses())
        (receipts_dir / "wallet-freeze-reversal.receipt.json").unlink()
        result = self.run_validator("red", receipts_dir)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("receipt set mismatch", result.stderr)

    def test_rejects_missing_raw_response(self) -> None:
        receipts_dir = self.write_receipts("red", self.red_misses())
        (receipts_dir / "money-rounding-source-missing.response.md").unlink()
        result = self.run_validator("red", receipts_dir)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("raw response missing", result.stderr)

    def test_rejects_tampered_raw_response(self) -> None:
        receipts_dir = self.write_receipts("red", self.red_misses())
        _ = (receipts_dir / "money-rounding-source-missing.response.md").write_text(
            "tampered"
        )
        result = self.run_validator("red", receipts_dir)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("response_sha256 mismatch", result.stderr)

    def test_rejects_mismatched_external_grader_provenance(self) -> None:
        receipts_dir = self.write_receipts("red", self.red_misses())
        provenance_path = receipts_dir / "grader-provenance.json"
        provenance = load_json_object(provenance_path)
        bindings = provenance.get("bindings")
        if not isinstance(bindings, list):
            self.fail("Expected provenance bindings")
        binding = cast(dict[str, object], bindings[0])
        binding["grader_task_id"] = "other-task"
        _ = provenance_path.write_text(json.dumps(provenance, sort_keys=True) + "\n")
        result = self.run_validator("red", receipts_dir)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("provenance grader_task_id mismatch", result.stderr)

    def test_rejects_missing_external_grader_provenance(self) -> None:
        receipts_dir = self.write_receipts("red", self.red_misses())
        (receipts_dir / "grader-provenance.json").unlink()
        result = self.run_validator("red", receipts_dir)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("grader provenance missing", result.stderr)

    def test_rejects_provenance_run_id_mismatch(self) -> None:
        receipts_dir = self.write_receipts("red", self.red_misses())
        provenance_path = receipts_dir / "grader-provenance.json"
        provenance = load_json_object(provenance_path)
        provenance["run_id"] = "other-run"
        _ = provenance_path.write_text(json.dumps(provenance, sort_keys=True) + "\n")
        result = self.run_validator("red", receipts_dir)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("grader provenance run_id mismatch", result.stderr)

    def test_rejects_raw_grader_producer_identity_mismatch(self) -> None:
        receipts_dir = self.write_receipts("red", self.red_misses())
        grader_path = receipts_dir / "money-rounding-source-missing.grader.json"
        grader_output = load_json_object(grader_path)
        grader_output["producer_session_id"] = "other-producer-session"
        self.refresh_grader_binding(
            receipts_dir, "money-rounding-source-missing", grader_output
        )
        result = self.run_validator("red", receipts_dir)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("grader output producer_session_id mismatch", result.stderr)

    def test_rejects_raw_grader_response_hash_mismatch(self) -> None:
        receipts_dir = self.write_receipts("red", self.red_misses())
        grader_path = receipts_dir / "money-rounding-source-missing.grader.json"
        grader_output = load_json_object(grader_path)
        grader_output["response_sha256"] = "0" * 64
        self.refresh_grader_binding(
            receipts_dir, "money-rounding-source-missing", grader_output
        )
        result = self.run_validator("red", receipts_dir)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("grader output response_sha256 mismatch", result.stderr)

    def test_rejects_missing_raw_grader_output(self) -> None:
        receipts_dir = self.write_receipts("red", self.red_misses())
        (receipts_dir / "money-rounding-source-missing.grader.json").unlink()
        result = self.run_validator("red", receipts_dir)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("raw grader output missing", result.stderr)

    def test_rejects_tampered_grader_output(self) -> None:
        receipts_dir = self.write_receipts("red", self.red_misses())
        _ = self.add_grader_artifact(receipts_dir, "money-rounding-source-missing")
        _ = (receipts_dir / "money-rounding-source-missing.grader.json").write_text(
            "tampered\n"
        )
        result = self.run_validator("red", receipts_dir)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("grader_output_sha256 mismatch", result.stderr)

    def test_rejects_green_with_failed_blocking_criterion(self) -> None:
        result = self.run_validator(
            "green",
            self.write_receipts("green", {"money-rounding-source-missing": {"FSE-04"}}),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("GREEN receipt failed blocking criterion FSE-04", result.stderr)


if __name__ == "__main__":
    _ = unittest.main()
