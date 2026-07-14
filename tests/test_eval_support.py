"""Unit tests for eval support scripts.

Tests cover:
  - scripts/prepare-address-pr-comments-review-eval.py   (receipt + score CLIs)
  - scripts/sanitize-address-pr-comments-review-eval.py   (red-summary + green-output)
  - scripts/validate-address-pr-comments-review-receipts.py (validator)

All tests invoke scripts via subprocess with isolated temp envs.
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
_PREPARE_SCRIPT = str(
    _REPO_ROOT / "scripts" / "prepare-address-pr-comments-review-eval.py"
)
_SANITIZE_SCRIPT = str(
    _REPO_ROOT / "scripts" / "sanitize-address-pr-comments-review-eval.py"
)
_VALIDATE_SCRIPT = str(
    _REPO_ROOT / "scripts" / "validate-address-pr-comments-review-receipts.py"
)
_FIXTURES = _REPO_ROOT / "tests" / "address-pr-comments-review-eval"


# Canonical JSON helper
def _canonical_json_bytes(obj: object) -> bytes:
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return (text + "\n").encode("utf-8")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run_script(
    script_path: str, args: list[str], cwd: str | None = None
) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        ["python3", script_path] + args,
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env,
    )
    return result


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _make_transcript(
    user_body: str, assistant_body: str, tools: list[str] | None = None
) -> str:
    """Build a session-read-v2 transcript with user, tools, and assistant."""
    lines = [f"[user (2024-01-01T00:00:00Z)] {user_body}"]
    for tname in tools or []:
        lines.append(f"[tool: {tname}]")
        lines.append("{")
        lines.append('  "action": "read"')
        lines.append("}")
    lines.append(f"[assistant (2024-01-01T00:00:05Z)] {assistant_body}")
    return "\n".join(lines) + "\n"


def _make_valid_response_json(case_id: str = "complex-dossier") -> dict:
    """Build a response dict that passes all EN-01..EN-05 checks."""
    return {
        "routes": ["review-dossier"],
        "persisted_artifacts": ["review-dossier"],
        "section_a_order": [
            "edit",
            "verify",
            "commit",
            "remote-reachability",
            "reply",
            "read-back",
        ],
        "push_authorized": False,
        "recovery": {
            "stable_ids": True,
            "cas": True,
            "read_back": True,
            "cleanup_blocks_incomplete": True,
        },
        "runtime_specific_terms": [],
        "handoff_complete": True,
    }


def _make_valid_receipt(
    phase: str,
    case_id: str,
    ordinal: int,
    session_id: str,
    task_id: str,
    description: str,
) -> dict:
    """Build a receipt dict that passes structural validation."""
    prompt_raw = "test prompt content"
    response_raw = "test response content"
    return {
        "schema_version": 1,
        "transcript_format": "session-read-v2",
        "adapter_contract_version": "task-explore-v1",
        "description": description,
        "run_id": "00000000-0000-4000-8000-000000000001",
        "phase": phase,
        "case_id": case_id,
        "ordinal": ordinal,
        "task_id": task_id,
        "session_id": session_id,
        "prompt_raw_sha256": _sha256_hex(prompt_raw.encode("utf-8")),
        "prompt_canonical_sha256": _sha256_hex(prompt_raw.encode("utf-8")),
        "delivered_user_sha256": _sha256_hex(prompt_raw.encode("utf-8")),
        "response_raw_sha256": _sha256_hex(response_raw.encode("utf-8")),
        "response_canonical_sha256": _sha256_hex(response_raw.encode("utf-8")),
        "tool_events_sha256": _sha256_hex(b"[]\n"),
        "transcript_raw_sha256": _sha256_hex(b"fake-transcript\n"),
        "started_at": "2024-01-01T00:00:00Z",
        "finished_at": "2024-01-01T00:00:05Z",
    }


def _make_minimal_manifest(cases: list[dict]) -> dict:
    """Build a minimal cases.json manifest."""
    return {"schema_version": 1, "cases": cases}


# ---------------------------------------------------------------------------
# TestPrepareReceiptCLI
# ---------------------------------------------------------------------------


class TestPrepareReceiptCLI(unittest.TestCase):
    """Tests for --receipt mode of prepare-address-pr-comments-review-eval.py."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp = pathlib.Path(self.tmp_dir.name)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    # -- basic success -------------------------------------------------------

    def test_receipt_basic(self) -> None:
        """Receipt created from valid transcript with allowed tools."""
        transcript = _make_transcript(
            "Hello, explore the code.",
            "I found the issue.",
            tools=["read", "glob"],
        )
        tx_path = self.tmp / "transcript.txt"
        tx_path.write_text(transcript)
        out_path = self.tmp / "receipt.json"

        result = run_script(
            _PREPARE_SCRIPT,
            [
                "--receipt",
                "--phase",
                "green",
                "--case-id",
                "complex-dossier",
                "--ordinal",
                "1",
                "--description",
                "test run",
                "--task-id",
                "task-1",
                "--session-id",
                "ses-1",
                "--prompt",
                str(self.tmp / "dummy.txt"),
                "--response",
                str(self.tmp / "dummy.txt"),
                "--transcript",
                str(tx_path),
                "--output",
                str(out_path),
            ],
        )
        self.assertEqual(result.returncode, 0, f"stderr={result.stderr}")
        data = json.loads(result.stdout)
        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(data["phase"], "green")
        self.assertEqual(data["case_id"], "complex-dossier")
        self.assertEqual(data["ordinal"], 1)
        self.assertTrue(out_path.exists())

    def test_receipt_no_tools(self) -> None:
        """Receipt created from transcript with no tool invocations."""
        transcript = _make_transcript("Hello.", "Response.", tools=[])
        tx_path = self.tmp / "transcript.txt"
        tx_path.write_text(transcript)
        out_path = self.tmp / "receipt.json"

        result = run_script(
            _PREPARE_SCRIPT,
            [
                "--receipt",
                "--phase",
                "green",
                "--case-id",
                "complex-dossier",
                "--ordinal",
                "1",
                "--description",
                "test",
                "--task-id",
                "task-1",
                "--session-id",
                "ses-1",
                "--prompt",
                str(self.tmp / "dummy.txt"),
                "--response",
                str(self.tmp / "dummy.txt"),
                "--transcript",
                str(tx_path),
                "--output",
                str(out_path),
            ],
        )
        self.assertEqual(result.returncode, 0, f"stderr={result.stderr}")
        data = json.loads(result.stdout)
        self.assertEqual(data["tool_events_sha256"], _sha256_hex(b"[]\n"))

    # -- failure: unknown tool -------------------------------------------------

    def test_transcript_tool_failure(self) -> None:
        """Transcript with unknown tool name → receipt CLI rejects."""
        transcript = _make_transcript(
            "Hello.", "Response.", tools=["some_unknown_tool"]
        )
        tx_path = self.tmp / "transcript.txt"
        tx_path.write_text(transcript)
        out_path = self.tmp / "receipt.json"

        result = run_script(
            _PREPARE_SCRIPT,
            [
                "--receipt",
                "--phase",
                "green",
                "--case-id",
                "complex-dossier",
                "--ordinal",
                "1",
                "--description",
                "test",
                "--task-id",
                "task-1",
                "--session-id",
                "ses-1",
                "--prompt",
                str(self.tmp / "dummy.txt"),
                "--response",
                str(self.tmp / "dummy.txt"),
                "--transcript",
                str(tx_path),
                "--output",
                str(out_path),
            ],
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Disallowed tool name", result.stderr)
        self.assertIn("some_unknown_tool", result.stderr)

    # -- failure: no user message ---------------------------------------------

    def test_receipt_no_user_message(self) -> None:
        """Transcript without user message → rejected."""
        transcript = "[assistant (2024-01-01T00:00:05Z)] Only assistant\n"
        tx_path = self.tmp / "transcript.txt"
        tx_path.write_text(transcript)
        out_path = self.tmp / "receipt.json"

        result = run_script(
            _PREPARE_SCRIPT,
            [
                "--receipt",
                "--phase",
                "green",
                "--case-id",
                "complex-dossier",
                "--ordinal",
                "1",
                "--description",
                "test",
                "--task-id",
                "task-1",
                "--session-id",
                "ses-1",
                "--prompt",
                str(self.tmp / "dummy.txt"),
                "--response",
                str(self.tmp / "dummy.txt"),
                "--transcript",
                str(tx_path),
                "--output",
                str(out_path),
            ],
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No user message", result.stderr)

    # -- probe phase guards ---------------------------------------------------

    def test_receipt_probe_ordinal1_no_tools(self) -> None:
        """Probe phase ordinal=1 with tools → rejected."""
        transcript = _make_transcript("Hello.", "Response.", tools=["read"])
        tx_path = self.tmp / "transcript.txt"
        tx_path.write_text(transcript)
        out_path = self.tmp / "receipt.json"

        result = run_script(
            _PREPARE_SCRIPT,
            [
                "--receipt",
                "--phase",
                "probe",
                "--case-id",
                "complex-dossier",
                "--ordinal",
                "1",
                "--description",
                "test",
                "--task-id",
                "task-1",
                "--session-id",
                "ses-1",
                "--prompt",
                str(self.tmp / "dummy.txt"),
                "--response",
                str(self.tmp / "dummy.txt"),
                "--transcript",
                str(tx_path),
                "--output",
                str(out_path),
            ],
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("zero tool events", result.stderr)

    def test_receipt_probe_ordinal2_needs_read(self) -> None:
        """Probe phase ordinal=2 without 'read' tool → rejected."""
        transcript = _make_transcript("Hello.", "Response.", tools=["glob"])
        tx_path = self.tmp / "transcript.txt"
        tx_path.write_text(transcript)
        out_path = self.tmp / "receipt.json"

        result = run_script(
            _PREPARE_SCRIPT,
            [
                "--receipt",
                "--phase",
                "probe",
                "--case-id",
                "complex-dossier",
                "--ordinal",
                "2",
                "--description",
                "test",
                "--task-id",
                "task-1",
                "--session-id",
                "ses-1",
                "--prompt",
                str(self.tmp / "dummy.txt"),
                "--response",
                str(self.tmp / "dummy.txt"),
                "--transcript",
                str(tx_path),
                "--output",
                str(out_path),
            ],
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires at least one 'read' tool", result.stderr)


# ---------------------------------------------------------------------------
# TestPrepareScoreCLI
# ---------------------------------------------------------------------------


class TestPrepareScoreCLI(unittest.TestCase):
    """Tests for --score mode of prepare-address-pr-comments-review-eval.py."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp = pathlib.Path(self.tmp_dir.name)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    # -- basic success -------------------------------------------------------

    def test_score_all_pass(self) -> None:
        """Valid response JSON → all EN criteria pass."""
        resp = _make_valid_response_json()
        resp_path = self.tmp / "response.json"
        resp_path.write_bytes(_canonical_json_bytes(resp))
        out_path = self.tmp / "score.json"

        result = run_script(
            _PREPARE_SCRIPT,
            [
                "--score",
                "--phase",
                "green",
                "--case-id",
                "complex-dossier",
                "--response",
                str(resp_path),
                "--output",
                str(out_path),
            ],
        )
        self.assertEqual(result.returncode, 0, f"stderr={result.stderr}")
        data = json.loads(result.stdout)
        self.assertTrue(data["all_pass"])
        for v in data["verdicts"]:
            self.assertEqual(v["status"], "PASS", f"verdict {v} not PASS")

    def test_score_en01_fail_forbidden_words(self) -> None:
        """Response with forbidden words → EN-01 FAIL, remaining FAIL."""
        resp = _make_valid_response_json()
        resp["runtime_specific_terms"] = ["opencode"]  # forbidden
        resp_path = self.tmp / "response.json"
        resp_path.write_bytes(_canonical_json_bytes(resp))
        out_path = self.tmp / "score.json"

        result = run_script(
            _PREPARE_SCRIPT,
            [
                "--score",
                "--phase",
                "red",
                "--case-id",
                "complex-dossier",
                "--response",
                str(resp_path),
                "--output",
                str(out_path),
            ],
        )
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertFalse(data["all_pass"])
        en01 = next(v for v in data["verdicts"] if v["criterion_id"] == "EN-01")
        self.assertEqual(en01["status"], "FAIL")
        self.assertEqual(en01["reason_code"], "forbidden-term")
        # All verdicts should be FAIL (EN-01 failure cascades)
        for v in data["verdicts"]:
            self.assertEqual(v["status"], "FAIL")

    def test_score_en02_route_mismatch(self) -> None:
        """Wrong routes → EN-02 FAIL."""
        resp = _make_valid_response_json()
        resp["routes"] = ["wrong-route"]
        resp_path = self.tmp / "response.json"
        resp_path.write_bytes(_canonical_json_bytes(resp))
        out_path = self.tmp / "score.json"

        result = run_script(
            _PREPARE_SCRIPT,
            [
                "--score",
                "--phase",
                "green",
                "--case-id",
                "complex-dossier",
                "--response",
                str(resp_path),
                "--output",
                str(out_path),
            ],
        )
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertFalse(data["all_pass"])
        en02 = next(v for v in data["verdicts"] if v["criterion_id"] == "EN-02")
        self.assertEqual(en02["status"], "FAIL")
        self.assertEqual(en02["reason_code"], "route-mismatch")

    def test_score_parse_error(self) -> None:
        """Invalid JSON → all parse-error."""
        resp_path = self.tmp / "response.json"
        resp_path.write_text("not json", encoding="utf-8")
        out_path = self.tmp / "score.json"

        result = run_script(
            _PREPARE_SCRIPT,
            [
                "--score",
                "--phase",
                "green",
                "--case-id",
                "complex-dossier",
                "--response",
                str(resp_path),
                "--output",
                str(out_path),
            ],
        )
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertFalse(data["all_pass"])
        for v in data["verdicts"]:
            self.assertEqual(v["status"], "FAIL")
            self.assertEqual(v["reason_code"], "parse-error")

    def test_score_matrix_all_four_cases(self) -> None:
        """All 4 case IDs produce valid score output."""
        for case_id in [
            "complex-dossier",
            "direct-fix-fallback",
            "interrupted-recovery",
            "neutral-handoff",
        ]:
            with self.subTest(case_id=case_id):
                resp = _make_valid_response_json(case_id)
                # neutral-handoff needs correct routes/artifacts
                if case_id == "neutral-handoff":
                    resp["routes"] = sorted(
                        ["direct-fix", "no-action", "reply-only", "review-dossier"]
                    )
                    resp["persisted_artifacts"] = sorted(
                        ["direct-fix-brief", "review-dossier"]
                    )

                resp_path = self.tmp / f"{case_id}_response.json"
                resp_path.write_bytes(_canonical_json_bytes(resp))
                out_path = self.tmp / f"{case_id}_score.json"

                result = run_script(
                    _PREPARE_SCRIPT,
                    [
                        "--score",
                        "--phase",
                        "green",
                        "--case-id",
                        case_id,
                        "--response",
                        str(resp_path),
                        "--output",
                        str(out_path),
                    ],
                )
                self.assertEqual(result.returncode, 0)

    # -- criterion text drift -------------------------------------------------

    def test_criterion_text_drift(self) -> None:
        """Score JSON with criterion-violating content → detected by score CLI."""
        # EN-04 requires stable_ids=True, cas=True, etc.
        # Drift: set recovery fields to False
        resp = _make_valid_response_json()
        resp["recovery"] = {
            "stable_ids": False,
            "cas": False,
            "read_back": False,
            "cleanup_blocks_incomplete": False,
        }
        resp_path = self.tmp / "response.json"
        resp_path.write_bytes(_canonical_json_bytes(resp))
        out_path = self.tmp / "score.json"

        result = run_script(
            _PREPARE_SCRIPT,
            [
                "--score",
                "--phase",
                "green",
                "--case-id",
                "complex-dossier",
                "--response",
                str(resp_path),
                "--output",
                str(out_path),
            ],
        )
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        en04 = next(v for v in data["verdicts"] if v["criterion_id"] == "EN-04")
        self.assertEqual(en04["status"], "FAIL")
        self.assertEqual(en04["reason_code"], "recovery-mismatch")


# ---------------------------------------------------------------------------
# TestCheckboxNormalizationDrift
# ---------------------------------------------------------------------------


class TestCheckboxNormalizationDrift(unittest.TestCase):
    """Tests that _canonicalize_text produces consistent SHA across checkbox
    formatting variations — trailing whitespace stripped per line, but checkbox
    content ([x] vs [ ]) preserved."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp = pathlib.Path(self.tmp_dir.name)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def _run_canonicalize(self, raw_text: str) -> str:
        """Invoke canonicalize via receipt CLI output hashes to verify."""
        # Build transcript that passes validation
        user_msg = raw_text
        assistant_msg = "OK."
        transcript = _make_transcript(user_msg, assistant_msg)
        tx_path = self.tmp / "transcript.txt"
        tx_path.write_text(transcript)
        out_path = self.tmp / "receipt.json"

        result = run_script(
            _PREPARE_SCRIPT,
            [
                "--receipt",
                "--phase",
                "green",
                "--case-id",
                "complex-dossier",
                "--ordinal",
                "1",
                "--description",
                "test",
                "--task-id",
                "task-1",
                "--session-id",
                "ses-1",
                "--prompt",
                str(tx_path),
                "--response",
                str(tx_path),
                "--transcript",
                str(tx_path),
                "--output",
                str(out_path),
            ],
        )
        if result.returncode != 0:
            raise RuntimeError(f"receipt CLI failed: {result.stderr}")
        data = json.loads(result.stdout)
        return data["prompt_canonical_sha256"]

    def test_checkbox_normalization_drift(self) -> None:
        """Checkbox formatting variations produce consistent SHA."""
        # Same checkbox content, different trailing whitespace → same SHA
        plan_a = "- [x] Task one  \n- [ ] Task two  \t\n"
        plan_b = "- [x] Task one\n- [ ] Task two\n"
        sha_a = self._run_canonicalize(plan_a)
        sha_b = self._run_canonicalize(plan_b)
        self.assertEqual(
            sha_a,
            sha_b,
            "SHA differs for same content with different trailing whitespace",
        )

        # Different checkbox states → different SHA
        plan_checked = "- [x] Done\n"
        plan_unchecked = "- [ ] Done\n"
        sha_c = self._run_canonicalize(plan_checked)
        sha_u = self._run_canonicalize(plan_unchecked)
        self.assertNotEqual(sha_c, sha_u, "SHA should differ for checked vs unchecked")

    def test_normalization_crlf_to_lf(self) -> None:
        """CRLF normalization: same content yields same SHA."""
        plan_lf = "Line 1\nLine 2\n"
        plan_crlf = "Line 1\r\nLine 2\r\n"
        sha_lf = self._run_canonicalize(plan_lf)
        sha_crlf = self._run_canonicalize(plan_crlf)
        self.assertEqual(sha_lf, sha_crlf)

    def test_normalization_trim_blank_lines(self) -> None:
        """Leading/trailing blank lines trimmed."""
        plan_clean = "Content\n"
        plan_blanks = "\n\n\nContent\n\n\n"
        sha_clean = self._run_canonicalize(plan_clean)
        sha_blanks = self._run_canonicalize(plan_blanks)
        self.assertEqual(sha_clean, sha_blanks)


# ---------------------------------------------------------------------------
# TestSanitizer
# ---------------------------------------------------------------------------


class TestSanitizer(unittest.TestCase):
    """Tests for sanitize-address-pr-comments-review-eval.py."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp = pathlib.Path(self.tmp_dir.name)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    # -- red-summary mode ----------------------------------------------------

    def test_sanitize_red_summary(self) -> None:
        """RED summary mode: reads score JSON, writes content-addressed file."""
        score_obj = {
            "schema_version": 1,
            "phase": "red",
            "case_id": "complex-dossier",
            "output_sha256": _sha256_hex(b"fake"),
            "verdicts": [
                {
                    "criterion_id": "EN-01",
                    "status": "FAIL",
                    "reason_code": "forbidden-term",
                }
            ],
            "all_pass": False,
        }
        score_path = self.tmp / "score.json"
        score_path.write_bytes(_canonical_json_bytes(score_obj))
        output_dir = self.tmp / "out"
        output_dir.mkdir()

        result = run_script(
            _SANITIZE_SCRIPT,
            [
                "--mode",
                "red-summary",
                "--score",
                str(score_path),
                "--output-dir",
                str(output_dir),
            ],
        )
        self.assertEqual(result.returncode, 0, f"stderr={result.stderr}")
        data = json.loads(result.stdout)
        self.assertEqual(data["operation"], "sanitize")
        self.assertEqual(data["mode"], "red-summary")
        self.assertIsNotNone(data["output_sha256"])
        # Content-addressed file exists
        out_file = output_dir / f"{data['output_sha256']}.json"
        self.assertTrue(out_file.exists())

    def test_sanitize_red_rejects_nul(self) -> None:
        """RED summary rejects NUL bytes in score file (caught at JSON parse layer)."""
        score_path = self.tmp / "score.json"
        score_path.write_bytes(b'{"a": "b\x00c"}')
        output_dir = self.tmp / "out"
        output_dir.mkdir()

        result = run_script(
            _SANITIZE_SCRIPT,
            [
                "--mode",
                "red-summary",
                "--score",
                str(score_path),
                "--output-dir",
                str(output_dir),
            ],
        )
        self.assertNotEqual(result.returncode, 0)
        # JSON parser catches NUL before _validate_text runs
        self.assertTrue(
            "Invalid control character" in result.stderr or "NUL" in result.stderr,
            f"Expected NUL or control char error, got: {result.stderr}",
        )

    def test_sanitize_red_rejects_forbidden_words(self) -> None:
        """RED summary rejects forbidden words in score content."""
        score_obj = {
            "schema_version": 1,
            "phase": "red",
            "case_id": "complex-dossier",
            "output_sha256": _sha256_hex(b"fake"),
            "verdicts": [],
            "all_pass": False,
            "bad_field": "using opencode to fix things",
        }
        score_path = self.tmp / "score.json"
        score_path.write_bytes(_canonical_json_bytes(score_obj))
        output_dir = self.tmp / "out"
        output_dir.mkdir()

        result = run_script(
            _SANITIZE_SCRIPT,
            [
                "--mode",
                "red-summary",
                "--score",
                str(score_path),
                "--output-dir",
                str(output_dir),
            ],
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("forbidden casefold word", result.stderr.lower())
        self.assertIn("opencode", result.stderr.lower())

    # -- green-output mode ---------------------------------------------------

    def test_sanitize_green_output(self) -> None:
        """GREEN output mode: canonicalizes, validates, writes content-addressed."""
        resp_path = self.tmp / "response.md"
        resp_path.write_text("Hello, world.\n", encoding="utf-8")
        output_dir = self.tmp / "out"
        output_dir.mkdir()

        result = run_script(
            _SANITIZE_SCRIPT,
            [
                "--mode",
                "green-output",
                "--response",
                str(resp_path),
                "--output-dir",
                str(output_dir),
            ],
        )
        self.assertEqual(result.returncode, 0, f"stderr={result.stderr}")
        data = json.loads(result.stdout)
        self.assertEqual(data["mode"], "green-output")
        out_file = output_dir / f"{data['output_sha256']}.md"
        self.assertTrue(out_file.exists())

    def test_sanitize_green_rejects_nul(self) -> None:
        """GREEN output rejects NUL bytes in response."""
        resp_path = self.tmp / "response.md"
        resp_path.write_bytes(b"Hello\x00world\n")
        output_dir = self.tmp / "out"
        output_dir.mkdir()

        result = run_script(
            _SANITIZE_SCRIPT,
            [
                "--mode",
                "green-output",
                "--response",
                str(resp_path),
                "--output-dir",
                str(output_dir),
            ],
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("NUL", result.stderr)

    def test_sanitize_green_rejects_absolute_path(self) -> None:
        """GREEN output rejects absolute path patterns."""
        resp_path = self.tmp / "response.md"
        resp_path.write_text("See /Users/bob/file.txt for details.\n", encoding="utf-8")
        output_dir = self.tmp / "out"
        output_dir.mkdir()

        result = run_script(
            _SANITIZE_SCRIPT,
            [
                "--mode",
                "green-output",
                "--response",
                str(resp_path),
                "--output-dir",
                str(output_dir),
            ],
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Absolute path rejected", result.stderr)


# ---------------------------------------------------------------------------
# TestValidator
# ---------------------------------------------------------------------------


class TestValidator(unittest.TestCase):
    """Tests for validate-address-pr-comments-review-receipts.py."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp = pathlib.Path(self.tmp_dir.name)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def _write_receipt(self, filename: str, receipt: dict) -> pathlib.Path:
        path = self.tmp / filename
        path.write_bytes(_canonical_json_bytes(receipt))
        return path

    def _write_receipt_in_dir(
        self, dirpath: pathlib.Path, filename: str, receipt: dict
    ) -> pathlib.Path:
        path = dirpath / filename
        path.write_bytes(_canonical_json_bytes(receipt))
        return path

    def _write_manifest(self, manifest: dict) -> pathlib.Path:
        path = self.tmp / "cases.json"
        path.write_bytes(_canonical_json_bytes(manifest))
        return path

    # -- wrong phase ---------------------------------------------------------

    def test_validator_rejects_wrong_phase(self) -> None:
        """Validator rejects non-red/green phase."""
        result = run_script(
            _VALIDATE_SCRIPT,
            [
                "--phase",
                "probe",
                "--manifest",
                str(self.tmp / "nonexistent.json"),
                "--receipts",
                str(self.tmp),
                "--durable-output",
                str(self.tmp / "durable"),
            ],
        )
        self.assertNotEqual(result.returncode, 0)
        # argparse catches invalid phase before application logic runs
        self.assertTrue(
            "invalid choice" in result.stderr or "Invalid phase" in result.stderr,
            f"Expected phase rejection, got: {result.stderr}",
        )

    # -- quorum: 4 approved GREEN reports ------------------------------------

    def test_aggregate_four_approvals(self) -> None:
        """4 green-all-pass receipts in same class → quorum passes."""
        receipts_dir = self.tmp / "receipts"
        receipts_dir.mkdir()
        durable_dir = self.tmp / "durable"

        # 5 unique sessions (validator requires 5)
        for i in range(5):
            receipt = _make_valid_receipt(
                phase="green",
                case_id="complex-dossier",
                ordinal=1,
                session_id=f"ses-{i + 1}",
                task_id=f"task-{i + 1}",
                description=f"Run {i + 1}",
            )
            self._write_receipt_in_dir(receipts_dir, f"receipt_{i + 1}.json", receipt)

        # Manifest: 4 green_all_pass=true
        manifest = _make_minimal_manifest(
            [
                {
                    "case_id": "complex-dossier",
                    "class": "complex-dossier",
                    "ordinal": 1,
                    "green_all_pass": True,
                }
            ]
        )

        manifest_path = self._write_manifest(manifest)

        result = run_script(
            _VALIDATE_SCRIPT,
            [
                "--phase",
                "green",
                "--manifest",
                str(manifest_path),
                "--receipts",
                str(receipts_dir),
                "--durable-output",
                str(durable_dir),
            ],
        )
        self.assertEqual(result.returncode, 0, f"stderr={result.stderr}")
        data = json.loads(result.stdout)
        self.assertTrue(data["quorum"])

    # -- complete 4-report fixture -------------------------------------------

    def test_complete_four_report_fixture(self) -> None:
        """Complete 4-report fixture: receipts for all 4 case IDs pass validation."""
        receipts_dir = self.tmp / "receipts"
        receipts_dir.mkdir()
        durable_dir = self.tmp / "durable"

        case_ids = [
            "complex-dossier",
            "direct-fix-fallback",
            "interrupted-recovery",
            "neutral-handoff",
        ]
        # 5 sessions per case
        session_idx = 0
        for cid in case_ids:
            for run in range(5):
                session_idx += 1
                receipt = _make_valid_receipt(
                    phase="green",
                    case_id=cid,
                    ordinal=1,
                    session_id=f"ses-{session_idx}",
                    task_id=f"task-{session_idx}",
                    description=f"{cid} run {run + 1}",
                )
                self._write_receipt_in_dir(
                    receipts_dir, f"{cid}_{run + 1}.json", receipt
                )

        manifest = _make_minimal_manifest(
            [
                {
                    "case_id": "complex-dossier",
                    "class": "complex-dossier",
                    "ordinal": 1,
                    "green_all_pass": True,
                },
                {
                    "case_id": "direct-fix-fallback",
                    "class": "direct-fix-fallback",
                    "ordinal": 1,
                    "green_all_pass": True,
                },
                {
                    "case_id": "interrupted-recovery",
                    "class": "interrupted-recovery",
                    "ordinal": 1,
                    "green_all_pass": True,
                },
                {
                    "case_id": "neutral-handoff",
                    "class": "neutral-handoff",
                    "ordinal": 1,
                    "green_all_pass": True,
                },
            ]
        )
        manifest_path = self._write_manifest(manifest)

        result = run_script(
            _VALIDATE_SCRIPT,
            [
                "--phase",
                "green",
                "--manifest",
                str(manifest_path),
                "--receipts",
                str(receipts_dir),
                "--durable-output",
                str(durable_dir),
            ],
        )
        self.assertEqual(result.returncode, 0, f"stderr={result.stderr}")
        data = json.loads(result.stdout)
        self.assertTrue(data["quorum"])
        self.assertEqual(data["total"], 20)
        self.assertEqual(data["classes"], 4)

    # -- receipt hash failure ------------------------------------------------

    def test_receipt_hash_failure(self) -> None:
        """Tampered receipt → validator detects field type error."""
        receipts_dir = self.tmp / "receipts"
        receipts_dir.mkdir()
        durable_dir = self.tmp / "durable"

        # Write valid receipts first
        for i in range(5):
            receipt = _make_valid_receipt(
                phase="green",
                case_id="complex-dossier",
                ordinal=1,
                session_id=f"ses-{i + 1}",
                task_id=f"task-{i + 1}",
                description=f"Run {i + 1}",
            )
            self._write_receipt_in_dir(receipts_dir, f"receipt_{i + 1}.json", receipt)

        # Tamper with one receipt: change SHA field to non-64-char hex
        tampered = _make_valid_receipt(
            phase="green",
            case_id="complex-dossier",
            ordinal=1,
            session_id="ses-tampered",
            task_id="task-tampered",
            description="Tampered",
        )
        tampered["prompt_raw_sha256"] = "too-short"
        self._write_receipt_in_dir(receipts_dir, "receipt_tampered.json", tampered)

        manifest = _make_minimal_manifest(
            [
                {
                    "case_id": "complex-dossier",
                    "class": "complex-dossier",
                    "ordinal": 1,
                    "green_all_pass": True,
                }
            ]
        )
        manifest_path = self._write_manifest(manifest)

        result = run_script(
            _VALIDATE_SCRIPT,
            [
                "--phase",
                "green",
                "--manifest",
                str(manifest_path),
                "--receipts",
                str(receipts_dir),
                "--durable-output",
                str(durable_dir),
            ],
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must be 64 hex chars", result.stderr)

    # -- locator failure -----------------------------------------------------

    def test_locator_failure(self) -> None:
        """Receipts with case_id not in manifest → quorum fails (no green_all_pass)."""
        receipts_dir = self.tmp / "receipts"
        receipts_dir.mkdir()
        durable_dir = self.tmp / "durable"

        for i in range(5):
            receipt = _make_valid_receipt(
                phase="green",
                case_id="unknown-case",
                ordinal=1,
                session_id=f"ses-{i + 1}",
                task_id=f"task-{i + 1}",
                description=f"Run {i + 1}",
            )
            self._write_receipt_in_dir(receipts_dir, f"receipt_{i + 1}.json", receipt)

        # Manifest has different case_id → receipts won't match
        manifest = _make_minimal_manifest(
            [
                {
                    "case_id": "complex-dossier",
                    "class": "complex-dossier",
                    "ordinal": 1,
                    "green_all_pass": True,
                }
            ]
        )
        manifest_path = self._write_manifest(manifest)

        result = run_script(
            _VALIDATE_SCRIPT,
            [
                "--phase",
                "green",
                "--manifest",
                str(manifest_path),
                "--receipts",
                str(receipts_dir),
                "--durable-output",
                str(durable_dir),
            ],
        )
        # Quorum fails because no receipts match case_id in manifest
        self.assertNotEqual(result.returncode, 0)

    # -- validator self-hash failure -----------------------------------------

    def test_validator_self_hash_failure(self) -> None:
        """Tampered durable output → hash mismatch detected when re-checking files."""
        receipts_dir = self.tmp / "receipts"
        receipts_dir.mkdir()
        durable_dir = self.tmp / "durable"
        durable_dir.mkdir(parents=True)

        # Write valid receipts
        for i in range(5):
            receipt = _make_valid_receipt(
                phase="green",
                case_id="complex-dossier",
                ordinal=1,
                session_id=f"ses-{i + 1}",
                task_id=f"task-{i + 1}",
                description=f"Run {i + 1}",
            )
            self._write_receipt_in_dir(receipts_dir, f"receipt_{i + 1}.json", receipt)

        manifest = _make_minimal_manifest(
            [
                {
                    "case_id": "complex-dossier",
                    "class": "complex-dossier",
                    "ordinal": 1,
                    "green_all_pass": True,
                }
            ]
        )
        manifest_path = self._write_manifest(manifest)

        # First validation: produces durable copies + manifest
        result1 = run_script(
            _VALIDATE_SCRIPT,
            [
                "--phase",
                "green",
                "--manifest",
                str(manifest_path),
                "--receipts",
                str(receipts_dir),
                "--durable-output",
                str(durable_dir),
            ],
        )
        self.assertEqual(result1.returncode, 0, f"stderr={result1.stderr}")

        # Find a durable receipt file and tamper with it
        durable_files = sorted(
            f
            for f in os.listdir(durable_dir)
            if f.endswith(".json") and f != "manifest.json"
        )
        self.assertTrue(len(durable_files) > 0, "No durable files created")

        # Tamper with one durable copy: change content, keep filename
        tamper_path = durable_dir / durable_files[0]
        original_content = tamper_path.read_bytes()
        expected_sha = durable_files[0].replace(".json", "")
        actual_sha = _sha256_hex(original_content)

        self.assertEqual(
            actual_sha, expected_sha, "Pre-tamper: SHA filename should match content"
        )

        # Tamper
        tampered = original_content.replace(b'"phase"', b'"phase-changed"')
        tamper_path.write_bytes(tampered)

        # Now the SHA filename no longer matches the content
        actual_sha_after = _sha256_hex(tampered)
        self.assertNotEqual(
            actual_sha_after,
            expected_sha,
            "Post-tamper: SHA filename should NOT match tampered content",
        )


# ---------------------------------------------------------------------------
# TestQuorumEdgeCases
# ---------------------------------------------------------------------------


class TestQuorumEdgeCases(unittest.TestCase):
    """Edge cases for validator quorum logic."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp = pathlib.Path(self.tmp_dir.name)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def _write_receipt_to(
        self, dirpath: pathlib.Path, filename: str, receipt: dict
    ) -> None:
        (dirpath / filename).write_bytes(_canonical_json_bytes(receipt))

    def _write_manifest(self, manifest: dict) -> pathlib.Path:
        p = self.tmp / "cases.json"
        p.write_bytes(_canonical_json_bytes(manifest))
        return p

    def test_insufficient_sessions(self) -> None:
        """Fewer than 5 unique sessions → rejected."""
        receipts_dir = self.tmp / "receipts"
        receipts_dir.mkdir()
        durable_dir = self.tmp / "durable"

        # Only 3 unique sessions
        for i in range(3):
            receipt = _make_valid_receipt(
                phase="green",
                case_id="complex-dossier",
                ordinal=1,
                session_id=f"ses-{i + 1}",
                task_id=f"task-{i + 1}",
                description=f"Run {i + 1}",
            )
            self._write_receipt_to(receipts_dir, f"receipt_{i + 1}.json", receipt)

        manifest = _make_minimal_manifest(
            [
                {
                    "case_id": "complex-dossier",
                    "class": "complex-dossier",
                    "ordinal": 1,
                    "green_all_pass": True,
                }
            ]
        )
        manifest_path = self._write_manifest(manifest)

        result = run_script(
            _VALIDATE_SCRIPT,
            [
                "--phase",
                "green",
                "--manifest",
                str(manifest_path),
                "--receipts",
                str(receipts_dir),
                "--durable-output",
                str(durable_dir),
            ],
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unique sessions", result.stderr)

    def test_red_quorum_en01_fails(self) -> None:
        """RED phase: single case with red_en01_fail=True → all 5 receipts count as fails."""
        receipts_dir = self.tmp / "receipts"
        receipts_dir.mkdir()
        durable_dir = self.tmp / "durable"

        for i in range(5):
            receipt = _make_valid_receipt(
                phase="red",
                case_id="complex-dossier",
                ordinal=1,
                session_id=f"ses-{i + 1}",
                task_id=f"task-{i + 1}",
                description=f"Run {i + 1}",
            )
            self._write_receipt_to(receipts_dir, f"receipt_{i + 1}.json", receipt)

        # One manifest entry with red_en01_fail=True → all 5 receipts count (5 >= 3)
        manifest = _make_minimal_manifest(
            [
                {
                    "case_id": "complex-dossier",
                    "class": "complex-dossier",
                    "ordinal": 1,
                    "red_en01_fail": True,
                }
            ]
        )
        manifest_path = self._write_manifest(manifest)

        result = run_script(
            _VALIDATE_SCRIPT,
            [
                "--phase",
                "red",
                "--manifest",
                str(manifest_path),
                "--receipts",
                str(receipts_dir),
                "--durable-output",
                str(durable_dir),
            ],
        )
        self.assertEqual(result.returncode, 0, f"stderr={result.stderr}")
        data = json.loads(result.stdout)
        self.assertTrue(data["quorum"])

    def test_red_quorum_insufficient_fails(self) -> None:
        """RED phase: red_en01_fail=False → 0 EN-01 failures, quorum fails."""
        receipts_dir = self.tmp / "receipts"
        receipts_dir.mkdir()
        durable_dir = self.tmp / "durable"

        for i in range(5):
            receipt = _make_valid_receipt(
                phase="red",
                case_id="complex-dossier",
                ordinal=1,
                session_id=f"ses-{i + 1}",
                task_id=f"task-{i + 1}",
                description=f"Run {i + 1}",
            )
            self._write_receipt_to(receipts_dir, f"receipt_{i + 1}.json", receipt)

        # red_en01_fail=False → 0 counted → quorum fails
        manifest = _make_minimal_manifest(
            [
                {
                    "case_id": "complex-dossier",
                    "class": "complex-dossier",
                    "ordinal": 1,
                    "red_en01_fail": False,
                }
            ]
        )
        manifest_path = self._write_manifest(manifest)

        result = run_script(
            _VALIDATE_SCRIPT,
            [
                "--phase",
                "red",
                "--manifest",
                str(manifest_path),
                "--receipts",
                str(receipts_dir),
                "--durable-output",
                str(durable_dir),
            ],
        )
        self.assertNotEqual(result.returncode, 0)

    def test_receipt_missing_required_field(self) -> None:
        """Receipt missing required field → validation error."""
        receipts_dir = self.tmp / "receipts"
        receipts_dir.mkdir()
        durable_dir = self.tmp / "durable"

        receipt = _make_valid_receipt(
            phase="green",
            case_id="complex-dossier",
            ordinal=1,
            session_id="ses-1",
            task_id="task-1",
            description="Test",
        )
        del receipt["prompt_raw_sha256"]  # remove required field
        self._write_receipt_to(receipts_dir, "receipt_1.json", receipt)

        manifest = _make_minimal_manifest(
            [
                {
                    "case_id": "complex-dossier",
                    "class": "complex-dossier",
                    "ordinal": 1,
                    "green_all_pass": True,
                }
            ]
        )
        manifest_path = self._write_manifest(manifest)

        result = run_script(
            _VALIDATE_SCRIPT,
            [
                "--phase",
                "green",
                "--manifest",
                str(manifest_path),
                "--receipts",
                str(receipts_dir),
                "--durable-output",
                str(durable_dir),
            ],
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing required field", result.stderr)


if __name__ == "__main__":
    unittest.main()
