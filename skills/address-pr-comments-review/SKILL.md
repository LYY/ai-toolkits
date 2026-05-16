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

**Platform lock**: OpenCode + OhMyOpenCode (Sisyphus) only. Dossier placement and Prometheus → `/start-work` flow are Sisyphus-specific. Not compatible with other agent platforms (Claude Code, Cursor, Gemini CLI, etc.).

**Self-contained**: uses its own `scripts/list_comments.py` (vendored, no Python package dependencies; requires `gh` CLI).

## Prerequisites

- `gh` CLI installed and authenticated (`gh auth status` must pass)
- OpenCode + OhMyOpenCode (Sisyphus) environment
- Current git branch has an open PR, or you know the PR number

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
[2] Classify + validate (per comment analysis)
    ↓
[2.5] Cross-reference check (duplicates / conflicts / relations)
    ↓
[3] Overview table → interactive confirmation (silence = consent)
    ↓   discussion complete
[4] Final confirmation table → user approves
    ↓   approved
[5] Generate review dossier → write to .sisyphus/notepads/pr-<N>-dossier/dossier.md
    ↓
[6] User switches to Prometheus, gives dossier → interactive plan generation → /start-work executes
```

### [1] Collect Comments

```bash
python3 ./scripts/list_comments.py --json
```

The script auto-detects the PR from the current branch via `gh pr view`. Override with `--pr <N>`. For cross-repo access (when not running from the repo directory), use `--repo owner/name`. Include resolved threads with `--include-resolved`.

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
| `already_replied` | Comment already has a human reply — skip |
| `out_of_scope` | Outside this PR's scope |
| `needs_clarification` | Need reviewer input to proceed |

**Discussion flag**: Comments with `needs_clarification` or high-risk `valid` items get marked 🔴.

**Edge cases**:

| Situation | Handling |
|-----------|----------|
| Comment is minimized (hidden) | Treat as `informational` — no action. GitHub UI hides it; reviewer likely retracted it. |
| Author is deleted/ghost | Still classify normally. If actionable, reply still goes to the thread even though author is gone. |
| Empty body | Treat as `informational` — no content to act on. |
| Comment from PR author themselves | Still classify by content. Self-review notes can be `informational` or `actionable` depending on content. |
| Comment has `has_replies: true` from `list_comments.py` | Classify as `already_replied`. The script detected a non-bot reply in the thread (inline) or a subsequent reply comment/review (review body / top-level). User can override in Step 3 if they want to re-address. |

**Classification → Dossier section mapping**:

| Intent | Conclusion | Dossier Section | Action |
|--------|-----------|-----------------|--------|
| actionable | `valid` | Section A | Code change + test + reply + commit |
| actionable | `invalid` | Section B | Reply only (explain why) |
| actionable | `already_fixed` | Section B | Reply only (confirm already fixed) |
| actionable | `already_replied` | Section C | No action — already handled |
| actionable | `out_of_scope` | Section B | Reply only (suggest follow-up if needed) |
| actionable | `needs_clarification` | Section B | Reply only (with resolved direction) |
| informational | — | Section C | No action at all |

### [2.5] Cross-Reference Check

**Before presenting the overview table**, scan all classified comments for cross-comment patterns. Multiple reviewers (copilot, bot, human) often flag the same issue or give conflicting advice.

#### Detect Duplicates

Two or more comments point to the **same file + same line + same issue** or substantially overlapping concerns:

| Signal | Example |
|--------|---------|
| Same `path:line` | Both @copilot and @alice flag `foo.ts:42` |
| Different line, same function | `foo.ts:42` and `foo.ts:47` both in `handleSubmit()` |
| Same semantic issue | "null check missing" and "add guard clause" on same code block |

**Action**: Merge duplicates into one entry in the overview table. List all authors as "noted by @X, @Y". Assign the most specific conclusion (e.g., if one says `valid` and another says `valid`, keep one `valid`; if opinions differ, see Conflicts below).

#### Detect Conflicts

Two or more comments on the **same code** with **opposing or incompatible recommendations**:

| Signal | Example |
|--------|---------|
| Opposite changes | @alice: "use const" vs @bob: "use let for reassignment" |
| Incompatible approaches | @copilot: "extract to helper" vs @alice: "inline for clarity" |
| Different conclusions | @bot says `valid`, @human says `invalid` on same issue |

**Action**: Merge into one entry, mark 🔴 for discussion, present both options:

```
| 3 | @alice vs @bob | inline | foo.ts:42 | var declaration choice | ⚠️ conflict | 🔴 resolve |
```

During Step 3 discussion, present both sides and ask user to choose.

#### Detect Related Comments

Comments on **different files/lines** that are **causally or logically connected**:

| Signal | Example |
|--------|---------|
| Call chain | Comment A on `foo.ts:42` (callee), Comment B on `bar.ts:15` (caller) |
| Shared type/interface | Both touch the same struct/type definition |
| Sequential workflow | Fixing A might make B's concern irrelevant |

**Action**: Note the relationship in the overview table. In the dossier, add dependency notes so plan mode can order tasks or group related changes.

#### Detect Already-Replied Comments

`list_comments.py` now outputs a `has_replies` field for every comment:

| Comment kind | Detection method |
|-------------|-----------------|
| inline | Review thread has > 1 comment AND at least one is from a non-AI author |
| review body | A subsequent issue comment or COMMENT review exists by a different non-bot author |
| top_level | Same as review body — subsequent issue comment by a different non-bot author |

**Action**: Comments with `has_replies: true` are classified as `already_replied` and placed in Section C (no action). The overview table should note these with a `↩ already replied` indicator so the user is aware. User can override in Step 3 by reclassifying as `valid` or another conclusion.

### [3] Overview Table + Interactive Confirmation

Present the full analysis in a structured table. **Apply [2.5] cross-reference results**: merged duplicates appear as single entries with multiple authors, conflicts are flagged 🔴.

```
## PR #N Comment Analysis — X total (Y raw), Z actionable (after dedup)

