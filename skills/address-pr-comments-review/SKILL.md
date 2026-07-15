---
name: address-pr-comments-review
description: >-
  Use when processing GitHub PR review comments that need human oversight before
  applying changes, or when cleaning up artifacts produced by this PR comment workflow.
  For large PRs, complex reviews with mixed human + AI bot feedback, PRs with blocking
  concerns, cleanup, cleanup-all, or any situation where fully automatic execution is too risky.
---

# Address PR Comments Review (Interactive)

## Overview

A three-phase interactive workflow for GitHub PR comment review. First bind the current checkout, then detect the PR and collect comments from that checkout.

- **Phase 1** (this skill): bind the current checkout, detect the PR, collect comments, ground actionable items in current-code evidence, classify from that evidence, and confirm interactively. If code changes are needed, either produce a review dossier for an executor or, for explicitly confirmed simple low-risk work, produce a Direct Fix Brief. If only replies are needed, post them directly and verify by read-back. If nothing is actionable, end.
- **Phase 2**: user gives the generated artifact to any capable executor via copy-paste handoff prompts.
- **Phase 3**: execution runs in the same checkout by the chosen executor.

Artifact storage is generic. Each artifact has one handoff owned by `references/execution.md`.
**Self-contained**: uses vendored `scripts/list_comments.py` (no Python package dependencies; requires `gh` CLI).

## On-Demand Loading

Load only the file needed for the current step. No file assumes you've read previous ones.

| Step | What You're Doing | Load | ~Lines |
|------|------------------|------|--------|
| 0 | Bind current checkout before PR detection | `references/execution.md` | 150 |
| 1 | Detect PR and collect comments from bound checkout | `references/execution.md` | 150 |
| 2a | Build evidence ledger for actionable comments | `references/classify.md` | 420 |
| 2b | Classify each comment from evidence, not suggestion text | `references/classify.md` | 420 |
| 2c | Detect duplicates, conflicts, relations across full set | `references/cross-reference.md` | 340 |
| 3 | Present overview table, discuss 🔴 items, get confirmation | `references/interaction.md` | 200 |
| 4a | Pre-write cross-reference scan (9 checks) | `references/dossier-output.md` §Validation Gates | 100 |
| 4b | Dossier Accuracy Grill Gate before writing final artifact | `references/dossier-output.md` §Dossier Accuracy Grill Gate | 80 |
| 4c | Generate dossier (Sections A/B/C, guardrails, dependencies) | `references/dossier-output.md` §Dossier Structure | 200 |
| 4d | Optional Direct Fix Brief for simple low-risk Section A, then direct-fix handoff | `references/dossier-output.md` §Direct-Fix Fast Path + `references/execution.md` §Direct Fix Brief Handoff | 200 |
| 4e | Enforce reply task contract (gate check, templates, duplicate strategy) | `references/dossier-output.md` §Reply Policy | 200 |
| 5 | Handoff message to user | `references/execution.md` §Dossier Handoff or §Direct Fix Brief Handoff | 20 |
| cleanup | Clean current PR artifacts | `references/execution.md` §Artifact Cleanup | 80 |
| cleanup-all | Clean all default artifacts | `references/execution.md` §Artifact Cleanup | 80 |

**Small PR fast-path** (≤5 raw comments, no conflicts after Step 2): user can say "proceed" after Step 3 table, skip individual discussion. This compresses interaction only; it does not by itself authorize direct code execution.

**Direct-Fix Fast Path** (simple low-risk Section A): after Step 3 confirmation and Step 4a scan, the user may explicitly choose Direct Fix after seeing the final classification table. The batch is bounded to one through five independent Section A tasks. Every task must be unambiguous, low-risk, single-file, dependency-free, conflict-free, and complete enough for execution and reply read-back. Run the Dossier Accuracy Grill Gate first. If all eligibility checks pass, write a Direct Fix Brief instead of the full dossier. No second plan-approval step is required for an eligible batch. If any eligibility condition fails, name every failed condition and route to Review Dossier.

**Reply-only path** (Section A = 0, Section B > 0): after Step 0 has bound the current checkout and Step 3 confirms replies only, load `dossier-output.md`. Read §Reply Endpoints, §Direct Reply-Only Posting, and §Reply Policy. Skip Dossier Structure, Sections A/B/C, Validation Gates, and Handoff. This path MUST POST/send replies through the documented endpoints, then verify each reply by read-back with GET/LIST operations. Drafting or composing reply text is not completion.

## Prerequisites

- `gh` CLI installed and authenticated (`gh auth status`)
- A target checkout can be resolved from the current Git root; explicit `worktree_path=` is used for handoff or operator override, not as the default interaction path

## Error Recovery

| Failure | Action |
|---------|--------|
| `gh` not installed / not authenticated | Stop. Tell user to run `gh auth login`. |
| `list_comments.py` fails (network, API rate limit, empty JSON) | Retry once after 5s. If still fails, verify `gh pr view` works manually, report error, ask user. |
| PR not found | Report gh error. Ask user to verify PR number/state. |
| Zero comments | Report "PR has no comments, nothing to review." |
| All comments informational | No dossier needed. All Section A=0, B=0 — nothing actionable. End. |

