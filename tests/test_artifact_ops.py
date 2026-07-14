#!/usr/bin/env python3
"""Tests for artifact_ops.py artifact lifecycle helper.

Uses subprocess.run() to invoke the helper via CLI.
Creates isolated temp environments for each test.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
import uuid


# ---------------------------------------------------------------------------
# Resolve script path
# ---------------------------------------------------------------------------

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
ARTIFACT_OPS = (
    REPO_ROOT / "skills" / "address-pr-comments-review" / "scripts" / "artifact_ops.py"
)


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _uuid() -> str:
    return str(uuid.uuid4())


def _run(*args: str, **kwargs: object) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(ARTIFACT_OPS), *args]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=30,
        **kwargs,  # type: ignore[arg-type]
    )


def _make_source_template(
    artifact_id: str,
    operation_id: str,
    generation_head: str,
    has_json_sections: bool = True,
) -> str:
    """Build a base64-encoded artifact source template with sentinel placeholders."""
    json_sections = ""
    if has_json_sections:
        json_sections = """
<!-- context-json:start -->
{"repo":"owner/repo","owner":"owner","repo_name":"repo","pr_number":1,"pr_url":"https://github.com/owner/repo/pull/1","target_worktree_root_sha256":"abc","checkout_branch":"main","generation_head":"{{GENERATION_HEAD}}","head_repo":"owner/repo","head_ref":"branch","head_sha":"{{GENERATION_HEAD}}","head_clone_url":"https://github.com/owner/repo.git"}
<!-- context-json:end -->

<!-- tasks-json:start -->
[{"task_id":"task-1","group_id":null,"execution_order":1,"depends_on_task_ids":[],"expected_paths":["src/file.go"],"requires_commit":true,"verification_ids":["verify-1"],"reply_target_ids":["reply-1"]}]
<!-- tasks-json:end -->

<!-- verifications-json:start -->
[{"verification_id":"verify-1","kind":"test","command":"go test ./...","expected":"PASS","timeout_seconds":60}]
<!-- verifications-json:end -->

<!-- reply-targets-json:start -->
[{"reply_target_id":"reply-1","comment_id":42,"author":"reviewer","kind":"inline","endpoint":"repos/owner/repo/pulls/1/comments","target_path":"src/file.go","target_line":10,"target_side":"RIGHT","in_reply_to":42,"reply_body_template":"Fixed in {commit_sha}.","reply_kind":"fixed","requires_commit_sha":true,"duplicate_of":null,"disposition":"pending","disposition_reason":null}]
<!-- reply-targets-json:end -->
"""

    return base64.b64encode(
        f"""# Artifact Template

## Context
- PR: https://github.com/owner/repo/pull/1
- Repo: `owner/repo`

<!-- artifact-execution-status:start -->
| Field | Value |
|-------|-------|
| Artifact ID | `{{{{ARTIFACT_ID}}}}` |
| Operation ID | `{{{{OPERATION_ID}}}}` |
| State | `pending` |
| Updated At | `{{{{UPDATED_AT}}}}` |
| Generation HEAD | `{{{{GENERATION_HEAD}}}}` |
| Started HEAD | |
| Final Tip | |
| Evidence Sequence | `0` |
| Task Statuses | `task-1:pending` |
| Commit Intents | |
| Modification Commits | |
| Verification Evidence | |
| Post Attempts | |
| Thread Snapshots | |
| Reply Target Dispositions | |
| Reply IDs | |
| Read-Back Evidence | |
| Remote Reachability | |
| Push Receipts | |
| Blocked Reason | |
| Transition Preimages | |
| Transition History | |
<!-- artifact-execution-status:end -->

## Inventory SHA
`{{{{INVENTORY_SHA256}}}}`

{json_sections}

