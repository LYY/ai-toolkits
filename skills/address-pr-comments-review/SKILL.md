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
- **Phase 2**: user gives the generated artifact to an executor. OMO/Prometheus is optional and supported by copy-paste handoff prompts.
- **Phase 3**: execution runs in the same checkout. For OMO, user runs `/start-work <PLAN_PATH> worktree_path=<TARGET_WORKTREE_ROOT>`.

**Platform lock**: OpenCode + OhMyOpenCode (Sisyphus) only for this installed workflow. Artifact storage is generic by default; Prometheus mode and `/start-work` are optional handoff targets.
**Self-contained**: uses vendored `scripts/list_comments.py` (no Python package dependencies; requires `gh` CLI).

## On-Demand Loading

Load only the file needed for the current step. No file assumes you've read previous ones.

| Step | What You're Doing | Load | ~Lines |
|------|------------------|------|--------|
| 0 | Bind current checkout before PR detection | `references/platform.md` | 150 |
| 1 | Detect PR and collect comments from bound checkout | `references/platform.md` | 150 |
| 2a | Build evidence ledger for actionable comments | `references/classify.md` | 420 |
| 2b | Classify each comment from evidence, not suggestion text | `references/classify.md` | 420 |
| 2c | Detect duplicates, conflicts, relations across full set | `references/cross-reference.md` | 340 |
| 3 | Present overview table, discuss 🔴 items, get confirmation | `references/interaction.md` | 200 |
| 4a | Pre-write cross-reference scan (7 checks) | `references/dossier-output.md` §Validation Gates | 100 |
| 4b | Dossier Accuracy Grill Gate before writing final artifact | `references/dossier-output.md` §Dossier Accuracy Grill Gate | 80 |
| 4c | Generate dossier (Sections A/B/C, guardrails, dependencies) | `references/dossier-output.md` §Dossier Structure | 200 |
| 4d | Optional Direct Fix Brief for simple low-risk Section A | `references/dossier-output.md` §Direct-Fix Fast Path | 180 |
| 4e | Enforce reply task contract (gate check, templates, duplicate strategy) | `references/dossier-output.md` §Reply Policy | 200 |
| 5 | Handoff message to user | `references/platform.md` §Handoff | 20 |
| cleanup | Clean current PR artifacts | `references/platform.md` §Artifact Cleanup | 80 |
| cleanup-all | Clean all default artifacts | `references/platform.md` §Artifact Cleanup | 80 |

**Small PR fast-path** (≤5 raw comments, no conflicts after Step 2): user can say "proceed" after Step 3 table, skip individual discussion. This compresses interaction only; it does not by itself authorize direct code execution.

**Direct-Fix Fast Path** (simple low-risk Section A): after Step 3 confirmation and Step 4a scan, the user may explicitly choose direct fix when every code-change item is unambiguous, low-risk, single-file, dependency-free, conflict-free, and has complete reply target data. Run the Dossier Accuracy Grill Gate first. If it passes, write a Direct Fix Brief instead of the full Prometheus dossier. If any ambiguity appears, use the normal dossier/Prometheus path.

**Reply-only path** (Section A = 0, Section B > 0): after Step 0 has bound the current checkout and Step 3 confirms replies only, load `dossier-output.md`. Read §Reply Endpoints, §Direct Reply-Only Posting, and §Reply Policy. Skip Dossier Structure, Sections A/B/C, Validation Gates, and Handoff. This path MUST POST/send replies through the documented endpoints, then verify each reply by read-back with GET/LIST operations. Drafting or composing reply text is not completion.

## Prerequisites

- `gh` CLI installed and authenticated (`gh auth status`)
- OpenCode + OhMyOpenCode (Sisyphus) environment
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
[0] Bind Current Checkout (references/platform.md)
  │  └─ TARGET_WORKTREE_ROOT bound before PR detection
  │
[1] Detect PR + Collect (references/platform.md)
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
  │  └─ User explicitly confirms ("ok" / "proceed" / etc.)
  │
  ├── Post-Confirmation Routing (references/interaction.md §Post-Confirmation Routing)
  │     ├─ A > 0 (simple, direct-fix chosen) ─► [4a] Pre-Write Scan → [4b] Grill Gate → [4d] Direct Fix Brief → direct execution handoff
  │     ├─ A > 0 (default/complex code changes) ─► [4a] Pre-Write Scan → [4b] Grill Gate → [4c] Dossier → Reply task contract → [5]
  │     ├─ A = 0, B > 0 (replies) ─► POST/send replies → read-back verify replies → done
  │     └─ A = 0, B = 0 (nothing)  ─► done
  │
[4a] Pre-Write Scan (references/dossier-output.md §Validation Gates)
  │  └─ 7 checks pass  ← BLOCKING GATE
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
  │  └─ Prometheus execution plan MUST include reply task(s) after code/test/commit work and before read-back verification
  │
[5] Handoff → generic executor prompt; optional OMO /start-work prompt with worktree_path=TARGET_WORKTREE_ROOT
```

**Do NOT run Prometheus or `/start-work` yourself.** User drives optional OMO Phase 2 & 3.

**Cleanup commands route first**: If the user invokes `/address-pr-comments-review cleanup` or `/address-pr-comments-review cleanup-all`, load `references/platform.md` §Artifact Cleanup immediately. Do not bind PR comments, classify, generate dossiers, post replies, or run the normal review workflow.

For the exact Phase 2 and Phase 3 handoff, use `references/platform.md` §Handoff. Do not duplicate the handoff wording here.

**After `/start-work` succeeds**: `git log --oneline`, `git push`, verify PR replies.
**If `/start-work` fails mid-execution**: re-run this skill. `has_replies` detection skips handled items.

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
# Resolve TARGET_WORKTREE_ROOT first in references/platform.md, then run commands from that checkout.

# Auto-detect PR, collect comments
python3 "$SCRIPT" --json

# Cross-repo PR
python3 "$SCRIPT" --repo owner/name --pr <N> --json

# Include resolved threads
python3 "$SCRIPT" --include-resolved --json
```
