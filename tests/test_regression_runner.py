from __future__ import annotations

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

    def test_route_direct_fix_invokes_v2_contract_checks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            isolated_root = self.copy_isolated_root(temp_dir)
            dossier_path = (
                isolated_root
                / "skills/address-pr-comments-review/references/dossier-output.md"
            )
            dossier = dossier_path.read_text(encoding="utf-8").replace(
                "<!-- direct-fix-policy:start -->\n", "", 1
            )
            dossier_path.write_text(dossier, encoding="utf-8")

            result = self.run_runner(isolated_root)
            route_stderr = (
                isolated_root
                / "tests/address-pr-comments-review-regressions/cases"
                / "route-direct-fix/stderr.bin"
            ).read_text(encoding="utf-8")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FAIL: route-direct-fix", result.stdout)
        self.assertIn(
            'APR003: missing marker "<!-- direct-fix-policy:start -->"',
            route_stderr,
        )

    def test_checker_rejects_legacy_field_inside_direct_fix_section(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            isolated_root = self.copy_isolated_root(temp_dir)
            dossier_path = (
                isolated_root
                / "skills/address-pr-comments-review/references/dossier-output.md"
            )
            dossier = dossier_path.read_text(encoding="utf-8").replace(
                "- **expected_paths**: [CHANGED_OR_VERIFICATION_PATH, ...]\n",
                "- **expected_paths**: [CHANGED_OR_VERIFICATION_PATH, ...]\n"
                + "- **Implementation paths**: [CHANGED_PATH, ...]\n",
                1,
            )
            dossier_path.write_text(dossier, encoding="utf-8")

            result = self.run_checker(isolated_root)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            'APR005: legacy Direct Fix field "Implementation paths"',
            result.stderr,
        )

    def test_checker_allows_legacy_field_outside_direct_fix_section(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            isolated_root = self.copy_isolated_root(temp_dir)
            dossier_path = (
                isolated_root
                / "skills/address-pr-comments-review/references/dossier-output.md"
            )
            dossier = dossier_path.read_text(encoding="utf-8").replace(
                "## Direct Fix Brief\n",
                "Legacy rejection catalog: Implementation paths\n\n## Direct Fix Brief\n",
                1,
            )
            dossier_path.write_text(dossier, encoding="utf-8")

            result = self.run_checker(isolated_root)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

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
