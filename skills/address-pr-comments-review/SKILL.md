---
name: address-pr-comments-review
description: >-
  Use when processing GitHub PR review comments that need human oversight before
  applying changes. For large PRs, complex reviews with mixed human + AI bot feedback,
  PRs with blocking concerns, or any situation where fully automatic execution is too risky.
---

# Address PR Comments Review (Interactive)

## Overview

A two-phase interactive workflow for GitHub PR comment review.

- **Phase 1** (this skill): collect, classify, and confirm comments interactively with the user, then generate a Sisyphus execution plan.
- **Phase 2**: user runs `/start-work` to load the plan and execute per-comment tasks in isolated workspaces.

**Platform lock**: OpenCode + OhMyOpenCode (Sisyphus) only. Plan generation depends on the Metis/Momus review chain and `/start-work` execution mode. Not compatible with other agent platforms (Claude Code, Cursor, Gemini CLI, etc.).

**Self-contained**: uses its own `scripts/list_comments.py` (vendored, no external dependencies).

## Prerequisites

- `gh` CLI installed and authenticated
- OpenCode + OhMyOpenCode (Sisyphus) environment
- Current git branch has an open PR, or you know the PR number

## Workflow

```
PR address or auto-detect
    ↓
[1] Collect comments (list_comments.py)
    ↓
[2] Classify + validate (per comment analysis)
    ↓
[3] Overview table → interactive confirmation (silence = consent)
    ↓   discussion complete
[4] Final confirmation table → user approves
    ↓   approved
[5] Plan generation: AI draft → Metis review → Momus review → write
    ↓
[6] User runs /start-work to execute
```

### [1] Collect Comments

```bash
python3 ./scripts/list_comments.py --json
```

The script auto-detects the PR from the current branch via `gh pr view`. Override with `--pr <N>`. Include resolved threads with `--include-resolved`.

Aggregates:
- Top level PR comments
- Review body comments
- Inline review comments (unresolved threads by default)
- AI prompt snippets when present in bot comments

### [2] Classify + Validate

For each comment, determine three attributes:

**Source**: `@human` vs `@bot` (coderabbit, etc.)

**Intent**: `actionable` (needs work or reply) vs `informational` (LGTM, emoji, praise, FYI — skip entirely)

**Conclusion** (actionable comments only):

| Conclusion | Meaning |
|-----------|---------|
| `valid` | Should be addressed |
| `invalid` | Doesn't apply, with brief reason |
| `already_fixed` | Already resolved in current code |
| `out_of_scope` | Outside this PR's scope |
| `needs_clarification` | Need reviewer input to proceed |

**Discussion flag**: Comments with `needs_clarification` or high-risk `valid` items get marked 🔴.

### [3] Overview Table + Interactive Confirmation

Present the full analysis in a structured table:

```
## PR #N Comment Analysis — X total, Y actionable

### Overview
| # | 来源 | 类型 | 文件 | 摘要 | 结论 | 讨论 |
|---|------|------|------|------|------|------|
| 1 | @human | inline | foo.ts:42 | var → const | valid | |
| 2 | @bot   | inline | bar.ts:15 | rename suggestion | invalid | |
| 3 | @human | inline | baz.ts:8 | logic question | needs_clarification | 🔴 needs input |

### 🔴 Needs Discussion (N items)
Expand each 🔴 item with context and explicitly ask the user for direction.

### 📝 Silent Consent (M items)
Items without 🔴 are accepted as-is per AI conclusion. Speak up if you disagree.
```

**Interaction rules**:
- Silence = consent. If user says "continue", "ok", "go ahead", or doesn't object — assume agreement with AI conclusions.
- User can object to specific items by number. Discuss and update the conclusion.
- `needs_clarification` items require explicit user direction. Do not proceed without it.
- Discuss 🔴 items first, then confirm the rest are accepted.

### [4] Final Confirmation Table

After all discussion converges, produce an updated table reflecting every outcome. All 🔴 items must be resolved (conclusion changed or confirmed). User explicitly confirms with "ok" or equivalent.

This is the last checkpoint before plan generation.

### [5] Plan Generation (Sisyphus Format)

Write the plan to `.sisyphus/plans/pr-<N>-review.md`.

**Process**:
1. AI drafts the plan from the final confirmed table
2. **Metis** reviews the draft: finds ambiguity, omissions, hidden AI failure points
3. **Momus** reviews the draft: checks clarity, verifiability, completeness, actionability
4. AI applies corrections from both reviews and writes the final plan

**Plan structure**:

```markdown
# PR #N Review Plan

## Context
- PR: <url>
- Branch: <branch>
- Analyzed: <timestamp>
- Actionable: X | To fix: Y

## Tasks

### Task 1: Comment #M — <summary>
- **Dev**: <changes needed, with file paths and line numbers>
- **Test**: <test strategy>
- **Reply**: <inline/review/top_level> → @<author> "template"
- **Deps**: []

### Task 2: ...

## Skipped Comments
- Comment #K: <conclusion> — <reason>

## Dependencies
- Tasks 1..N independent unless otherwise noted
```

### [6] Handoff to /start-work

User runs `/start-work` to load the plan and execute tasks. Each task:
1. Creates an isolated workspace (git worktree)
2. Implements the change
3. Runs targeted tests and checks
4. Replies to the PR comment inline (or as conversation comment)
5. Commits locally (no push)

Do not proceed beyond plan generation. The `/start-work` session handles execution.

## Interaction Checklist

| Step | Gate | Condition |
|------|------|-----------|
| 3 | Overview confirmed | User accepts or remains silent after 🔴 items discussed |
| 4 | Final table confirmed | User explicitly confirms ("ok", "go ahead") |
| 5 | Plan approved | Metis + Momus reviews pass |

## Key Principles

- **AI is analyst, user is decider**. The skill classifies and suggests conclusions, but the user makes final calls, especially on `needs_clarification` and high-risk items.
- **Good classification saves time**. Accurate `informational` tagging and correct conclusions reduce review cycles.
- **Every non-informational comment gets a conclusion**. No actionable comment is left without a disposition in the final table.
- **Plan must be cleanly executable**. Metis and Momus exist to catch plans that would waste time on ambiguity or missing context.
- **Silence is consent by default**. Uncontested items proceed on AI recommendation. If the user wants stricter oversight, they can request item by item review.
- **The two-phase split exists for a reason**. Do not collapse phase 2 into phase 1. Plan generation is the boundary; execution follows separately via `/start-work`.

## Quick Commands

```bash
# Auto-detect PR, collect comments
python3 ./scripts/list_comments.py --json

# Manual PR override
python3 ./scripts/list_comments.py --pr <N> --json

# Include resolved inline threads
python3 ./scripts/list_comments.py --json --include-resolved
```
