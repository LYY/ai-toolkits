---
name: address-pr-comments-review
description: >-
  Use when processing GitHub PR review comments that need human oversight before
  applying changes. For large PRs, complex reviews with mixed human + AI bot feedback,
  PRs with blocking concerns, or any situation where fully automatic execution is too risky.
---

# Address PR Comments Review (Interactive)

## Overview

A three-phase interactive workflow for GitHub PR comment review. First bind the current checkout, then detect the PR and collect comments from that checkout.

- **Phase 1** (this skill): bind the current checkout, detect the PR, collect, classify, and confirm comments interactively. If code changes are needed, produce a review dossier for Phase 2. If only replies are needed, post them directly and verify by read-back. If nothing is actionable, end.
- **Phase 2**: user switches to Prometheus mode, gives it the dossier, and has an interactive conversation to generate an execution plan.
- **Phase 3**: user runs `/start-work <PLAN_PATH> worktree_path=<TARGET_WORKTREE_ROOT>` so execution starts in the same checkout.

**Platform lock**: OpenCode + OhMyOpenCode (Sisyphus) only. Dossier placement, Prometheus mode, and `/start-work` handoff are Sisyphus-specific.
**Self-contained**: uses vendored `scripts/list_comments.py` (no Python package dependencies; requires `gh` CLI).

## On-Demand Loading

Load only the file needed for the current step. No file assumes you've read previous ones.

| Step | What You're Doing | Load | ~Lines |
|------|------------------|------|--------|
| 0 | Bind current checkout before PR detection | `references/platform.md` | 150 |
| 1 | Detect PR and collect comments from bound checkout | `references/platform.md` | 150 |
| 2a | Classify each comment individually | `references/classify.md` | 330 |
| 2b | Detect duplicates, conflicts, relations across full set | `references/cross-reference.md` | 340 |
| 3 | Present overview table, discuss 🔴 items, get confirmation | `references/interaction.md` | 200 |
| 4a | Pre-write cross-reference scan (8 checks) | `references/dossier-output.md` §Validation Gates | 100 |
| 4b | Generate dossier (Sections A/B/C, guardrails, dependencies) | `references/dossier-output.md` §Dossier Structure | 200 |
| 4c | Enforce reply task contract (gate check, templates, duplicate strategy) | `references/dossier-output.md` §Reply Policy | 200 |
| 5 | Handoff message to user | `references/platform.md` §Handoff | 20 |

**Small PR fast-path** (≤5 raw comments, no conflicts after Step 2): user can say "proceed" after Step 3 table, skip individual discussion.

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
[2a] Classify (references/classify.md)
  │
[2b] Cross-Ref (references/cross-reference.md)
  │  ├─ duplicates merged, conflicts flagged, relations noted
  │  └─ already-replied detected
  │
[3] Interactive Table (references/interaction.md)
  │  ├─ 🔴 items discussed & resolved  ← BLOCKING GATE
  │  ├─ Silent consent for non-🔴 items
  │  └─ User explicitly confirms ("ok" / "proceed" / etc.)
  │
  ├── Post-Confirmation Routing (references/interaction.md §Post-Confirmation Routing)
  │     ├─ A > 0 (code changes) ────► [4a] Pre-Write Scan → [4b] Dossier → [4c] Reply task contract → [5]
  │     ├─ A = 0, B > 0 (replies) ─► POST/send replies → read-back verify replies → done
  │     └─ A = 0, B = 0 (nothing)  ─► done
  │
[4a] Pre-Write Scan (references/dossier-output.md §Validation Gates)
  │  └─ 8 checks pass  ← BLOCKING GATE
  │
[4b] Dossier → .omo/notepads/pr-<N>-dossier/
  │
[4c] Replies (references/dossier-output.md §Reply Policy)
  │  └─ Prometheus execution plan MUST include reply task(s) after code/test/commit work and before read-back verification
  │
[5] Handoff with worktree_path=TARGET_WORKTREE_ROOT → Prometheus → /start-work
```

**Do NOT run Prometheus or `/start-work` yourself.** User drives Phase 2 & 3.

For the exact Phase 2 and Phase 3 handoff, use `references/platform.md` §Handoff. Do not duplicate the handoff wording here.

**After `/start-work` succeeds**: `git log --oneline`, `git push`, verify PR replies.
**If `/start-work` fails mid-execution**: re-run this skill. `has_replies` detection skips handled items.

## Key Principles

- **AI is analyst, user is decider.** Skill classifies; user decides on 🔴 items.
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
