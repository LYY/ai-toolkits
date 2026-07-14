# Executor-Neutral Evaluation Results

> address-pr-comments-review skill — behavioral acceptance evaluation
> Attempt ID: `678a49cb-f4e9-4d72-9d53-f1730d607103`

## Frozen Inputs

| Input | SHA-256 |
|-------|---------|
| `cases.json` (manifest) | (pending — from Task 3) |
| `case-ids.txt` (canonical) | (pending — from Task 3) |
| `final-criteria.json` | (pending — from Task 3) |
| `eval-matrix.md` (source) | (pending — reference freeze) |

## RED Baseline

| # | Case ID | Expected Exit | Expected Diagnostic | Status |
|---|---------|--------------|---------------------|--------|
| 1 | `route-review-dossier` | 0 | — | Pending |
| 2 | `route-direct-fix` | 0 | — | Pending |
| 3 | `route-reply-only` | 0 | — | Pending |
| 4 | `route-no-action` | 0 | — | Pending |
| 5 | `checkout-mismatch` | 0 | — | Pending |
| 6 | `stale-evidence` | 2 | — | Pending |
| 7 | `dirty-target` | 0 | — | Pending |
| 8 | `index-nonempty` | 2 | — | Pending |
| 9 | `lifecycle-legal` | 2 | — | Pending |
| 10 | `lifecycle-illegal` | 2 | `illegal-transition` | Pending |
| 11 | `lifecycle-status-write-failure` | 4 | `io-error` | Pending |
| 12 | `lifecycle-lock-cas` | 3 | `cas-mismatch` | Pending |
| 13 | `commit-parent-path` | 0 | — | Pending |
| 14 | `commit-fork-remote` | 0 | — | Pending |
| 15 | `commit-push-resume` | 2 | — | Pending |
| 16 | `reply-preexisting` | 2 | — | Pending |
| 17 | `reply-marker-conflict` | 2 | — | Pending |
| 18 | `reply-ambiguous` | 2 | — | Pending |
| 19 | `cleanup-matrix` | 0 | — | Pending |
| 20 | `cleanup-recovery` | 0 | — | Pending |

**RED Summary**: All 20 cases expected to produce correct exit codes and diagnostic codes in baseline runs. Happy-path cases (exit 0): routes, create operations. Error cases (exit 2/3/4): transition failures, CAS mismatches, IO errors.

## GREEN Evaluation (Executor-Neutral Behavioral)

**Date**: 2026-07-14
**Sessions**: 20 (4 classes × 5 ordinals)
**Evidence**: `docs/address-pr-comments-review/eval-evidence/green/`

### GREEN Behavioral Results

| Criterion | EN-01 (No Runtime Terms) | EN-03 (Section A Order) | EN-04 (Recovery) | Overall |
|-----------|--------------------------|-------------------------|-------------------|---------|
| complex-dossier (5 ordinals) | 0/5 PASS | 5/5 PASS | 5/5 PASS | **0/5** |
| direct-fix-fallback (5 ordinals) | 0/5 PASS | 5/5 PASS | 5/5 PASS | **0/5** |
| interrupted-recovery (5 ordinals) | 0/5 PASS | 5/5 PASS | 5/5 PASS | **0/5** |
| neutral-handoff (5 ordinals) | 0/5 PASS | 5/5 PASS | 5/5 PASS | **0/5** |
| **Total** | **0/20 PASS** | **20/20 PASS** | **20/20 PASS** | **0/20** |

### Root Cause

All 20 agents independently identified runtime-specific terms in the skill files:

| Term | Occurrences (out of 20) | Source |
|------|------------------------|--------|
| OpenCode | 20/20 | `execution.md` line 3 |
| OhMyOpenCode | 20/20 | `execution.md` line 3 |
| Sisyphus | 20/20 | `execution.md` line 3 |
| Prometheus | 20/20 | `execution.md` handoff section |
| OMO | 19/20 | `execution.md` lines 3, 222, 258 |

**Affected file**: skills/address-pr-comments-review/references/execution.md, line 3:
> Platform lock: OpenCode + OhMyOpenCode (Sisyphus) only.

This violates executor-neutral requirement EN-01. The SKILL.md itself is clean; only `execution.md` contains platform-specific references.

### What Passed (confirmed executor-neutral)

| Aspect | Result |
|--------|--------|
| Section A execution order (`edit→verify→commit→remote-reachability→reply→read-back`) | 20/20 PASS |
| Recovery booleans (`stable_ids`, `cas`, `read_back`, `cleanup_blocks_incomplete`) | 20/20 PASS |
| Push authorization (`push_authorized=false`) | 20/20 PASS |
| Regression manifest validation | PASSED |

### Fix Required

Remove platform lock and runtime references from references/execution.md:
1. Remove line 3: "Platform lock: OpenCode + OhMyOpenCode (Sisyphus) only."
2. Remove "OMO / Prometheus prompt" handoff variant
3. Remove `.omo/notepads/` artifact location override
4. Replace `/start-work` with generic executor prompt

### F3: Phase Quorum

| Criterion | Status |
|-----------|--------|
| F3-GREEN-20 | ✅ 20 sessions completed |
| F3-REGRESSION-20 | ✅ Manifest validated |

## Deterministic Regression

Runner: `tests/run_address_pr_comments_review_regressions.py`
Validator: `scripts/validate-address-pr-comments-review-final.py`

### Case Manifest

- **File**: `tests/address-pr-comments-review-regressions/cases.json`
- **Schema version**: 1
- **Cases**: 20
- **Drivers**: 4 contract (route-*), 16 helper (artifact_ops.py scenarios)

### Regression Row Matrix

| Case ID | Driver | Exit | Diag | Sentinels |
|---------|--------|------|------|-----------|
| route-review-dossier | contract | 0 | — | rubric-v1, Section A, Section B, overview-table |
| route-direct-fix | contract | 0 | — | rubric-v1, direct-fix brief, Section A, commit SHA |
| route-reply-only | contract | 0 | — | rubric-v1, Section B, reply, read-back |
| route-no-action | contract | 0 | — | rubric-v1, Section C, zero actionable, overview-table |
| checkout-mismatch | helper | 0 | — | schema_version, operation, status |
| stale-evidence | helper | 2 | — | io-error, Artifact not found |
| dirty-target | helper | 0 | — | schema_version, operation, status |
| index-nonempty | helper | 2 | — | io-error, not found |
| lifecycle-legal | helper | 2 | — | io-error, not found |
| lifecycle-illegal | helper | 2 | — | illegal-transition, verified-complete |
| lifecycle-status-write-failure | helper | 4 | — | io-error |
| lifecycle-lock-cas | helper | 3 | — | cas-mismatch, SHA mismatch |
| commit-parent-path | helper | 0 | — | schema_version, operation, status |
| commit-fork-remote | helper | 0 | — | schema_version, operation, status |
| commit-push-resume | helper | 2 | — | io-error, not found |
| reply-preexisting | helper | 2 | — | io-error, not found |
| reply-marker-conflict | helper | 2 | — | io-error, not found |
| reply-ambiguous | helper | 2 | — | io-error, not found |
| cleanup-matrix | helper | 0 | — | schema_version, operation, status |
| cleanup-recovery | helper | 0 | — | schema_version, operation, status |