### Overview
| # | 来源 | 类型 | 文件 | 摘要 | 结论 | 去重/冲突 | 讨论 |
|---|------|------|------|------|------|-----------|------|
| 1 | @alice, @copilot | inline | foo.ts:42 | var → const | valid | ≡ merged (2 reviews) | |
| 2 | @bot   | inline | bar.ts:15 | rename suggestion | invalid | | |
| 3 | @alice vs @bob | inline | baz.ts:8 | const vs let choice | ⚠️ conflict | ↯ conflicting advice | 🔴 resolve |
| 4 | @human | inline | qux.ts:3 | logic question | needs_clarification | | 🔴 needs input |
| 5 | @reviewer | review | — | LGTM but note on perf | already_replied | ↩ already replied | |

Legend:
- ≡ merged — duplicate comments combined into one entry
- ↯ conflict — opposing recommendations, user must choose
- ↩ already replied — comment already has a human reply; skipped by default
- 🔴 resolve — needs user decision before proceeding

### 🔴 Needs Discussion (N items)
Expand each 🔴 item with context. For conflicts, present both sides:

**Comment #3 — Conflict on baz.ts:8**:
- @alice suggests: `const result = await fetch()` (immutable)
- @bob suggests: `let result = await fetch()` (may reassign later)
- Current code uses `var`. Both agree it should change, disagree on replacement.
- Which approach? (const / let / other)

### 📝 Silent Consent (M items)
Items without 🔴 are accepted as-is per AI conclusion. Speak up if you disagree.
```

**Interaction rules**:
- Silence = consent. If user says "continue", "ok", "go ahead", or doesn't object — assume agreement with AI conclusions.
- User can object to specific items by number. Discuss and update the conclusion.
- `needs_clarification` items require explicit user direction. Do not proceed without it.
- Discuss 🔴 items first, then confirm the rest are accepted.

**Scaling for large PRs** (20+ actionable comments):

| Problem | Solution |
|---------|----------|
| Overview table too long | Show 🔴 items inline, collapse 📝 items to a summary line: "12 silent-consent items (see dossier for details)" |
| Too many 🔴 to discuss at once | Batch into groups of 5-7, discuss one batch at a time |
| User overwhelmed | Offer to prioritize: "Should we discuss CRITICAL/high-risk items first, then handle the rest in silent consent?" |
| Dossier would be enormous | Section A/B items are already individual — plan mode handles scale. Dossier length is expected for large PRs. |

### [4] Final Confirmation Table

After all discussion converges, produce an updated table reflecting every outcome. All 🔴 items must be resolved (conclusion changed or confirmed).

**Include a change summary** so the user can quickly see what changed from Step 3:

```
## Changes from Step 3
- #2: conclusion changed from `valid` to `invalid` (discussion: doesn't apply after all)
- #3: conflict resolved — chose @alice's `const` approach, rejecting @bob's `let`
- #5: split from merged entry #4 (discussion revealed different issues)
- #7: conclusion changed from `needs_clarification` → `valid` (user provided direction)