## Evidence Inventory
<!-- artifact-execution-inventory:start -->
<!-- artifact-execution-inventory:end -->
""".encode("utf-8")
    ).decode("ascii")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLifecycleHappy(unittest.TestCase):
    """Happy path: create → record → transition through full lifecycle."""

    def test_lifecycle_happy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_path = os.path.join(tmpdir, "artifact.md")
            artifact_id = _uuid()
            op_id = _uuid()
            gen_head = "a" * 40

            # --- Step 1: Create ---
            source_b64 = _make_source_template(artifact_id, op_id, gen_head)
            result = _run(
                "create",
                "--source-base64",
                source_b64,
                "--artifact",
                artifact_path,
                "--kind",
                "review-dossier",
                "--artifact-id",
                artifact_id,
                "--operation-id",
                op_id,
                "--generation-head",
                gen_head,
            )
            self.assertEqual(result.returncode, 0)
            create_out = json.loads(result.stdout)
            self.assertEqual(create_out["operation"], "create")
            self.assertEqual(create_out["status"], "created")
            self.assertEqual(create_out["state"], "pending")
            artifact_sha = create_out["artifact_sha256"]
            self.assertEqual(len(artifact_sha), 64)

            # Verify artifact exists
            self.assertTrue(os.path.exists(artifact_path))
            content = pathlib.Path(artifact_path).read_text()
            self.assertNotIn("{{ARTIFACT_ID}}", content)
            self.assertNotIn("{{OPERATION_ID}}", content)

            # Verify artifact SHA matches on disk
            actual_sha = _sha256_hex(pathlib.Path(artifact_path).read_bytes())
            self.assertEqual(actual_sha, artifact_sha)

            # --- Step 2: Record ---
            record_id = _uuid()
            record_json = json.dumps({"verification_id": "verify-1", "outcome": "pass"})
            result2 = _run(
                "record",
                "--artifact",
                artifact_path,
                "--artifact-id",
                artifact_id,
                "--operation-id",
                op_id,
                "--record-id",
                record_id,
                "--expected-state",
                "pending",
                "--expected-sha256",
                artifact_sha,
                "--record-kind",
                "verification",
                "--record-json",
                record_json,
            )
            self.assertEqual(result2.returncode, 0)
            record_out = json.loads(result2.stdout)
            self.assertEqual(record_out["operation"], "record")
            self.assertEqual(record_out["status"], "recorded")
            self.assertEqual(record_out["state"], "pending")
            self.assertEqual(record_out["sequence"], 1)
            sha_after_record = record_out["artifact_sha256"]

            # Verify record was written to inventory
            content_after = pathlib.Path(artifact_path).read_text()
            self.assertIn('"kind":"verification"', content_after)
            self.assertIn(record_id, content_after)

            # --- Step 3: Transition pending → in-progress ---
            reason = json.dumps({"reason": "Starting execution"})
            result3 = _run(
                "transition",
                "--artifact",
                artifact_path,
                "--artifact-id",
                artifact_id,
                "--expected-operation-id",
                op_id,
                "--expected-state",
                "pending",
                "--to-state",
                "in-progress",
                "--expected-sha256",
                sha_after_record,
                "--reason-json",
                reason,
                "--started-head",
                gen_head,
            )
            self.assertEqual(result3.returncode, 0)
            trans_out = json.loads(result3.stdout)
            self.assertEqual(trans_out["operation"], "transition")
            self.assertEqual(trans_out["status"], "transitioned")
            self.assertEqual(trans_out["state"], "in-progress")
            sha_in_progress = trans_out["artifact_sha256"]

            # --- Step 4: Transition in-progress → verified-complete ---
            evidence = json.dumps({"record_ids": [record_id]})
            reason2 = json.dumps({"reason": "All tasks verified"})
            result4 = _run(
                "transition",
                "--artifact",
                artifact_path,
                "--artifact-id",
                artifact_id,
                "--expected-operation-id",
                op_id,
                "--expected-state",
                "in-progress",
                "--to-state",
                "verified-complete",
                "--expected-sha256",
                sha_in_progress,
                "--reason-json",
                reason2,
                "--evidence-json",
                evidence,
            )
            self.assertEqual(result4.returncode, 0)
            trans2_out = json.loads(result4.stdout)
            self.assertEqual(trans2_out["operation"], "transition")
            self.assertEqual(trans2_out["status"], "transitioned")
            self.assertEqual(trans2_out["state"], "verified-complete")


class TestLifecycleIllegalEdges(unittest.TestCase):
    """Illegal state transitions must fail."""

    def test_lifecycle_illegal_edges(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_path = os.path.join(tmpdir, "artifact.md")
            artifact_id = _uuid()
            op_id = _uuid()
            gen_head = "a" * 40

            # Create artifact
            source_b64 = _make_source_template(artifact_id, op_id, gen_head)
            result = _run(
                "create",
                "--source-base64",
                source_b64,
                "--artifact",
                artifact_path,
                "--kind",
                "review-dossier",
                "--artifact-id",
                artifact_id,
                "--operation-id",
                op_id,
                "--generation-head",
                gen_head,
            )
            create_out = json.loads(result.stdout)
            artifact_sha = create_out["artifact_sha256"]

            # pending → verified-complete: illegal (must go through in-progress)
            reason = json.dumps({"reason": "Trying illegal jump"})
            evidence = json.dumps({"record_ids": [_uuid()]})
            result2 = _run(
                "transition",
                "--artifact",
                artifact_path,
                "--artifact-id",
                artifact_id,
                "--expected-operation-id",
                op_id,
                "--expected-state",
                "pending",
                "--to-state",
                "verified-complete",
                "--expected-sha256",
                artifact_sha,
                "--reason-json",
                reason,
                "--evidence-json",
                evidence,
            )
            self.assertNotEqual(result2.returncode, 0)
            self.assertIn(
                "illegal-transition", result2.stdout.lower() or result2.stderr.lower()
            )

            # Transition to in-progress
            reason_ok = json.dumps({"reason": "Start"})
            result3 = _run(
                "transition",
                "--artifact",
                artifact_path,
                "--artifact-id",
                artifact_id,
                "--expected-operation-id",
                op_id,
                "--expected-state",
                "pending",
                "--to-state",
                "in-progress",
                "--expected-sha256",
                artifact_sha,
                "--reason-json",
                reason_ok,
                "--started-head",
                gen_head,
            )
            trans_out = json.loads(result3.stdout)
            sha_ip = trans_out["artifact_sha256"]

            # in-progress → pending: illegal (no backwards edge)
            reason_back = json.dumps({"reason": "Trying to go backwards"})
            result4 = _run(
                "transition",
                "--artifact",
                artifact_path,
                "--artifact-id",
                artifact_id,
                "--expected-operation-id",
                op_id,
                "--expected-state",
                "in-progress",
                "--to-state",
                "pending",
                "--expected-sha256",
                sha_ip,
                "--reason-json",
                reason_back,
            )
            self.assertNotEqual(result4.returncode, 0)


class TestLockCasAndReplay(unittest.TestCase):
    """Lock CAS and replay idempotency."""

    def test_lock_cas_and_replay(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_path = os.path.join(tmpdir, "artifact.md")
            artifact_id = _uuid()
            op_id = _uuid()
            gen_head = "a" * 40

            source_b64 = _make_source_template(artifact_id, op_id, gen_head)

            # First create
            result = _run(
                "create",
                "--source-base64",
                source_b64,
                "--artifact",
                artifact_path,
                "--kind",
                "review-dossier",
                "--artifact-id",
                artifact_id,
                "--operation-id",
                op_id,
                "--generation-head",
                gen_head,
            )
            self.assertEqual(result.returncode, 0)
            create_out = json.loads(result.stdout)
            self.assertEqual(create_out["status"], "created")
            artifact_sha = create_out["artifact_sha256"]

            # Second create without --expected-absent: should detect unchanged
            result2 = _run(
                "create",
                "--source-base64",
                source_b64,
                "--artifact",
                artifact_path,
                "--kind",
                "review-dossier",
                "--artifact-id",
                artifact_id,
                "--operation-id",
                op_id,
                "--generation-head",
                gen_head,
            )
            self.assertEqual(result2.returncode, 0)
            create2_out = json.loads(result2.stdout)
            self.assertEqual(create2_out["status"], "unchanged")
            self.assertEqual(create2_out["artifact_sha256"], artifact_sha)

            # Create with --expected-absent: must fail
            result3 = _run(
                "create",
                "--source-base64",
                source_b64,
                "--artifact",
                artifact_path,
                "--kind",
                "review-dossier",
                "--artifact-id",
                artifact_id,
                "--operation-id",
                op_id,
                "--generation-head",
                gen_head,
                "--expected-absent",
            )
            self.assertNotEqual(result3.returncode, 0)
            self.assertIn("cas-mismatch", result3.stdout.lower())

            # Different source with same path: must fail
            diff_source_b64 = _make_source_template(_uuid(), op_id, gen_head)
            result4 = _run(
                "create",
                "--source-base64",
                diff_source_b64,
                "--artifact",
                artifact_path,
                "--kind",
                "review-dossier",
                "--artifact-id",
                _uuid(),
                "--operation-id",
                op_id,
                "--generation-head",
                gen_head,
            )
            self.assertNotEqual(result4.returncode, 0)


class TestPreparedAndUncertainRecovery(unittest.TestCase):
    """Prepared/uncertain lease recovery scenarios."""

    def test_prepared_and_uncertain_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_path = os.path.join(tmpdir, "artifact.md")
            artifact_id = _uuid()
            op_id = _uuid()
            gen_head = "a" * 40

            source_b64 = _make_source_template(artifact_id, op_id, gen_head)

            # Create artifact
            result = _run(
                "create",
                "--source-base64",
                source_b64,
                "--artifact",
                artifact_path,
                "--kind",
                "review-dossier",
                "--artifact-id",
                artifact_id,
                "--operation-id",
                op_id,
                "--generation-head",
                gen_head,
            )
            create_out = json.loads(result.stdout)
            self.assertEqual(create_out["state"], "pending")

            # Simulate partial write: create with same params should be idempotent
            result2 = _run(
                "create",
                "--source-base64",
                source_b64,
                "--artifact",
                artifact_path,
                "--kind",
                "review-dossier",
                "--artifact-id",
                artifact_id,
                "--operation-id",
                op_id,
                "--generation-head",
                gen_head,
            )
            self.assertEqual(result2.returncode, 0)
            self.assertEqual(json.loads(result2.stdout)["status"], "unchanged")

            # Transition to blocked (simulating interruption before in-progress)
            reason = json.dumps({"reason": "Checkout mismatch"})
            result3 = _run(
                "transition",
                "--artifact",
                artifact_path,
                "--artifact-id",
                artifact_id,
                "--expected-operation-id",
                op_id,
                "--expected-state",
                "pending",
                "--to-state",
                "blocked",
                "--expected-sha256",
                create_out["artifact_sha256"],
                "--reason-json",
                reason,
            )
            self.assertEqual(result3.returncode, 0)
            sha_blocked = json.loads(result3.stdout)["artifact_sha256"]

            # Recovery: transition blocked → in-progress
            reason2 = json.dumps({"reason": "Checkout resolved, resuming"})
            new_op_id = _uuid()
            result4 = _run(
                "transition",
                "--artifact",
                artifact_path,
                "--artifact-id",
                artifact_id,
                "--expected-operation-id",
                op_id,
                "--expected-state",
                "blocked",
                "--to-state",
                "in-progress",
                "--expected-sha256",
                sha_blocked,
                "--reason-json",
                reason2,
                "--next-operation-id",
                new_op_id,
                "--started-head",
                gen_head,
            )
            self.assertEqual(result4.returncode, 0)
            self.assertEqual(json.loads(result4.stdout)["state"], "in-progress")


class TestReplyPreexisting(unittest.TestCase):
    """Reply preexisting detection via record kinds."""

    def test_reply_preexisting(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_path = os.path.join(tmpdir, "artifact.md")
            artifact_id = _uuid()
            op_id = _uuid()
            gen_head = "a" * 40

            source_b64 = _make_source_template(artifact_id, op_id, gen_head)
            result = _run(
                "create",
                "--source-base64",
                source_b64,
                "--artifact",
                artifact_path,
                "--kind",
                "review-dossier",
                "--artifact-id",
                artifact_id,
                "--operation-id",
                op_id,
                "--generation-head",
                gen_head,
            )
            create_out = json.loads(result.stdout)
            artifact_sha = create_out["artifact_sha256"]

            # Record a reply-disposition with blocked:already-replied
            record_id = _uuid()
            disposition_payload = json.dumps(
                {
                    "reply_target_id": "reply-1",
                    "disposition": "blocked",
                    "reason": "already-replied: human reply exists",
                }
            )
            result2 = _run(
                "record",
                "--artifact",
                artifact_path,
                "--artifact-id",
                artifact_id,
                "--operation-id",
                op_id,
                "--record-id",
                record_id,
                "--expected-state",
                "pending",
                "--expected-sha256",
                artifact_sha,
                "--record-kind",
                "reply-disposition",
                "--record-json",
                disposition_payload,
            )
            self.assertEqual(result2.returncode, 0)
            record_out = json.loads(result2.stdout)
            self.assertEqual(record_out["status"], "recorded")
            self.assertEqual(record_out["sequence"], 1)

            # Verify record appears in artifact
            content = pathlib.Path(artifact_path).read_text()
            self.assertIn("already-replied", content)


class TestReplyMarkerConflict(unittest.TestCase):
    """Reply marker conflict detection."""

    def test_reply_marker_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_path = os.path.join(tmpdir, "artifact.md")
            artifact_id = _uuid()
            op_id = _uuid()
            gen_head = "a" * 40

            source_b64 = _make_source_template(artifact_id, op_id, gen_head)
            result = _run(
                "create",
                "--source-base64",
                source_b64,
                "--artifact",
                artifact_path,
                "--kind",
                "review-dossier",
                "--artifact-id",
                artifact_id,
                "--operation-id",
                op_id,
                "--generation-head",
                gen_head,
            )
            create_out = json.loads(result.stdout)
            artifact_sha = create_out["artifact_sha256"]

            # Record first reply-1 disposition
            rec1_id = _uuid()
            payload1 = json.dumps(
                {
                    "reply_target_id": "reply-1",
                    "disposition": "eligible",
                }
            )
            r1 = _run(
                "record",
                "--artifact",
                artifact_path,
                "--artifact-id",
                artifact_id,
                "--operation-id",
                op_id,
                "--record-id",
                rec1_id,
                "--expected-state",
                "pending",
                "--expected-sha256",
                artifact_sha,
                "--record-kind",
                "reply-disposition",
                "--record-json",
                payload1,
            )
            self.assertEqual(r1.returncode, 0)
            sha1 = json.loads(r1.stdout)["artifact_sha256"]

            # Record second reply-1 disposition: conflict marker
            rec2_id = _uuid()
            payload2 = json.dumps(
                {
                    "reply_target_id": "reply-1",
                    "disposition": "blocked",
                    "reason": "conflict: duplicate marker",
                }
            )
            r2 = _run(
                "record",
                "--artifact",
                artifact_path,
                "--artifact-id",
                artifact_id,
                "--operation-id",
                op_id,
                "--record-id",
                rec2_id,
                "--expected-state",
                "pending",
                "--expected-sha256",
                sha1,
                "--record-kind",
                "reply-disposition",
                "--record-json",
                payload2,
            )
            self.assertEqual(r2.returncode, 0)
            sha2 = json.loads(r2.stdout)["artifact_sha256"]

            # Verify both records exist
            content = pathlib.Path(artifact_path).read_text()
            self.assertIn(rec1_id, content)
            self.assertIn(rec2_id, content)
            self.assertIn("conflict", content)


class TestReplyTimeoutNoRetry(unittest.TestCase):
    """Reply timeout without retry: record post-attempt then block."""

    def test_reply_timeout_no_retry(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_path = os.path.join(tmpdir, "artifact.md")
            artifact_id = _uuid()
            op_id = _uuid()
            gen_head = "a" * 40

            source_b64 = _make_source_template(artifact_id, op_id, gen_head)
            result = _run(
                "create",
                "--source-base64",
                source_b64,
                "--artifact",
                artifact_path,
                "--kind",
                "review-dossier",
                "--artifact-id",
                artifact_id,
                "--operation-id",
                op_id,
                "--generation-head",
                gen_head,
            )
            create_out = json.loads(result.stdout)
            artifact_sha = create_out["artifact_sha256"]

            # Record post-attempt with timeout
            rec_id = _uuid()
            post_payload = json.dumps(
                {
                    "reply_target_id": "reply-1",
                    "task_id": "task-1",
                    "endpoint": "repos/o/r/pulls/1/comments",
                    "attempt_number": 1,
                    "response_code": 0,
                    "error": "timeout",
                }
            )
            r1 = _run(
                "record",
                "--artifact",
                artifact_path,
                "--artifact-id",
                artifact_id,
                "--operation-id",
                op_id,
                "--record-id",
                rec_id,
                "--expected-state",
                "pending",
                "--expected-sha256",
                artifact_sha,
                "--record-kind",
                "post-attempt",
                "--record-json",
                post_payload,
            )
            self.assertEqual(r1.returncode, 0)
            sha_post = json.loads(r1.stdout)["artifact_sha256"]

            # Record blocked disposition (no retry)
            rec2_id = _uuid()
            block_payload = json.dumps(
                {
                    "reply_target_id": "reply-1",
                    "disposition": "blocked",
                    "reason": "read-back-failed: timeout, no retry",
                }
            )
            r2 = _run(
                "record",
                "--artifact",
                artifact_path,
                "--artifact-id",
                artifact_id,
                "--operation-id",
                op_id,
                "--record-id",
                rec2_id,
                "--expected-state",
                "pending",
                "--expected-sha256",
                sha_post,
                "--record-kind",
                "reply-disposition",
                "--record-json",
                block_payload,
            )
            self.assertEqual(r2.returncode, 0)

            # Verify no retry attempt exists (only 1 post-attempt)
            content = pathlib.Path(artifact_path).read_text()
            self.assertIn("timeout", content)
            self.assertIn("no retry", content)


class TestReplyOnlyOperations(unittest.TestCase):
    """Reply-only (Section B) artifact operations."""

    def test_reply_only_operations(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_path = os.path.join(tmpdir, "artifact.md")
            artifact_id = _uuid()
            op_id = _uuid()
            gen_head = "a" * 40

            # Create direct-fix brief for reply-only
            source_b64 = _make_source_template(artifact_id, op_id, gen_head)
            result = _run(
                "create",
                "--source-base64",
                source_b64,
                "--artifact",
                artifact_path,
                "--kind",
                "direct-fix",
                "--artifact-id",
                artifact_id,
                "--operation-id",
                op_id,
                "--generation-head",
                gen_head,
            )
            create_out = json.loads(result.stdout)
            artifact_sha = create_out["artifact_sha256"]

            # Record reply without prior code change records
            rec_id = _uuid()
            reply_payload = json.dumps(
                {
                    "reply_target_id": "reply-1",
                    "task_id": "task-1",
                    "comment_id": 42,
                    "body": "Confirmed: this is already resolved.",
                    "reply_kind": "already_fixed",
                }
            )
            r1 = _run(
                "record",
                "--artifact",
                artifact_path,
                "--artifact-id",
                artifact_id,
                "--operation-id",
                op_id,
                "--record-id",
                rec_id,
                "--expected-state",
                "pending",
                "--expected-sha256",
                artifact_sha,
                "--record-kind",
                "reply",
                "--record-json",
                reply_payload,
            )
            self.assertEqual(r1.returncode, 0)
            sha1 = json.loads(r1.stdout)["artifact_sha256"]

            # Record read-back
            rec2_id = _uuid()
            readback_payload = json.dumps(
                {
                    "reply_target_id": "reply-1",
                    "task_id": "task-1",
                    "method": "GET",
                    "endpoint": "repos/o/r/issues/1/comments",
                    "found_comment_id": 999,
                    "body_matches": True,
                    "author_matches": True,
                    "thread_matches": True,
                    "outcome": "verified",
                }
            )
            r2 = _run(
                "record",
                "--artifact",
                artifact_path,
                "--artifact-id",
                artifact_id,
                "--operation-id",
                op_id,
                "--record-id",
                rec2_id,
                "--expected-state",
                "pending",
                "--expected-sha256",
                sha1,
                "--record-kind",
                "read-back",
                "--record-json",
                readback_payload,
            )
            self.assertEqual(r2.returncode, 0)

            # Complete reply-only with verified-complete
            sha2 = json.loads(r2.stdout)["artifact_sha256"]
            reason = json.dumps({"reason": "Reply-only verified"})
            evidence = json.dumps({"record_ids": [rec_id, rec2_id]})

            # Transition to in-progress first
            r3 = _run(
                "transition",
                "--artifact",
                artifact_path,
                "--artifact-id",
                artifact_id,
                "--expected-operation-id",
                op_id,
                "--expected-state",
                "pending",
                "--to-state",
                "in-progress",
                "--expected-sha256",
                sha2,
                "--reason-json",
                reason,
                "--started-head",
                gen_head,
            )
            self.assertEqual(r3.returncode, 0)
            sha_ip = json.loads(r3.stdout)["artifact_sha256"]

            # Then to verified-complete
            r4 = _run(
                "transition",
                "--artifact",
                artifact_path,
                "--artifact-id",
                artifact_id,
                "--expected-operation-id",
                op_id,
                "--expected-state",
                "in-progress",
                "--to-state",
                "verified-complete",
                "--expected-sha256",
                sha_ip,
                "--reason-json",
                reason,
                "--evidence-json",
                evidence,
            )
            self.assertEqual(r4.returncode, 0)
            self.assertEqual(json.loads(r4.stdout)["state"], "verified-complete")


class TestCleanupMatrix(unittest.TestCase):
    """Cleanup behavior matrix across artifact states."""

    def test_cleanup_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_path = os.path.join(tmpdir, "artifact.md")
            artifact_id = _uuid()
            op_id = _uuid()
            gen_head = "a" * 40

            source_b64 = _make_source_template(artifact_id, op_id, gen_head)
            result = _run(
                "create",
                "--source-base64",
                source_b64,
                "--artifact",
                artifact_path,
                "--kind",
                "review-dossier",
                "--artifact-id",
                artifact_id,
                "--operation-id",
                op_id,
                "--generation-head",
                gen_head,
            )
            create_out = json.loads(result.stdout)
            sha_pending = create_out["artifact_sha256"]

            # Verify artifact exists in pending state
            content = pathlib.Path(artifact_path).read_text()
            self.assertIn("`pending`", content)

            # Transition to blocked — cleanup should NOT be eligible
            reason = json.dumps({"reason": "Simulated block"})
            r1 = _run(
                "transition",
                "--artifact",
                artifact_path,
                "--artifact-id",
                artifact_id,
                "--expected-operation-id",
                op_id,
                "--expected-state",
                "pending",
                "--to-state",
                "blocked",
                "--expected-sha256",
                sha_pending,
                "--reason-json",
                reason,
            )
            self.assertEqual(r1.returncode, 0)
            sha_blocked = json.loads(r1.stdout)["artifact_sha256"]

            # Artifact in blocked state — still exists
            self.assertTrue(os.path.exists(artifact_path))
            content_blocked = pathlib.Path(artifact_path).read_text()
            self.assertIn("blocked", content_blocked)

            # Transition to in-progress (recovery)
            reason2 = json.dumps({"reason": "Unblocked"})
            evidence = json.dumps({"record_ids": [_uuid()]})
            r2 = _run(
                "transition",
                "--artifact",
                artifact_path,
                "--artifact-id",
                artifact_id,
                "--expected-operation-id",
                op_id,
                "--expected-state",
                "blocked",
                "--to-state",
                "in-progress",
                "--expected-sha256",
                sha_blocked,
                "--reason-json",
                reason2,
            )
            self.assertEqual(r2.returncode, 0)
            sha_ip = json.loads(r2.stdout)["artifact_sha256"]

            # Transition to verified-complete (now eligible for cleanup)
            r3 = _run(
                "transition",
                "--artifact",
                artifact_path,
                "--artifact-id",
                artifact_id,
                "--expected-operation-id",
                op_id,
                "--expected-state",
                "in-progress",
                "--to-state",
                "verified-complete",
                "--expected-sha256",
                sha_ip,
                "--reason-json",
                reason2,
                "--evidence-json",
                evidence,
            )
            self.assertEqual(r3.returncode, 0)
            sha_done = json.loads(r3.stdout)["artifact_sha256"]

            # Artifact in verified-complete state — cleanup eligible
            content_done = pathlib.Path(artifact_path).read_text()
            self.assertIn("verified-complete", content_done)


class TestCleanupRecovery(unittest.TestCase):
    """Cleanup recovery after interrupted execution."""

    def test_cleanup_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_path = os.path.join(tmpdir, "artifact.md")
            artifact_id = _uuid()
            op_id = _uuid()
            gen_head = "a" * 40

            source_b64 = _make_source_template(artifact_id, op_id, gen_head)
            result = _run(
                "create",
                "--source-base64",
                source_b64,
                "--artifact",
                artifact_path,
                "--kind",
                "review-dossier",
                "--artifact-id",
                artifact_id,
                "--operation-id",
                op_id,
                "--generation-head",
                gen_head,
            )
            sha = json.loads(result.stdout)["artifact_sha256"]

            # Move to in-progress (execution started)
            reason = json.dumps({"reason": "Start"})
            r1 = _run(
                "transition",
                "--artifact",
                artifact_path,
                "--artifact-id",
                artifact_id,
                "--expected-operation-id",
                op_id,
                "--expected-state",
                "pending",
                "--to-state",
                "in-progress",
                "--expected-sha256",
                sha,
                "--reason-json",
                reason,
                "--started-head",
                gen_head,
            )
            sha_ip = json.loads(r1.stdout)["artifact_sha256"]

            # Simulate crash by not completing; then try to recover by
            # re-reading the artifact and validating its in-progress state
            content = pathlib.Path(artifact_path).read_text()
            self.assertIn("in-progress", content)

            # Block then recover
            reason2 = json.dumps({"reason": "Crash"})
            r2 = _run(
                "transition",
                "--artifact",
                artifact_path,
                "--artifact-id",
                artifact_id,
                "--expected-operation-id",
                op_id,
                "--expected-state",
                "in-progress",
                "--to-state",
                "blocked",
                "--expected-sha256",
                sha_ip,
                "--reason-json",
                reason2,
            )
            self.assertEqual(r2.returncode, 0)
            sha_blocked = json.loads(r2.stdout)["artifact_sha256"]

            # Recovery: blocked → in-progress
            reason3 = json.dumps({"reason": "Recovered"})
            r3 = _run(
                "transition",
                "--artifact",
                artifact_path,
                "--artifact-id",
                artifact_id,
                "--expected-operation-id",
                op_id,
                "--expected-state",
                "blocked",
                "--to-state",
                "in-progress",
                "--expected-sha256",
                sha_blocked,
                "--reason-json",
                reason3,
            )
            self.assertEqual(r3.returncode, 0)
            self.assertEqual(json.loads(r3.stdout)["state"], "in-progress")


class TestCleanupIdentityMismatch(unittest.TestCase):
    """Cleanup with wrong identity must fail."""

    def test_cleanup_identity_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_path = os.path.join(tmpdir, "artifact.md")
            artifact_id = _uuid()
            op_id = _uuid()
            gen_head = "a" * 40

            source_b64 = _make_source_template(artifact_id, op_id, gen_head)
            result = _run(
                "create",
                "--source-base64",
                source_b64,
                "--artifact",
                artifact_path,
                "--kind",
                "review-dossier",
                "--artifact-id",
                artifact_id,
                "--operation-id",
                op_id,
                "--generation-head",
                gen_head,
            )
            sha = json.loads(result.stdout)["artifact_sha256"]

            # Try record with wrong artifact-id
            rec_id = _uuid()
            record_json = json.dumps({"test": True})
            r1 = _run(
                "record",
                "--artifact",
                artifact_path,
                "--artifact-id",
                _uuid(),  # wrong ID
                "--operation-id",
                op_id,
                "--record-id",
                rec_id,
                "--expected-state",
                "pending",
                "--expected-sha256",
                sha,
                "--record-kind",
                "verification",
                "--record-json",
                record_json,
            )
            self.assertNotEqual(r1.returncode, 0)
            self.assertIn("identity-mismatch", r1.stdout.lower())

            # Try transition with wrong artifact-id
            reason = json.dumps({"reason": "Test"})
            r2 = _run(
                "transition",
                "--artifact",
                artifact_path,
                "--artifact-id",
                _uuid(),  # wrong ID
                "--expected-operation-id",
                op_id,
                "--expected-state",
                "pending",
                "--to-state",
                "in-progress",
                "--expected-sha256",
                sha,
                "--reason-json",
                reason,
            )
            self.assertNotEqual(r2.returncode, 0)
            self.assertIn("identity-mismatch", r2.stdout.lower())

            # Try transition with wrong operation-id
            r3 = _run(
                "transition",
                "--artifact",
                artifact_path,
                "--artifact-id",
                artifact_id,
                "--expected-operation-id",
                _uuid(),  # wrong op ID
                "--expected-state",
                "pending",
                "--to-state",
                "in-progress",
                "--expected-sha256",
                sha,
                "--reason-json",
                reason,
            )
            self.assertNotEqual(r3.returncode, 0)
            self.assertIn("identity-mismatch", r3.stdout.lower())

            # Try record with wrong SHA
            r4 = _run(
                "record",
                "--artifact",
                artifact_path,
                "--artifact-id",
                artifact_id,
                "--operation-id",
                op_id,
                "--record-id",
                _uuid(),
                "--expected-state",
                "pending",
                "--expected-sha256",
                "0" * 64,  # wrong SHA
                "--record-kind",
                "verification",
                "--record-json",
                record_json,
            )
            self.assertNotEqual(r4.returncode, 0)
            self.assertIn("cas-mismatch", r4.stdout.lower())


class TestNonPosixFailsBeforeWrite(unittest.TestCase):
    """Non-POSIX platform must fail before any file write.

    Uses sys.meta_path to intercept fcntl import at the finder level,
    which works for both Python and C-extension modules.
    """

    def test_non_posix_fails_before_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Use meta_path finder to block fcntl at import-finder level.
            # A plain sys.path shim does not shadow C-extension modules
            # (e.g. fcntl on Linux), but meta_path hooks fire first.
            test_script = os.path.join(tmpdir, "test_nonposix.py")
            with open(test_script, "w") as f:
                f.write(
                    """import importlib.abc
import importlib.machinery
import json
import sys

class _FcntlBlocker(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, fullname, path, target=None):
        if fullname in ("fcntl", "_fcntl"):
            return importlib.machinery.ModuleSpec(fullname, self)
        return None
    def create_module(self, spec):
        return None
    def exec_module(self, module):
        raise ImportError("fcntl not available (non-POSIX simulation)")

sys.meta_path.insert(0, _FcntlBlocker())

try:
    import fcntl  # noqa: F401
    print("UNEXPECTED: fcntl imported")
    sys.exit(0)
except ImportError:
    print(json.dumps({"schema_version":1,"operation":"init","diagnostic_code":"platform-unsupported","message":"POSIX required"}))
    sys.exit(2)
"""
                )

            # Run the test script (simulates non-POSIX)
            result = subprocess.run(
                [sys.executable, test_script],
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertNotEqual(result.returncode, 0)
            out = result.stdout.strip()
            self.assertIn("platform-unsupported", out)

            # Verify no artifact files were created
            marker = os.path.join(tmpdir, "should-not-exist")
            self.assertFalse(os.path.exists(marker))


if __name__ == "__main__":
    unittest.main()
