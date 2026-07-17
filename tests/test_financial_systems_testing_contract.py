from __future__ import annotations

import pathlib
import shutil
import subprocess
import tempfile
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
CHECKER = REPO_ROOT / "scripts" / "check-financial-systems-testing-contract.sh"
RUNNER = REPO_ROOT / "tests" / "financial-systems-testing-contract" / "run.sh"
MANIFEST = REPO_ROOT / "tests" / "financial-systems-testing-contract" / "manifest.tsv"
SKILL_DIR = REPO_ROOT / "skills" / "financial-systems-testing"


class FinancialSystemsTestingContractTests(unittest.TestCase):
    def run_checker(self, root: pathlib.Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(CHECKER), str(root)],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_missing_required_file_reports_fst001(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            result = self.run_checker(root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FST001", result.stderr)

    def test_manifest_covers_every_diagnostic_and_fst008_submutation(self) -> None:
        rows = [
            line.split("\t")
            for line in MANIFEST.read_text(encoding="utf-8").splitlines()
            if line and not line.startswith("#") and not line.startswith("case_id")
        ]
        diagnostics = {row[3] for row in rows if row[3] != "-"}
        self.assertEqual(diagnostics, {f"FST00{number}" for number in range(1, 10)})
        fst008_mutations = {row[1] for row in rows if row[3] == "FST008"}
        self.assertEqual(
            fst008_mutations,
            {
                "reference-skill-backlink",
                "reference-sibling-link",
                "reference-docs-link",
                "reference-absolute-path",
                "reference-public-skill-route",
            },
        )
        self.assertIn("forbidden-compliance-name", {row[1] for row in rows})

    def test_happy_skill_passes_contract_checker(self) -> None:
        result = self.run_checker(REPO_ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_mutation_suite_has_one_stable_diagnostic_per_case(self) -> None:
        result = subprocess.run(
            ["bash", str(RUNNER)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("failed=0", result.stdout)

    def test_checker_accepts_an_explicit_repo_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            (root / "skills").mkdir()
            _ = shutil.copytree(
                SKILL_DIR, root / "skills" / "financial-systems-testing"
            )
            result = self.run_checker(root)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    _ = unittest.main()