### Final Overview
| # | ... (updated table with all changes applied) |
```

User explicitly confirms with "ok" or equivalent.

This is the last checkpoint before dossier generation.

### [5] Generate Review Dossier

**Do NOT generate a plan here.** The skill produces a dossier — a comprehensive requirements document based on everything confirmed in Steps 2-4. Plan generation happens in the next phase via an interactive Prometheus conversation (which has built-in Metis gap analysis and Momus review).

**CRITICAL — Final Cross-Reference Scan**: Before writing the dossier, re-scan the **final confirmed table** (from Step 4) against the original cross-reference results (from Step 2.5). Discussion may have changed conclusions, revealed new connections, or created new duplicates.

Run through this checklist:

| Check | What to look for | Action if found |
|-------|-----------------|-----------------|
| **New duplicates** | Two entries with same file:line but different # numbers after discussion renumbering | Merge into one entry, update counts |
| **Stale duplicates** | Two entries were merged in Step 2.5, but discussion changed one conclusion (e.g., `valid` → `invalid`) — they may no longer be duplicates | Split back to separate entries with their new conclusions |
| **Unresolved conflicts** | Any entry still marked 🔴 or ↯ without a user decision recorded | **STOP. Do not proceed.** Return to Step 3 for resolution |
| **Orphaned replies** | A comment was marked `valid` in Step 2 but changed to `invalid` during discussion — does its duplicate partner still need the code change? | Verify the remaining entry is correctly classified |
| **New relations** | Discussion revealed that fixing Comment #X will also fix Comment #Y's concern (not duplicate, but related) | Add dependency note: "Task Y may become unnecessary after Task X" |
| **Cross-section leakage** | A comment in Section A (code change) actually only needs a reply based on final discussion | Move to Section B |
| **Reply target mismatch** | Merged duplicates — all authors listed? Each has an `in_reply_to` ID? | Verify all authors are accounted for |
| **Stale already_replied** | A comment was marked `already_replied` in Step 2, but discussion revealed the reply was insufficient or from a bot | Reclassify as `valid`, `invalid`, etc. |

**Gate rule**: If any 🔴 item remains unresolved, do NOT write the dossier. Return to Step 3. If all checks pass, proceed.

Write the dossier to `.sisyphus/notepads/pr-<N>-dossier/dossier.md`. Create the directory if it doesn't exist.

**Dossier structure**:

```markdown
# Review Dossier: PR #N — {{PR_TITLE}}

> **For Prometheus**: Read this dossier and generate an execution plan for `/start-work`.
> All decisions confirmed below. Ask clarifying questions if any task is ambiguous.
> *Minimum requirements: no same-file concurrency, precise test names, scope guardrails per task, reply-only tasks locked down, final verification wave. How you achieve these is up to you.*

## Executive Summary
| Category | Count | Action |
|----------|-------|--------|
| Needs code change + reply | N | Modify code, run tests, reply inline, commit |
| Needs reply only | M | Reply inline with explanation, no code changes |
| Already replied (skip) | R | Already has a human reply — no action needed |
| Informational (skip) | K | No action |
| **Total plan tasks** | **N+M** | **code tasks + reply tasks** |
| **Raw comments (before dedup)** | T | Original count from list_comments.py |
| **Merged duplicates** | D | Comments merged into others above |
| **Conflicts resolved** | C | User chose one direction among conflicting advice |

## Dedup & Conflict Notes

| Type | Count | Details |
|------|-------|---------|
| Duplicates merged | D | Comments #X, #Y merged into Task A due to same file:line |
| Conflicts resolved | C | Comment #X vs #Y: user chose @alice's approach over @bob's |

## Context
- PR: {{PR_URL}}, Branch: {{BRANCH}}, Repo: {{REPO}}, Analyzed: {{TIMESTAMP}}

---

## A. Comments Requiring Code Change + Reply (N items)