## Workflow (with Gates)

```
[0] Bind Current Checkout (references/execution.md)
  │  └─ TARGET_WORKTREE_ROOT bound before PR detection
  │
[1] Detect PR + Collect (references/execution.md)
  │
[2a] Evidence Ledger (references/classify.md)
  │  └─ actionable comments grounded in current HEAD code evidence before conclusion
  │
[2b] Classify From Evidence (references/classify.md)
  │  └─ concern verdict and reviewer suggestion fit decided separately
  │
[2c] Cross-Ref (references/cross-reference.md)
  │  ├─ duplicates merged, conflicts flagged, relations noted
  │  └─ already-replied detected
  │
[3] Interactive Table (references/interaction.md)
  │  ├─ 🔴 items discussed & resolved  ← BLOCKING GATE
  │  ├─ Silent consent for non-🔴 items
  │  └─ User explicitly confirms table; `proceed` does not select Direct Fix
  │
  ├── Post-Confirmation Routing (references/interaction.md §Post-Confirmation Routing)
  │     ├─ A > 0 (Direct Fix explicitly selected, eligible 1-5 batch) ─► [4a] Pre-Write Scan → [4b] Grill Gate → [4d] Direct Fix Brief → execution.md §Direct Fix Brief Handoff
  │     ├─ A > 0 (default/complex code changes) ─► [4a] Pre-Write Scan → [4b] Grill Gate → [4c] Dossier → Reply task contract → [5]
  │     ├─ A = 0, B > 0 (replies) ─► POST/send replies → read-back verify replies → done
  │     └─ A = 0, B = 0 (nothing)  ─► done
  │
[4a] Pre-Write Scan (references/dossier-output.md §Validation Gates)
  │  └─ 9 checks pass  ← BLOCKING GATE
  │
[4b] Dossier Accuracy Grill Gate
  │  └─ ask only unresolved implementation/scope/test/reply questions; grill-with-docs is not default
  │
[4c] Dossier → ~/.local/state/ai-toolkits/pr-comments/<owner>__<repo>/pr-<N>/
  │
[4d] Direct Fix Brief → ~/.local/state/ai-toolkits/pr-comments/<owner>__<repo>/pr-<N>/direct-fix-<TIMESTAMP>.md
  │  └─ contains exact edit, guardrails, verification, reply endpoint, commit SHA requirement, read-back verification
  │
[4e] Replies (references/dossier-output.md §Reply Policy)
  │  └─ Execution plan MUST include reply task(s) after code/test/commit work and before read-back verification
  │
[5] Handoff → execution.md §Dossier Handoff or §Direct Fix Brief Handoff
```

Direct Fix execution is serial and fail-stop. A failed checkout validation, verification, commit, push, remote-reachability check, reply, or read-back blocks the whole batch. Preserve completed task evidence and leave later tasks unresolved. Review Dossier remains plan-first and waits for explicit user approval before editing. See `references/interaction.md` for route selection, `references/dossier-output.md` for eligibility and fail-stop artifact rules, and `references/execution.md` for the exclusive handoffs.

**Do NOT act as the executor yourself.** User drives Phase 2 & 3.

**Cleanup commands route first**: If the user invokes `/address-pr-comments-review cleanup` or `/address-pr-comments-review cleanup-all`, load `references/execution.md` §Artifact Cleanup immediately. Do not bind PR comments, classify, generate dossiers, post replies, or run the normal review workflow.

For exact handoff wording, use `references/execution.md` §Dossier Handoff or §Direct Fix Brief Handoff. Do not duplicate handoff templates here.

**After execution succeeds**: `git log --oneline`, `git push`, verify PR replies.
**If execution fails mid-way**: re-run this skill. `has_replies` detection skips handled items.

## Key Principles

- **AI is analyst, user is decider.** Skill classifies; user decides on 🔴 items.
- **Concern first, fix second.** Review comments are evidence leads, not implementation instructions.
- **No evidence, no conclusion.** Actionable comments need current-code evidence before `valid`, `invalid`, `already_fixed`, or `partially_addressed`.
- **Suggestion is not solution.** A reviewer may identify a real issue while proposing the wrong fix.
- **Duplicates are detected, not created.** Same `file:line` + same concern = one task.
- **Conflicts are surfaced, not buried.** Opposing advice is flagged and documented.

## Quick Commands

```bash
# Resolve SCRIPT: <skill-dir>/scripts/list_comments.py
# (<skill-dir> = directory containing this SKILL.md)
# Resolve TARGET_WORKTREE_ROOT first in references/execution.md, then run commands from that checkout.

# Auto-detect PR, collect comments
python3 "$SCRIPT" --json

# Cross-repo PR
python3 "$SCRIPT" --repo owner/name --pr <N> --json

# Include resolved threads
python3 "$SCRIPT" --include-resolved --json
```
