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
- **Phase 2**: user invokes Sisyphus plan mode (`@plan`) with the dossier — Prometheus generates a proper execution plan (with built-in Metis gap analysis + Momus review).
- **Phase 3**: user runs `/start-work` to execute the plan in isolated workspaces.

**Platform lock**: OpenCode + OhMyOpenCode (Sisyphus) only. Dossier placement and `@plan` → `/start-work` flow are Sisyphus-specific. Not compatible with other agent platforms (Claude Code, Cursor, Gemini CLI, etc.).

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
[5] Generate review dossier → write to .sisyphus/notepads/pr-<N>-dossier/dossier.md
    ↓
[6] User runs @plan with dossier → Prometheus generates plan → /start-work executes
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

**CRITICAL**: Read the **full `body`** field from the JSON output, not just `excerpt`. The excerpt is truncated to 220 characters and may cut off the actual content of long review comments. Always use `body` for classification decisions.

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

**Classification → Dossier section mapping**:

| Intent | Conclusion | Dossier Section | Action |
|--------|-----------|-----------------|--------|
| actionable | `valid` | Section A | Code change + test + reply + commit |
| actionable | `invalid` | Section B | Reply only (explain why) |
| actionable | `already_fixed` | Section B | Reply only (confirm already fixed) |
| actionable | `out_of_scope` | Section B | Reply only (suggest follow-up if needed) |
| actionable | `needs_clarification` | Section B | Reply only (with resolved direction) |
| informational | — | Section C | No action at all |

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

This is the last checkpoint before dossier generation.

### [5] Generate Review Dossier

**Do NOT generate a plan here.** The skill produces a dossier — a comprehensive requirements document. Plan generation is handled by Sisyphus plan mode (Prometheus) in the next phase, which has built-in Metis gap analysis and Momus review.

Write the dossier to `.sisyphus/notepads/pr-<N>-dossier/dossier.md`. Create the directory if it doesn't exist.

**Dossier structure**:

```markdown
# Review Dossier: PR #N — {{PR_TITLE}}

> **For Prometheus plan mode**: Read this dossier to generate the execution plan.
> No further interview needed — all decisions are confirmed below.

## Executive Summary
| Category | Count | Action |
|----------|-------|--------|
| Needs code change + reply | N | Modify code, run tests, reply inline, commit |
| Needs reply only | M | Reply inline with explanation, no code changes |
| Informational (skip) | K | No action |
| **Total tasks for plan** | **N+M** | **code tasks + reply tasks** |

## Context
- PR: {{PR_URL}}, Branch: {{BRANCH}}, Repo: {{REPO}}, Analyzed: {{TIMESTAMP}}

---

## A. Comments Requiring Code Change + Reply (N items)

### Comment #{{ID}}: {{SUMMARY}}
- **Source**: @{{AUTHOR}} | {{KIND}} | {{FILE_PATH}}:{{LINE}}
- **Conclusion**: `valid`
- **What to change**: {{DEV_CHANGES}} (exact file paths, line numbers, specific code modification)
- **How to test**: {{TEST_STRATEGY}} (specific test commands, expected output)
- **Reply after fix**: {{REPLY_KIND}} → @{{AUTHOR}}
  ```bash
  gh api repos/{{REPO}}/pulls/{{PR}}/comments --method POST \
    -F body="{{REPLY_TEXT}}" -F commit_id=$(git rev-parse HEAD) \
    -F path="{{FILE_PATH}}" -F line={{LINE}} -F side=RIGHT \
    -F in_reply_to={{COMMENT_ID}}
  ```
- **Commit message**: `{{SUGGESTED_COMMIT_MESSAGE}}`

---

## B. Comments Requiring Reply Only (M items)

**No code changes needed.** Each item only requires an inline reply explaining the decision. No tests, no commits.

### Comment #{{ID}}: {{SUMMARY}}
- **Source**: @{{AUTHOR}} | {{KIND}} | {{FILE_PATH}}:{{LINE}}
- **Conclusion**: `{{CONCLUSION}}` — {{RATIONALE}}
- **Reply**: {{REPLY_KIND}} → @{{AUTHOR}}
  ```bash
  gh api repos/{{REPO}}/... (same endpoint selection as section A)
  ```

---

## C. Informational Comments — No Action (K items)

No code changes. No replies. LGTM, praise, emoji-only, FYI.

| # | Source | Kind | Summary |
|---|--------|------|---------|
| {{ID}} | @{{AUTHOR}} | {{KIND}} | {{SUMMARY}} |

---

## Reply Templates (Reference for Plan Mode)
| Outcome | Reply |
|---------|-------|
| valid (fixed) | `Fixed in <commit_sha>.` |
| invalid | `This suggestion doesn't apply because <brief reason>.` |
| already_fixed | `Already resolved in the current code — no changes needed.` |
| out_of_scope | `This is outside the scope of this PR. <Optional: suggest follow-up>.` |
| needs_clarification | `Confirmed: <resolved direction>.` |
```

**Rules for dossier content**:
- Every `valid` comment goes in **Section A** (code change + reply + test + commit).
- Every `invalid` / `already_fixed` / `out_of_scope` / `needs_clarification` comment goes in **Section B** (reply only). These are NOT "skipped" — the reviewer is waiting for a response explaining why.
- Only `informational` comments (LGTM, praise, emoji, FYI) go in **Section C** (truly no action).
- For Section A: exact file paths, line numbers, specific code change description, test strategy with commands, reply template, and suggested commit message are ALL required.
- For Section B: each item must include the conclusion rationale and exact reply text. Include gh api commands with `in_reply_to` for inline replies.
- Be exhaustive. Prometheus and Atlas operate with zero business context — the dossier is their only source of truth.

### [6] Handoff — Next Steps

After dossier is saved, output:

```
Dossier saved to .sisyphus/notepads/pr-<N>-dossier/dossier.md