### Comment #{{ID}}: {{SUMMARY}}
- **Source**: @{{AUTHOR}} | {{KIND}} | {{FILE_PATH}}:{{LINE}}
- **Also noted by**: @{{DUP_AUTHOR1}}, @{{DUP_AUTHOR2}} (omit if no duplicates)
- **Conclusion**: `valid`
- **What to change**: {{DEV_CHANGES}} (exact file paths, line numbers, specific code modification)
- **How to test**: {{TEST_STRATEGY}} (specific test commands, expected output)
- **Reply after fix**: {{REPLY_KIND}} → @{{AUTHOR}} (reply to ALL authors who raised this issue)

  **Choose endpoint by reply kind** (NOT all inline):
  ```bash
  # inline:
  gh api repos/{{REPO}}/pulls/{{PR}}/comments --method POST \
    -F body="{{REPLY_TEXT}}" -F commit_id=$(git rev-parse HEAD) \
    -F path="{{FILE_PATH}}" -F line={{LINE}} -F side=RIGHT \
    -F in_reply_to={{COMMENT_ID}}

  # review body:
  gh api repos/{{REPO}}/issues/{{PR}}/comments --method POST \
    -F body="@{{AUTHOR}} {{REPLY_TEXT}}"

  # top_level:
  gh api repos/{{REPO}}/issues/{{PR}}/comments --method POST \
    -F body="{{REPLY_TEXT}}"
  ```
- **Reply to duplicate authors**: Same reply, directed to @{{DUP_AUTHOR}} via their own `in_reply_to` ID
- **Commit message**: `{{SUGGESTED_COMMIT_MESSAGE}}`

---

## B. Comments Requiring Reply Only (M items)

**No code changes needed.** Each item only requires an inline reply explaining the decision. No tests, no commits.

### Comment #{{ID}}: {{SUMMARY}}
- **Source**: @{{AUTHOR}} | {{KIND}} | {{FILE_PATH}}:{{LINE}}
- **Conclusion**: `{{CONCLUSION}}` — {{RATIONALE}}
- **Reply**: {{REPLY_KIND}} → @{{AUTHOR}}

  **Choose endpoint by reply kind** (NOT all inline):
  ```bash
  # inline:
  gh api repos/{{REPO}}/pulls/{{PR}}/comments --method POST \
    -F body="{{REPLY_TEXT}}" -F commit_id={{COMMIT_SHA}} \
    -F path="{{FILE_PATH}}" -F line={{LINE}} -F side=RIGHT \
    -F in_reply_to={{COMMENT_ID}}

  # review body:
  gh api repos/{{REPO}}/issues/{{PR}}/comments --method POST \
    -F body="@{{AUTHOR}} {{REPLY_TEXT}}"

  # top_level:
  gh api repos/{{REPO}}/issues/{{PR}}/comments --method POST \
    -F body="{{REPLY_TEXT}}"
  ```

  **Note**: `{{COMMIT_SHA}}` for reply-only tasks = the PR branch's HEAD commit (use `git rev-parse HEAD` in the PR branch). No new commit is created, but inline replies require a valid commit SHA on the PR branch.

---

## C. Informational & Already-Replied Comments — No Action (K + R items)

No code changes. No replies. LGTM, praise, emoji-only, FYI, and already-replied comments.

| # | Source | Kind | Summary | Reason |
|---|--------|------|---------|--------|
| {{ID}} | @{{AUTHOR}} | {{KIND}} | {{SUMMARY}} | {{informational / already_replied}} |

---

## Reply Templates (Reference for Plan Mode)
| Outcome | Reply |
|---------|-------|
| valid (fixed) | `Fixed in <commit_sha>.` |
| invalid | `This suggestion doesn't apply because <brief reason>.` |
| already_fixed | `Already resolved in the current code — no changes needed.` |
| out_of_scope | `This is outside the scope of this PR. <Optional: suggest follow-up>.` |
| needs_clarification | `Confirmed: <resolved direction>.` (direction resolved during Step 3 discussion — unlike auto skill where reply asks the question) |
| conflict (not chosen) | `Thanks for the suggestion. We went with @other's approach for <reason>.` |

---

## Cross-Reference Checks

| Check | Status |
|-------|--------|
| New duplicates | {{NEW_DUP_CHECK}} |
| Stale duplicates | {{STALE_DUP_CHECK}} |
| Unresolved conflicts | {{UNRESOLVED_CONFLICT_CHECK}} |
| Orphaned replies | {{ORPHANED_REPLY_CHECK}} |
| New relations | {{NEW_RELATION_CHECK}} |
| Cross-section leakage | {{CROSS_SECTION_CHECK}} |
| Reply target mismatch | {{REPLY_TARGET_CHECK}} |
| Stale already_replied | {{STALE_ALREADY_REPLIED_CHECK}} |

