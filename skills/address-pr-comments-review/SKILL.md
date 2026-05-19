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

- **Phase 1** (this skill): collect, classify, and confirm comments interactively with the user, then produce a review dossier.
- **Phase 2**: user switches to Prometheus mode, gives it the dossier, and has an interactive conversation to generate an execution plan (with built-in Metis gap analysis + Momus review).
- **Phase 3**: user runs `/start-work` to execute the plan in isolated workspaces.

**Platform lock**: OpenCode + OhMyOpenCode (Sisyphus) only. Dossier placement and Prometheus to `/start-work` flow are Sisyphus-specific. Not compatible with other agent platforms.

**Self-contained**: uses its own `scripts/list_comments.py` (vendored, no Python package dependencies; requires `gh` CLI).

## Quick Reference

| For operators who need to... | Open this file |
|---|---|
| **Classify a comment** (source, intent, conclusion) | `references/classification.md` |
| **Detect duplicates, conflicts, or relations** | `references/cross-reference.md` |
| **Run the interactive confirmation table** | `references/interaction.md` |
| **Write the review dossier** | `references/dossier.md` |
| **Compose a reply to a comment** | `references/reply.md` |
| **Find runtime commands** (collection, paths, handoff) | `references/platform.md` |
| **Run validation gates and checks** | `references/validation.md` |

## Prerequisites

- `gh` CLI installed and authenticated (see `references/platform.md` for verification)
- OpenCode + OhMyOpenCode (Sisyphus) environment
- Current git branch has an open PR, or you know the PR number

## Reference Architecture

This skill uses a four-layer reference architecture. Detailed rules live in dedicated protocol files under `references/`. SKILL.md orchestrates them.

| Layer | Files | Role |
|-------|-------|------|
| Entry | `SKILL.md` | Entry point, phases, orchestration, error recovery |
| Workflow | `classification.md`, `cross-reference.md`, `interaction.md` | How each step works |
| Decision | `dossier.md`, `reply.md` | What to produce |
| Templates | `platform.md`, `validation.md` | Commands, checklists, gate rules |

See `references/overview.md` for the full precedence model and file map.

## Error Recovery

| Failure | Response |
|---------|----------|
| `gh` not installed / not authenticated | Stop. Tell user to run `gh auth login`. |
| `list_comments.py` fails (network, API rate limit) | Retry once after 5 seconds. If still fails, report the error and ask user if they want to continue with manual PR number override. |
| PR not found (wrong number, closed, merged) | Report the specific gh error. Ask user to verify PR number and state. |
| **Zero comments on PR** | Report: "PR has no comments — nothing to review." Suggest the user check if reviews are pending. |
| **All comments are informational** | Still produce a minimal dossier (Section A=0, B=0, C=all) with a note. User can then decide to skip `/start-work`. |
| Script returns empty JSON | Verify `gh pr view` works manually. Check that the branch has an open PR. |

## Workflow

```
PR address or auto-detect
    ↓
[1] Collect comments (list_comments.py)
    ↓
[2] Classify + cross-reference
    ↓
[3] Interactive confirmation (silence = consent)
    ↓
[4] Generate review dossier
    ↓
[5] Handoff → Prometheus → /start-work
```

### [1] Collect Comments

See `references/platform.md` (Comment Collection section) for collection script usage.

### [2] Classify & Cross-Reference

**CRITICAL**: Read the full `body` field from JSON output, not `excerpt` (truncated to 220 chars).

- **Classify**: Per `references/classification.md` — source detection, intent assessment, conclusion taxonomy, edge cases, dossier section mapping.
- **Cross-reference**: Per `references/cross-reference.md` — duplicate detection, conflict detection, relation detection, already-replied detection, cross-file escalation rules.

### [3] Interactive Confirmation

Present the structured overview table per `references/interaction.md` (mandatory, even when zero items are actionable). Follow the interaction flow: resolve flagged items first, non-flagged items proceed by silent consent, then produce a final confirmation table with change summary. User must explicitly confirm before proceeding to dossier generation.

### [4] Generate Review Dossier

Write the dossier to `.sisyphus/notepads/pr-<N>-dossier/dossier-<TIMESTAMP>.md`. The dossier is a requirements document, not an execution plan — plan generation happens in Phase 2.

**Before writing**: run the final cross-reference scan per `references/validation.md` (8-item checklist). If any item remains unresolved, return to Step 3.

**After writing**: verify file existence, valid markdown, count matching, no placeholder leakage, and endpoint correctness per `references/validation.md`.

See `references/dossier.md` for the full dossier structure (Executive Summary, Reply Endpoints, Sections A/B/C templates, duplicate and conflict handling, dependency notation, scope guardrails).

### [5] Handoff

See `references/platform.md` (Handoff section) for the handoff message format.

**Do NOT run `@plan` or `/start-work` yourself.** The user drives Phase 2 (Prometheus conversation) and Phase 3 (`/start-work` execution).

**After execution**: review commits (`git log --oneline`), `git push`, verify replies on the PR. If anything was missed, re-run this skill — `has_replies` detection skips already-handled items.

**If `/start-work` fails mid-execution**: check which tasks succeeded (commits + PR replies), re-run this skill to generate a dossier of remaining items, then generate a new plan and re-run.

## Reply Policy

The reply policy governs when and how to reply to PR comments. See `references/reply.md` for the complete set of rules: the pre-reply gate checklist, change summary requirements, duplicate author reply strategy, partial fix reply requirements, and reply templates per conclusion.

## Interaction Checklist

| Step | Gate | Condition |
|------|------|-----------|
| 2 | Cross-reference scanned | Duplicates merged, conflicts flagged, relations noted, already-replied detected |
| 3 | Overview confirmed | User accepts or remains silent after flagged items discussed |
| 3 | Final table confirmed | User explicitly confirms ("ok", "go ahead") |
| 4 (before write) | Final cross-reference scan | All 8 checks pass, no unresolved items remain |
| 4 | Dossier written | File exists and is complete (no unfilled placeholders) |
| 5 | Handoff delivered | User sees next-step instructions with Prometheus conversation + `/start-work` |

## Key Principles

- **AI is analyst, user is decider**. Skill classifies and suggests; user makes final calls on `needs_clarification` and high-risk items.
- **Silence is consent**. Uncontested items proceed on AI recommendation. Object by item number to override.
- **Three phases, never collapse**. Phase 1 = dossier (this skill), Phase 2 = interactive Prometheus plan, Phase 3 = `/start-work` execution.
- **Duplicates are detected, not created**. Cross-reference merges same file:line issues into single tasks. Plan mode must never see two tasks modifying the same line for the same reason.
- **Conflicts are surfaced, not buried**. Opposing reviewer advice is flagged during interaction and documented in the dossier.
- **Final scan is mandatory**. Discussion changes things. The cross-reference scan before dossier generation catches new duplicates, stale merges, and unresolved conflicts. Never skip this gate.

## Quick Commands

```bash
# Auto-detect PR, collect comments
python3 ./scripts/list_comments.py --json

# Cross-repo PR
python3 ./scripts/list_comments.py --repo owner/name --pr <N> --json

# Include resolved threads
python3 ./scripts/list_comments.py --include-resolved --json
```
