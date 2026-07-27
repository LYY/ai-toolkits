from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parent.parent
RUNNER = "tests/run_address_pr_comments_review_regressions.py"
CHECKER = "scripts/check-address-pr-comments-review-contract.sh"
DOSSIER = "skills/address-pr-comments-review/references/dossier-output.md"
MANIFEST = "tests/address-pr-comments-review-regressions/cases.json"
CASE_IDS = "tests/address-pr-comments-review-regressions/case-ids.txt"


class RegressionRunnerTestCase(unittest.TestCase):
    def copy_isolated_root(self, temp_dir: str) -> Path:
        isolated_root = Path(temp_dir) / "repository"
        shutil.copytree(
            REPO_ROOT,
            isolated_root,
            ignore=shutil.ignore_patterns(
                ".git", ".omo", ".codegraph", ".code-review-graph", "__pycache__"
            ),
        )
        return isolated_root

    def run_runner(
        self, isolated_root: Path, *args: str
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", RUNNER, *args],
            cwd=isolated_root,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )

    def run_checker(self, isolated_root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", CHECKER, str(isolated_root)],
            cwd=isolated_root,
            capture_output=True,
            text=True,
        )

    def dossier_path(self, isolated_root: Path) -> Path:
        return isolated_root / DOSSIER

    def manifest_path(self, isolated_root: Path) -> Path:
        return isolated_root / MANIFEST

    def test_full_runner_passes_in_copy_without_git_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = self.run_runner(self.copy_isolated_root(temp_dir))

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("total=20 passed=20 failed=0 skipped=0", result.stdout)

    def test_manifest_rejects_tampered_fixture_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            isolated_root = self.copy_isolated_root(temp_dir)
            manifest_path = (
                isolated_root
                / "tests/address-pr-comments-review-regressions/cases.json"
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["cases"][0]["fixture_sha256"] = "0" * 64
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            result = self.run_runner(isolated_root, "--validate-manifest-only")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("fixture_sha256 mismatch", result.stderr)

    def test_manifest_rejects_case_count_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            isolated_root = self.copy_isolated_root(temp_dir)
            manifest_path = (
                isolated_root
                / "tests/address-pr-comments-review-regressions/cases.json"
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["cases"].pop()
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            result = self.run_runner(isolated_root, "--validate-manifest-only")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Expected 20 cases, got 19", result.stderr)

    def test_route_direct_fix_invokes_v2_contract_function(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            isolated_root = self.copy_isolated_root(temp_dir)
            checker_path = isolated_root / CHECKER
            checker = checker_path.read_text(encoding="utf-8").replace(
                "check_direct_fix_v2_contract() {\n",
                "check_direct_fix_v2_contract() {\n"
                "    echo 'APR005: forced Direct Fix v2 check failure' >&2\n"
                "    return 1\n",
                1,
            )
            checker_path.write_text(checker, encoding="utf-8")

            result = self.run_runner(isolated_root)
            route_stderr = (
                isolated_root
                / "tests/address-pr-comments-review-regressions/cases"
                / "route-direct-fix/stderr.bin"
            ).read_text(encoding="utf-8")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FAIL: route-direct-fix", result.stdout)
        self.assertIn("APR005: forced Direct Fix v2 check failure", route_stderr)

    def test_manifest_rejects_renamed_case_and_catalog_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            isolated_root = self.copy_isolated_root(temp_dir)
            manifest_path = self.manifest_path(isolated_root)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["cases"][0]["case_id"] = "renamed-route"
            case_ids_path = isolated_root / CASE_IDS
            ids_text = case_ids_path.read_text(encoding="utf-8").replace(
                "route-review-dossier", "renamed-route", 1
            )
            case_ids_path.write_text(ids_text, encoding="utf-8")
            manifest["case_ids_sha256"] = hashlib.sha256(
                ids_text.encode("utf-8")
            ).hexdigest()
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            result = self.run_runner(isolated_root, "--validate-manifest-only")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("case_id inventory mismatch", result.stderr)

    def test_manifest_rejects_non_string_case_id_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            isolated_root = self.copy_isolated_root(temp_dir)
            manifest_path = self.manifest_path(isolated_root)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["cases"][0]["case_id"] = []
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            result = self.run_runner(isolated_root, "--validate-manifest-only")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("case_id must be a non-empty string", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_manifest_rejects_inexact_schema_and_field_types(self) -> None:
        mutations = (
            ("boolean-version", lambda manifest: manifest.update(schema_version=True)),
            ("extra-key", lambda manifest: manifest.update(unexpected=True)),
            ("invalid-env", lambda manifest: manifest["cases"][0].update(env=[])),
        )
        for name, mutate in mutations:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp_dir:
                isolated_root = self.copy_isolated_root(temp_dir)
                manifest_path = self.manifest_path(isolated_root)
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                mutate(manifest)
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

                result = self.run_runner(isolated_root, "--validate-manifest-only")

                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("Traceback", result.stderr)

    def test_runner_confines_arbitrary_artifact_path_to_case_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            isolated_root = self.copy_isolated_root(temp_dir)
            external_artifact = Path(temp_dir) / "outside.md"
            manifest_path = (
                isolated_root
                / "tests/address-pr-comments-review-regressions/cases.json"
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            case = next(
                case
                for case in manifest["cases"]
                if case["case_id"] == "checkout-mismatch"
            )
            artifact_index = case["argv"].index("--artifact") + 1
            case["argv"][artifact_index] = str(external_artifact)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            result = self.run_runner(isolated_root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse(external_artifact.exists())


if __name__ == "__main__":
    unittest.main()