## Dependencies

{{DEPENDENCIES}}

If related comments exist (call chain, shared type), note here:
- Task X and Task Y both modify `shared_type.go` — coordinate changes.
- Task A is a callee of Task B's caller — order: fix callee first, then caller.
- Fixing Task X may make Task Y unnecessary — verify after X is complete.

## Scope Guardrails

These constraints prevent scope creep. Prometheus bakes them into every task.

| Rule | Rationale |
|------|-----------|
| {{GUARDRAIL_1}} | {{RATIONALE_1}} |
| {{GUARDRAIL_2}} | {{RATIONALE_2}} |

Common guardrails: no vendor/ refresh, no global refactors beyond the fix, reply-only tasks must not modify code or run tests.
```

**Rules for dossier content**:
- Every `valid` comment goes in **Section A** (code change + reply + test + commit).
- Every `invalid` / `already_fixed` / `out_of_scope` / `needs_clarification` comment goes in **Section B** (reply only). These are NOT "skipped" — the reviewer is waiting for a response explaining why.
- Only `informational` comments (LGTM, praise, emoji, FYI) and `already_replied` comments (already has a human reply) go in **Section C** (truly no action).
- For Section A: exact file paths, line numbers, specific code change description, test strategy with commands, reply template, and suggested commit message are ALL required.
- For Section B: each item must include the conclusion rationale and exact reply text. Include gh api commands with `in_reply_to` for inline replies.
- **Duplicate handling**: When comments #X and #Y are merged (same file:line, same issue), produce ONE task entry. List all authors. Reply to EACH author individually using their own `in_reply_to` ID. Note the merge in Dedup & Conflict Notes.
  - All duplicate authors get the same reply content (the fix was applied / the conclusion stands).
  - Each reply uses the author's own comment ID as `in_reply_to`. Do NOT use the same ID for multiple replies.
  - For 3+ duplicates: list all IDs explicitly in the task so plan mode can loop.
- **Conflict handling**: When user resolves a conflict (choosing @A's approach over @B's), the chosen direction goes in Section A (or B). The rejected direction goes in Section B as a reply-only item: explain to the rejected reviewer why their approach wasn't taken.
- **Related comments**: When two tasks are causally related (call chain, shared type), add dependency notes below. Plan mode will use these to order tasks or group related changes.
- Be exhaustive. Prometheus and Atlas operate with zero business context — the dossier is their only source of truth.

**After writing the dossier**, verify:

| Check | Command/Condition |
|-------|-------------------|
| File exists | `test -f .sisyphus/notepads/pr-<N>-dossier/dossier.md` |
| Valid markdown | File starts with `# Review Dossier:` |
| Counts match | Executive Summary counts = actual items in each section |
| No placeholder left | No `{{...}}` template variables remain — all should be substituted |
| Reply endpoint correct | Each reply task uses the endpoint matching its `{{REPLY_KIND}}` (inline/review/top_level) |

If any check fails, fix and re-verify before proceeding to Step 6.

### [6] Handoff — Next Steps

After dossier is saved, output:

```
Dossier saved to .sisyphus/notepads/pr-<N>-dossier/dossier.md

Next: switch to Prometheus mode and have a conversation. Paste the dossier
path and ask Prometheus to generate an execution plan. Interactive
conversation produces better plans than one-shot @plan — Prometheus can
ask clarifying questions, refine task granularity, and add precise file
paths and test commands.

After Prometheus writes the plan, review it, then run /start-work to execute.
```

**Do NOT run `@plan` or `/start-work` yourself.** The skill's job ends at dossier generation. The user controls when to proceed.

**What happens next (user-driven)**:
1. User switches to Prometheus mode (e.g., `@plan` to enter plan context, or directly invoke Prometheus).
2. User gives Prometheus the dossier: "Read `.sisyphus/notepads/pr-<N>-dossier/dossier.md` and generate an execution plan. Ask me if any task is ambiguous."
3. Prometheus reads the dossier, asks clarifying questions, refines task structure and execution details.
4. Prometheus writes the plan to `.sisyphus/plans/pr-<N>-review.md`.
5. User reviews the plan. Optionally run Momus review for gap analysis.
6. User reviews and approves (`ok`), then runs `/start-work` — Atlas executes per-comment tasks.

