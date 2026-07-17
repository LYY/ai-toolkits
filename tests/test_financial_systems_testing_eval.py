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
        for case in self.cases():
            case_id = required_str(case, "case_id")
            receipt = self.receipt(case, phase, misses.get(case_id, set()))
            _ = (receipts_dir / f"{case_id}.json").write_text(
                json.dumps(receipt, sort_keys=True) + "\n"
            )
        return receipts_dir

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
        receipt_path = receipts_dir / "money-rounding-source-missing.json"
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
        (receipts_dir / "wallet-freeze-reversal.json").unlink()
        result = self.run_validator("red", receipts_dir)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("receipt set mismatch", result.stderr)

    def test_rejects_green_with_failed_blocking_criterion(self) -> None:
        result = self.run_validator(
            "green",
            self.write_receipts("green", {"money-rounding-source-missing": {"FSE-04"}}),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("GREEN receipt failed blocking criterion FSE-04", result.stderr)


if __name__ == "__main__":
    _ = unittest.main()
