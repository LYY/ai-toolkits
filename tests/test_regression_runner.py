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
    ) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["python3", RUNNER, *args],
            cwd=isolated_root,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
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
