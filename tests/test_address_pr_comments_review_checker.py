from __future__ import annotations

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
DESIGN = "docs/address-pr-comments-review/executor-neutral-design.md"
ARCHITECTURE = "docs/address-pr-comments-review/architecture.md"


class ContractCheckerTestCase(unittest.TestCase):
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

    def run_runner(self, isolated_root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", RUNNER],
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

    def test_checker_rejects_malformed_policy_boundaries(self) -> None:
        start = "<!-- direct-fix-policy:start -->"
        end = "<!-- direct-fix-policy:end -->"
        mutations = (
            ("missing", f"{start}\n", "", "APR003: missing marker"),
            ("duplicate", start, f"{start}\n{start}", "APR003: duplicate marker"),
            ("misordered", start, end, "APR004: marker"),
            ("missing-section-end", "## Reply Policy\n", "", "APR005:"),
        )
        for name, old, new, diagnostic in mutations:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp_dir:
                isolated_root = self.copy_isolated_root(temp_dir)
                dossier_path = self.dossier_path(isolated_root)
                dossier = dossier_path.read_text(encoding="utf-8")
                if name == "misordered":
                    dossier = (
                        dossier.replace(start, "POLICY_MARKER_PLACEHOLDER", 1)
                        .replace(end, start, 1)
                        .replace("POLICY_MARKER_PLACEHOLDER", end, 1)
                    )
                else:
                    dossier = dossier.replace(old, new, 1)
                dossier_path.write_text(dossier, encoding="utf-8")

                result = self.run_checker(isolated_root)

                self.assertNotEqual(result.returncode, 0)
                self.assertIn(diagnostic, result.stderr)

    def test_checker_rejects_noncanonical_policy_schema_version(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            isolated_root = self.copy_isolated_root(temp_dir)
            dossier_path = self.dossier_path(isolated_root)
            dossier = dossier_path.read_text(encoding="utf-8").replace(
                '"direct_fix_schema_version":2',
                '"direct_fix_schema_version":1',
                1,
            )
            dossier_path.write_text(dossier, encoding="utf-8")
            result = self.run_checker(isolated_root)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "APR005: canonical Direct Fix policy JSON mismatch", result.stderr
        )

    def test_checker_rejects_policy_block_outside_direct_fix_section(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            isolated_root = self.copy_isolated_root(temp_dir)
            dossier_path = self.dossier_path(isolated_root)
            dossier = dossier_path.read_text(encoding="utf-8")
            start = dossier.index("<!-- direct-fix-policy:start -->")
            end_marker = "<!-- direct-fix-policy:end -->"
            end = dossier.index(end_marker, start) + len(end_marker)
            policy_block = dossier[start:end]
            dossier = dossier[:start] + dossier[end:]
            dossier = dossier.replace(
                "## Direct Fix Brief\n",
                f"{policy_block}\n\n## Direct Fix Brief\n",
                1,
            )
            dossier_path.write_text(dossier, encoding="utf-8")
            result = self.run_checker(isolated_root)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("APR004: Direct Fix policy markers must be inside", result.stderr)

    def test_checker_only_copy_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            isolated_root = Path(temp_dir) / "repository"
            scripts_dir = isolated_root / "scripts"
            scripts_dir.mkdir(parents=True)
            shutil.copy2(REPO_ROOT / CHECKER, scripts_dir / Path(CHECKER).name)
            result = self.run_checker(isolated_root)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "APR010: missing required product file"
            " skills/address-pr-comments-review/SKILL.md",
            result.stderr,
        )

    def test_checker_requires_all_declared_product_documents(self) -> None:
        for product_path in (DESIGN, ARCHITECTURE):
            with (
                self.subTest(product_path=product_path),
                tempfile.TemporaryDirectory() as temp_dir,
            ):
                isolated_root = self.copy_isolated_root(temp_dir)
                (isolated_root / product_path).unlink()

                result = self.run_checker(isolated_root)

                self.assertNotEqual(result.returncode, 0)
                self.assertIn(
                    f"APR010: missing required product file {product_path}",
                    result.stderr,
                )

    def test_missing_reply_policy_heading_emits_one_stable_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            isolated_root = self.copy_isolated_root(temp_dir)
            dossier_path = self.dossier_path(isolated_root)
            dossier = dossier_path.read_text(encoding="utf-8").replace(
                "## Reply Policy\n", "", 1
            )
            dossier_path.write_text(dossier, encoding="utf-8")

            result = self.run_checker(isolated_root)

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(
            result.stderr.splitlines(),
            [
                "APR005: Direct Fix Brief section requires one start and one end "
                "heading; found start=1 end=0"
            ],
        )

    def test_checker_rejects_normalized_relative_symlink_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            isolated_root = self.copy_isolated_root(temp_dir)
            (isolated_root / "inside").mkdir()
            (Path(temp_dir) / "outside").write_text("outside", encoding="utf-8")
            (isolated_root / "escape").symlink_to("inside/../../outside")
            result = self.run_checker(isolated_root)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("APR008:", result.stderr)

    def test_checker_allows_legacy_phrase_inside_direct_fix_section(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            isolated_root = self.copy_isolated_root(temp_dir)
            dossier_path = self.dossier_path(isolated_root)
            dossier = dossier_path.read_text(encoding="utf-8").replace(
                "## Direct Fix Brief\n",
                "## Direct Fix Brief\n\nChange paths are derived from selectors.\n",
                1,
            )
            dossier_path.write_text(dossier, encoding="utf-8")
            result = self.run_checker(isolated_root)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_checker_rejects_legacy_field_inside_direct_fix_section(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            isolated_root = self.copy_isolated_root(temp_dir)
            dossier_path = self.dossier_path(isolated_root)
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
            'APR005: legacy Direct Fix field "Implementation paths"', result.stderr
        )

    def test_checker_allows_legacy_field_outside_direct_fix_section(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            isolated_root = self.copy_isolated_root(temp_dir)
            dossier_path = self.dossier_path(isolated_root)
            dossier = dossier_path.read_text(encoding="utf-8").replace(
                "## Direct Fix Brief\n",
                "Legacy rejection catalog: Implementation paths\n\n"
                "## Direct Fix Brief\n",
                1,
            )
            dossier_path.write_text(dossier, encoding="utf-8")
            result = self.run_checker(isolated_root)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
