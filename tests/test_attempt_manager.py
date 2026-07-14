"""Unit tests for manage-address-pr-comments-review-attempt.py.

All tests invoke the script via subprocess with isolated temp envs.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import subprocess
import tempfile
import unittest


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
_SCRIPT_ABS = str(
    _REPO_ROOT / "scripts" / "manage-address-pr-comments-review-attempt.py"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run_script(
    script_args: list[str], env_overrides: dict | None = None
) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        ["python3", _SCRIPT_ABS] + script_args,
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
        env=env,
    )


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


class TestAttemptManager(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.repo_root = pathlib.Path(self.tmp_dir.name) / "repo"
        self.plan_dir = self.repo_root / ".omo" / "plans"
        self.plan_dir.mkdir(parents=True)
        self.plan_file = self.plan_dir / "plan.md"
        self.plan_file.write_text("test plan content\n")
        self.xdg_state = pathlib.Path(self.tmp_dir.name) / "xdg-state"
        self.xdg_state.mkdir()
        self.base_env = {"XDG_STATE_HOME": str(self.xdg_state)}

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def _run(
        self, *args: str, env_overrides: dict | None = None
    ) -> subprocess.CompletedProcess:
        env = self.base_env.copy()
        if env_overrides:
            env.update(env_overrides)
        return run_script(list(args), env_overrides=env)

    def _open_json(self, result: subprocess.CompletedProcess) -> dict:
        self.assertEqual(
            result.returncode,
            0,
            f"expected exit 0, got {result.returncode}; "
            f"stdout={result.stdout} stderr={result.stderr}",
        )
        return json.loads(result.stdout)

    # -------------------------------------------------------------------
    # test_attempt_open_resume
    # -------------------------------------------------------------------

    def test_attempt_open_resume(self) -> None:
        """open → created; re-open → resumed (same attempt_id); status → active."""

        gen_head = "a" * 40
        args = [
            "open",
            "--repo-root",
            str(self.repo_root),
            "--generation-head",
            gen_head,
            "--plan",
            str(self.plan_file),
        ]

        # Step 1: first open should create a new attempt
        res1 = self._run(*args)
        data1 = self._open_json(res1)
        self.assertEqual(data1["status"], "created")
        self.assertIsNotNone(data1["attempt_id"])
        self.assertIsNotNone(data1["attempt_path"])
        self.assertEqual(data1["operation"], "open")
        self.assertEqual(data1["schema_version"], 1)
        attempt_id = data1["attempt_id"]

        # Step 2: open again with same args → resumed, same attempt_id
        res2 = self._run(*args)
        data2 = self._open_json(res2)
        self.assertEqual(data2["status"], "resumed")
        self.assertEqual(data2["attempt_id"], attempt_id)
        self.assertEqual(data2["operation"], "open")

        # Step 3: status → state:"active", matching attempt_id
        res3 = self._run("status", "--repo-root", str(self.repo_root))
        data3 = self._open_json(res3)
        self.assertEqual(data3["operation"], "status")
        self.assertIsNotNone(data3["pointer"])
        self.assertEqual(data3["pointer"]["state"], "active")
        self.assertEqual(data3["pointer"]["attempt_id"], attempt_id)
        self.assertTrue(len(data3["pointer_sha256"]) > 0)

    # -------------------------------------------------------------------
    # test_attempt_bootstrap_crashes
    # -------------------------------------------------------------------

    def test_attempt_bootstrap_crashes(self) -> None:
        """Dirty bootstrapping dir → diagnostic_code:"recovery-required"."""
        canonical = str(self.repo_root.resolve()).encode("utf-8")
        repo_root_sha = _sha256_hex(canonical + b"\n")

        # Build state dirs
        state_base = (
            self.xdg_state
            / "ai-toolkits"
            / "address-pr-comments-review-executor-neutral"
        )
        active_dir = state_base / "active"
        active_dir.mkdir(parents=True, exist_ok=True)

        attempt_id = "00000000-0000-4000-8000-000000000001"
        attempt_dir = state_base / "attempts" / repo_root_sha / attempt_id

        # Plan SHA for the pointer
        plan_normalized = b"test plan content\n"
        plan_sha = _sha256_hex(plan_normalized)

        # Write a bootstrapping pointer
        pointer = {
            "schema_version": 1,
            "repo_root_sha256": repo_root_sha,
            "attempt_id": attempt_id,
            "attempt_path": str(attempt_dir),
            "state": "bootstrapping",
            "generation_head": "b" * 40,
            "plan_normalized_sha256": plan_sha,
            "aggregate_sha256": None,
            "updated_at": "2024-01-01T00:00:00+00:00",
        }
        pointer_path = active_dir / f"{repo_root_sha}.json"
        pointer_path.write_text(
            json.dumps(pointer, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )

        # Create attempt dir with an unexpected file → dirty state
        attempt_dir.mkdir(parents=True, exist_ok=True)
        (attempt_dir / "unexpected.txt").write_text("corrupt")

        # Run open → should die with recovery-required
        res = self._run(
            "open",
            "--repo-root",
            str(self.repo_root),
            "--generation-head",
            "a" * 40,
            "--plan",
            str(self.plan_file),
        )
        self.assertNotEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertEqual(data["diagnostic_code"], "recovery-required")
        self.assertEqual(data["operation"], "open")

    # -------------------------------------------------------------------
    # test_attempt_complete_cas
    # -------------------------------------------------------------------

    def test_attempt_complete_cas(self) -> None:
        """Complete transitions to completed; status confirms + aggregate_sha256."""
        gen_head = "a" * 40

        # Step 1: open
        res1 = self._run(
            "open",
            "--repo-root",
            str(self.repo_root),
            "--generation-head",
            gen_head,
            "--plan",
            str(self.plan_file),
        )
        data1 = self._open_json(res1)
        self.assertEqual(data1["status"], "created")
        attempt_id = data1["attempt_id"]
        attempt_path = pathlib.Path(data1["attempt_path"])
        pointer_sha = data1["pointer_sha256"]

        # Step 2: create final/review-wave.json and final/aggregate.json
        final_dir = attempt_path / "final"
        final_dir.mkdir(parents=True)

        wave_json = {
            "schema_version": 1,
            "state": "approved",
            "wave_id": "00000000-0000-4000-8000-000000000001",
            "generation_id": "00000000-0000-4000-8000-000000000002",
            "wave_dir": "waves/wave-1",
        }
        (final_dir / "review-wave.json").write_text(
            json.dumps(wave_json, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )

        aggregate_content = '{"schema_version":1,"status":"PASS"}\n'
        aggregate_path = final_dir / "aggregate.json"
        aggregate_path.write_text(aggregate_content, encoding="utf-8")

        # Step 3: complete
        res2 = self._run(
            "complete",
            "--repo-root",
            str(self.repo_root),
            "--attempt-id",
            attempt_id,
            "--pointer-sha256",
            pointer_sha,
            "--aggregate",
            str(aggregate_path),
        )
        data2 = self._open_json(res2)
        self.assertEqual(data2["status"], "completed")
        self.assertEqual(data2["operation"], "complete")
        self.assertEqual(data2["attempt_id"], attempt_id)

        # Step 4: status → completed, aggregate_sha256 non-null
        res3 = self._run("status", "--repo-root", str(self.repo_root))
        data3 = self._open_json(res3)
        self.assertEqual(data3["pointer"]["state"], "completed")
        self.assertIsNotNone(data3["pointer"]["aggregate_sha256"])
        self.assertTrue(len(data3["pointer"]["aggregate_sha256"]) > 0)

    # -------------------------------------------------------------------
    # test_attempt_complete_replay
    # -------------------------------------------------------------------

    def test_attempt_complete_replay(self) -> None:
        """Re-completing same state → already-completed, same pointer_sha256."""
        gen_head = "a" * 40

        # Open
        res1 = self._run(
            "open",
            "--repo-root",
            str(self.repo_root),
            "--generation-head",
            gen_head,
            "--plan",
            str(self.plan_file),
        )
        data1 = self._open_json(res1)
        attempt_id = data1["attempt_id"]
        attempt_path = pathlib.Path(data1["attempt_path"])
        pointer_sha = data1["pointer_sha256"]

        # Set up final dir
        final_dir = attempt_path / "final"
        final_dir.mkdir(parents=True)
        wave_json = {
            "schema_version": 1,
            "state": "approved",
            "wave_id": "00000000-0000-4000-8000-000000000001",
            "generation_id": "00000000-0000-4000-8000-000000000002",
            "wave_dir": "waves/wave-1",
        }
        (final_dir / "review-wave.json").write_text(
            json.dumps(wave_json, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        aggregate_path = final_dir / "aggregate.json"
        aggregate_path.write_text(
            '{"schema_version":1,"status":"PASS"}\n', encoding="utf-8"
        )

        # First complete
        res2 = self._run(
            "complete",
            "--repo-root",
            str(self.repo_root),
            "--attempt-id",
            attempt_id,
            "--pointer-sha256",
            pointer_sha,
            "--aggregate",
            str(aggregate_path),
        )
        data2 = self._open_json(res2)
        self.assertEqual(data2["status"], "completed")

        # Second complete with same args → already-completed
        res3 = self._run(
            "complete",
            "--repo-root",
            str(self.repo_root),
            "--attempt-id",
            attempt_id,
            "--pointer-sha256",
            data2["pointer_sha256"],
            "--aggregate",
            str(aggregate_path),
        )
        data3 = self._open_json(res3)
        self.assertEqual(data3["status"], "already-completed")
        self.assertEqual(data3["pointer_sha256"], data2["pointer_sha256"])
        self.assertEqual(data3["attempt_id"], attempt_id)

    # -------------------------------------------------------------------
    # test_attempt_non_posix_no_write
    # -------------------------------------------------------------------

    def test_attempt_non_posix_no_write(self) -> None:
        """Verify source has POSIX guard: fcntl ImportError → exit(2)."""
        script_path = (
            _REPO_ROOT / "scripts" / "manage-address-pr-comments-review-attempt.py"
        )
        self.assertTrue(script_path.exists(), f"Script not found: {script_path}")
        source = script_path.read_text(encoding="utf-8")

        self.assertIn(
            "except ImportError:", source, "Missing ImportError guard for fcntl"
        )
        self.assertIn(
            '"platform-unsupported"',
            source,
            "Missing platform-unsupported diagnostic code",
        )
        self.assertIn("POSIX required", source, "Missing POSIX required message")
        self.assertIn("sys.exit(2)", source, "Missing exit(2) on platform unsupported")
        self.assertIn(
            "DIAG_PLATFORM_UNSUPPORTED",
            source,
            "Missing DIAG_PLATFORM_UNSUPPORTED constant",
        )


if __name__ == "__main__":
    unittest.main()
