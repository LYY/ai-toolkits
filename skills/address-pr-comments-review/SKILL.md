---
name: address-pr-comments-review
description: >-
  Use when processing GitHub PR review comments that need human oversight before
  applying changes. For large PRs, complex reviews with mixed human + AI bot feedback,
  PRs with blocking concerns, or any situation where fully automatic execution is too risky.
---

# Address PR Comments Review (Interactive)

## Overview

A three-phase interactive workflow for GitHub PR comment review.

- **Phase 1** (this skill): collect, classify, and confirm comments interactively, then produce a review dossier.
- **Phase 2**: user switches to Prometheus mode, gives it the dossier, and has an interactive conversation to generate an execution plan.
- **Phase 3**: user runs `/start-work` to execute the plan in isolated workspaces.

**Platform lock**: OpenCode + OhMyOpenCode (Sisyphus) only. Dossier placement and Prometheus to `/start-work` flow are Sisyphus-specific.
**Self-contained**: uses vendored `scripts/list_comments.py` (no Python package dependencies; requires `gh` CLI).

## On-Demand Loading

Load only the file needed for the current step. No file assumes you've read previous ones.

| Step | What You're Doing | Load | ~Lines |
|------|------------------|------|--------|
| 1 | Collect comments from PR | `platform.md` | 150 |
| 2a | Classify each comment individually | `classify.md` | 330 |
| 2b | Detect duplicates, conflicts, relations across full set | `cross-reference.md` | 340 |
| 3 | Present overview table, discuss 🔴 items, get confirmation | `interaction.md` | 200 |
| 4a | Pre-write cross-reference scan (8 checks) | `dossier-output.md` §Validation Gates | 100 |
| 4b | Generate dossier (Sections A/B/C, guardrails, dependencies) | `dossier-output.md` §Dossier Structure | 200 |
| 4c | Compose replies (gate check, templates, duplicate strategy) | `dossier-output.md` §Reply Policy | 200 |
| 5 | Handoff message to user | `platform.md` §Handoff | 20 |

**Small PR fast-path** (≤5 raw comments, no conflicts after Step 2): user can say "proceed" after Step 3 table, skip individual discussion.

## Prerequisites

- `gh` CLI installed and authenticated (`gh auth status`)
- OpenCode + OhMyOpenCode (Sisyphus) environment
- Current branch has an open PR, or PR number is known

## Error Recovery

| Failure | Action |
|---------|--------|
| `gh` not installed / not authenticated | Stop. Tell user to run `gh auth login`. |
| `list_comments.py` fails (network, API rate limit) | Retry once after 5s. If still fails, report error, ask user. |
| PR not found | Report gh error. Ask user to verify PR number/state. |
| Zero comments | Report "PR has no comments — nothing to review." |
| All comments informational | Produce minimal dossier (Sections A=0, B=0, C=all). User can skip `/start-work`. |
| Script returns empty JSON | Verify `gh pr view` works manually. Check branch has open PR. |

## Workflow (with Gates)

```
[1] Collect (platform.md)
  │
[2a] Classify (classify.md)
  │
[2b] Cross-Ref (cross-reference.md)
  │  ├─ duplicates merged, conflicts flagged, relations noted
  │  └─ already-replied detected
  │
[3] Interactive Table (interaction.md)
  │  ├─ 🔴 items discussed & resolved  ← BLOCKING GATE
  │  ├─ Silent consent for non-🔴 items
  │  └─ User explicitly confirms ("ok" / "proceed" / etc.)
  │
[4a] Pre-Write Scan (dossier-output.md §Validation Gates)
  │  └─ 8 checks pass  ← BLOCKING GATE
  │
[4b] Dossier → .sisyphus/notepads/pr-<N>-dossier/
  │
[4c] Replies (dossier-output.md §Reply Policy)
  │
[5] Handoff → Prometheus → /start-work
```

**Do NOT run Prometheus or `/start-work` yourself.** User drives Phase 2 & 3.

**After `/start-work` succeeds**: `git log --oneline`, `git push`, verify PR replies.
**If `/start-work` fails mid-execution**: re-run this skill — `has_replies` detection skips handled items.

## Key Principles

- **AI is analyst, user is decider.** Skill classifies; user decides on 🔴 items.
- **Silence is consent.** Uncontested items proceed on AI recommendation.
- **Three phases, never collapse.** Dossier → Prometheus plan → `/start-work` execution.
- **Duplicates are detected, not created.** Same `file:line` + same concern = one task.
- **Conflicts are surfaced, not buried.** Opposing advice is flagged and documented.
- **Final scan is mandatory.** Discussion changes things — never skip the pre-write 8-check scan.

## Quick Commands

```bash
# Auto-detect PR, collect comments
python3 ./scripts/list_comments.py --json

# Cross-repo PR
python3 ./scripts/list_comments.py --repo owner/name --pr <N> --json

# Include resolved threads
python3 ./scripts/list_comments.py --include-resolved --json
```