Next: activate Sisyphus plan mode (@plan) to generate the execution plan from this dossier.
Prometheus will handle Metis gap analysis and Momus review internally.
Then run /start-work to execute.
```

**Do NOT run `@plan` or `/start-work` yourself.** The skill's job ends at dossier generation. The user controls when to proceed.

**What happens next (user-driven)**:
1. User invokes `@plan "generate execution plan from .sisyphus/notepads/pr-<N>-dossier/dossier.md"`
2. Prometheus reads the dossier, interviews if needed, runs Metis gap analysis
3. Prometheus writes the plan to `.sisyphus/plans/pr-<N>-review.md`
4. User reviews the plan, optionally triggers Momus review
5. User runs `/start-work` — Atlas executes per-comment tasks (dev → test → reply → commit)

## Interaction Checklist

| Step | Gate | Condition |
|------|------|-----------|
| 3 | Overview confirmed | User accepts or remains silent after 🔴 items discussed |
| 4 | Final table confirmed | User explicitly confirms ("ok", "go ahead") |
| 5 | Dossier written | `.sisyphus/notepads/pr-<N>-dossier/dossier.md` exists and is complete |
| 6 | Handoff delivered | User sees next-step instructions with `@plan` + `/start-work`

## Key Principles

- **AI is analyst, user is decider**. The skill classifies and suggests conclusions, but the user makes final calls, especially on `needs_clarification` and high-risk items.
- **Good classification saves time**. Accurate `informational` tagging and correct conclusions reduce review cycles.
- **Every non-informational comment gets a conclusion AND a reply.** No actionable comment is left without a disposition in the final table — and no non-informational comment is left without a reply task in the dossier (Section A or B).
- **"Skipped" only means informational.** `invalid`/`already_fixed`/`out_of_scope`/`needs_clarification` go in Section B (Reply Only), NOT in Section C. The reviewer is waiting for a response.
- **Dossier is the boundary and the single source of truth.** The skill produces a dossier, not a plan. Plan generation belongs to Prometheus. The dossier must be exhaustive — Prometheus and Atlas operate with zero business context.
- **Silence is consent by default**. Uncontested items proceed on AI recommendation. If the user wants stricter oversight, they can request item by item review.
- **Three phases, not two**. Phase 1 = dossier (this skill). Phase 2 = plan (`@plan` via Prometheus). Phase 3 = execute (`/start-work` via Atlas). Never collapse phases.

## Quick Commands

```bash
# Auto-detect PR, collect comments
python3 ./scripts/list_comments.py --json

# Manual PR override
python3 ./scripts/list_comments.py --pr <N> --json

# Include resolved inline threads
python3 ./scripts/list_comments.py --json --include-resolved
```