**Why interactive Prometheus over one-shot `@plan`**:
- Prometheus can ask follow-up questions about ambiguous file paths or test strategies.
- Interactive refinement produces better task granularity and parallel execution annotations.
- Direct conversation gives Prometheus more context to fill gaps the dossier might miss.

**After `/start-work` completes**:
- Review the generated commits (`git log --oneline`).
- `git push` the branch.
- Verify that replies appear correctly on the PR (check a few random comment threads).
- If anything was missed, re-run this skill — already-replied comments will be automatically skipped via `has_replies` detection.

**If `/start-work` fails mid-execution** (partial tasks complete, partial fail):
1. Check which tasks succeeded via `git log --oneline` (committed tasks) and the PR comment threads (replied tasks).
2. Re-run this skill — completed tasks with replies will be automatically detected as `already_replied` and skipped.
3. The skill will produce a new dossier containing only the remaining unhandled items.
4. Generate a new plan (Prometheus) and re-run `/start-work`.

## Interaction Checklist

| Step | Gate | Condition |
|------|------|-----------|
| 2.5 | Cross-reference scanned | Duplicates merged, conflicts flagged, relations noted, already-replied detected |
| 3 | Overview confirmed | User accepts or remains silent after 🔴 items discussed |
| 4 | Final table confirmed | User explicitly confirms ("ok", "go ahead") |
| 5 (before write) | Final cross-reference scan | All 7 checks pass, no unresolved 🔴 items remain |
| 5 | Dossier written | `.sisyphus/notepads/pr-<N>-dossier/dossier.md` exists and is complete |
| 6 | Handoff delivered | User sees next-step instructions with Prometheus conversation + `/start-work` |

## Key Principles

- **AI is analyst, user is decider**. The skill classifies and suggests conclusions, but the user makes final calls, especially on `needs_clarification` and high-risk items.
- **Good classification saves time**. Accurate `informational` tagging and correct conclusions reduce review cycles.
- **Every non-informational comment gets a conclusion AND a reply.** No actionable comment is left without a disposition in the final table — and no non-informational comment is left without a reply task in the dossier (Section A or B). Exception: `already_replied` comments go to Section C.
- **"Skipped" only means informational or already-replied.** `invalid`/`already_fixed`/`out_of_scope`/`needs_clarification` go in Section B (Reply Only), NOT in Section C. The reviewer is waiting for a response. Only `informational` and `already_replied` go in Section C.
- **Dossier is the boundary and the single source of truth.** The skill produces a dossier, not a plan. The dossier captures everything confirmed in Steps 2-4 — classification decisions, file paths, test strategies, reply templates. Plan generation happens in the next phase: an interactive Prometheus conversation. Prometheus can ask clarifying questions, but dossier should minimize back-and-forth — the less it has to guess, the better the plan.
- **Silence is consent by default**. Uncontested items proceed on AI recommendation. If the user wants stricter oversight, they can request item by item review.
- **Three phases, not two**. Phase 1 = dossier (this skill). Phase 2 = plan (interactive Prometheus conversation). Phase 3 = execute (`/start-work` via Atlas). Never collapse phases.
- **Duplicates are detected, not created**. Cross-reference check (Step 2.5) merges same file:line issues into single tasks. Plan mode must never see two tasks modifying the same line for the same reason.
- **Conflicts are surfaced, not buried**. Opposing reviewer advice is flagged 🔴 during interaction and documented in the dossier — chosen direction in Section A/B, rejected direction with explanation in Section B.
- **Final scan is mandatory**. Discussion changes things. The cross-reference scan at the start of Step 5 catches new duplicates, stale merges, and unresolved conflicts that emerged during conversation. Never skip this gate.

## Quick Commands

```bash
# Auto-detect PR, collect comments
python3 ./scripts/list_comments.py --json

# Manual PR override
python3 ./scripts/list_comments.py --pr <N> --json

# Cross-repo PR (when not in the repo directory)
python3 ./scripts/list_comments.py --repo owner/name --pr <N> --json

# Include resolved inline threads
python3 ./scripts/list_comments.py --json --include-resolved
```

Reply commands are generated per-task in the dossier (Section A for code changes, Section B for reply-only). See `references/dossier-template.md` for the endpoint selection table.
