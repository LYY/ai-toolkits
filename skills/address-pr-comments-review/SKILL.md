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

## Prerequisites

- `gh` CLI installed and authenticated (`gh auth status` must pass)
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

Run `python3 ./scripts/list_comments.py --json` to fetch all comments for the current PR. The script auto-detects the PR from the current branch via `gh pr view`. Override with `--pr <N>`. For cross-repo access (when not running from the repo directory), use `--repo owner/name`. Include resolved threads with `--include-resolved`.

The script aggregates top-level PR comments, review body comments, inline review comments (unresolved threads by default), and AI prompt snippets when present in bot comments.

See `references/platform.md` for all flags and usage variants.

### [2] Classify & Cross-Reference

**CRITICAL**: Read the full `body` field from JSON output, not `excerpt` (truncated to 220 chars).

For each comment, determine:
- **Source**: `@human` vs `@bot` — see `references/classification.md` (Source Detection)
- **Intent**: `actionable` vs `informational` — see `references/classification.md` (Intent Assessment)
- **Conclusion**: `valid`, `invalid`, `already_fixed`, `already_replied`, `out_of_scope`, `needs_clarification`, `partially_addressed` — see `references/classification.md` (Conclusion Taxonomy)
- **Edge cases**: minimized comments, thread_outdated, thread_resolved, has_replies, deleted/ghost authors, empty body, self-review — see `references/classification.md` (Edge Cases)
- **Dossier section mapping**: conclusions map to Section A (code change), Section B (reply only), or Section C (skip) — see `references/classification.md` (Dossier Section Mapping)

Then scan the full classified set for cross-comment patterns:
- **Duplicates**: same file:line + same concern — merge into one entry
- **Conflicts**: opposing recommendations on same code — flag for discussion
- **Related**: causally/logically connected comments across files — add dependency notes
- **Already-replied**: two-level assessment (has a reply vs reply is sufficient)
- **Cross-file escalation**: same pattern in multiple files — guardrail against scope creep

See `references/cross-reference.md` for detection signals, merge strategies, and escalation rules.

### [3] Interactive Confirmation

Present the full analysis in a structured overview table with headers: `# | 来源 | 类型 | 文件 | 摘要 | 结论 | 去重/冲突 | 讨论`. Even when zero items are actionable, the table is mandatory.

Discussion order:
1. Resolve flagged items (conflicts, needs_clarification, high-risk valid) one by one
2. Non-flagged items proceed by silent consent — user can object by number at any time
3. After all discussion converges, produce an updated final confirmation table with a change summary

User explicitly confirms with "ok" or equivalent before proceeding to dossier generation.

See `references/interaction.md` for table format, legend, silent consent rules, discussion gating, scaling strategies for large PRs, and confirmation gate rules.

### [4] Generate Review Dossier

Write the dossier to `.sisyphus/notepads/pr-<N>-dossier/dossier-<TIMESTAMP>.md`. Use `date +%Y%m%d-%H%M%S` for the timestamp. The dossier is a requirements document, not an execution plan — plan generation happens in Phase 2.

**Before writing**: run a final cross-reference scan against the confirmed table. Check for new duplicates, stale duplicates, unresolved conflicts, orphaned replies, new relations, cross-section leakage, reply target mismatch, and stale already_replied items. If any item remains unresolved, return to Step 3.

See `references/dossier.md` for the full dossier structure (Executive Summary, Reply Endpoints, Sections A/B/C templates, duplicate and conflict handling, dependency notation, scope guardrails).

See `references/validation.md` for the 8-item pre-write cross-reference scan checklist and post-write dossier verification checks.

**After writing**, verify:
- File exists at expected path
- File starts with `# Review Dossier:`
- Executive Summary counts match actual items in each section
- No `{{...}}` template placeholders remain unfilled
- Every reply task uses the correct endpoint kind

### [5] Handoff

```
Dossier saved to .sisyphus/notepads/pr-<N>-dossier/dossier-<TIMESTAMP>.md

To generate the execution plan, switch to Prometheus mode and paste:

  Read .sisyphus/notepads/pr-<N>-dossier/dossier-<TIMESTAMP>.md
  and generate an execution plan. Ask me if any task is ambiguous.
```

**Do NOT run `@plan` or `/start-work` yourself.** The user drives Phase 2 (Prometheus conversation) and Phase 3 (`/start-work` execution).

**After execution**: review commits (`git log --oneline`), `git push`, verify replies on the PR. If anything was missed, re-run this skill — `has_replies` detection skips already-handled items.

**If `/start-work` fails mid-execution**: check which tasks succeeded (commits + PR replies), re-run this skill to generate a dossier of remaining items, then generate a new plan and re-run.

## Reply Policy

The reply policy governs when and how to reply to PR comments. Key rules:

- **Pre-Reply Gate**: before composing any reply, verify the thread does not already have a sufficient human reply. If it does, do NOT reply. Four checks must all pass.
- **Change Summary Rule**: `Fixed in <sha>` alone is insufficient when the fix is misleading, partial, or non-obvious. Always add a change summary unless the change is truly self-explanatory.
- **Duplicate Author Reply**: when comments are merged as duplicates, compose ONE reply and send it to each author individually via their own `in_reply_to` ID.
- **Partial Fix Reply**: acknowledge the existing fix attempt, explain why it is insufficient, describe the correct fix direction.

See `references/reply.md` for the full pre-reply gate checklist, change summary rule, reply templates per conclusion, duplicate author strategy, and partial fix reply requirements.

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
