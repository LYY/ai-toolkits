# Dossier & Reply Output Protocol

Step 4 dossier generation, reply policy, and validation gates. Produces the review dossier and governs reply behavior.

---

## Dossier Structure

This file defines the dossier contract: the structure, content rules, evidence requirements, and quality checks for the review dossier generated after successful interaction (Step 4). The dossier is the final deliverable of Phase 1. It is a requirements document that captures every confirmed decision from Steps 2-4 and feeds Prometheus (Phase 2) for execution plan generation.

The dossier opens with an executive summary table:

```markdown
## Executive Summary
| Category | Count | Action |
|----------|-------|--------|
| Needs code change + reply | N | Modify code, run tests, reply inline, commit |
| Needs reply only | M | Reply inline with explanation, no code changes |
| Already replied (skip) | R | Already has a human reply -- no action needed |
| Informational (skip) | K | No action |
| **Total plan tasks** | **N+M** | **code tasks + reply tasks** |
| **Raw comments (before dedup)** | T | Original count from list_comments.py |
| **Merged duplicates** | D | Comments merged into others above |
| **Conflicts resolved** | C | User chose one direction among conflicting advice |
```

### Dedup & Conflict Notes

A single table following the executive summary lists merged duplicates (which comment IDs merged into which task) and resolved conflicts (which comments, whose approach was chosen).

### Context Line

```markdown
## Context
- PR: {{PR_URL}}, Branch: {{BRANCH}}, Repo: {{REPO}}
- Commit style: {{COMMIT_STYLE}} (run `git log --oneline -10`)
- Analyzed: {{TIMESTAMP}}
```

---

## Reply Endpoints

The dossier must include a reference table of `gh api` commands for each reply kind. Reply TEMPLATES are in `reply.md` -- not duplicated here.

**Ownership**: This section owns reply endpoint command templates. Gate logic and verification procedures are defined in Validation Gates below.

```markdown
## Reply Endpoints (shared by Sections A and B)

| Reply Kind | Endpoint | Key Flag |
|------------|----------|----------|
| `inline` | `repos/{owner}/{repo}/pulls/{pr}/comments` | `in_reply_to=<id>` |
| `review` | `repos/{owner}/{repo}/issues/{pr}/comments` | mention @author in body |
| `top_level` | `repos/{owner}/{repo}/issues/{pr}/comments` | -- |

```bash
# inline:
gh api repos/{{REPO}}/pulls/{{PR_NUMBER}}/comments --method POST \
  -F body="{{REPLY_TEXT}}" -F commit_id=$(git rev-parse HEAD) \
  -F path="{{FILE_PATH}}" -F line={{LINE}} -F side=RIGHT \
  -F in_reply_to={{COMMENT_ID}}

# review:
gh api repos/{{REPO}}/issues/{{PR_NUMBER}}/comments --method POST \
  -F body="@{{AUTHOR}} {{REPLY_TEXT}}"

# top_level:
gh api repos/{{REPO}}/issues/{{PR_NUMBER}}/comments --method POST \
  -F body="{{REPLY_TEXT}}"
```

**Commit SHA note**: Inline replies require a valid commit SHA on the PR branch (`git rev-parse HEAD`). `review` and `top_level` replies do not need `commit_id`.
```

---

## Section A: Comments Requiring Code Change + Reply

Section A captures every comment confirmed as requiring a code change and a reply. Each comment becomes one task entry.

### Section A Task Template

```markdown
### Task {{TASK_NUM}}: Comment #{{COMMENT_ID}} -- {{SUMMARY}}
- **Source**: @{{AUTHOR}} | {{KIND}} | {{FILE_PATH}}:{{LINE}}
- **Also noted by**: @{{DUP_AUTHOR1}}, @{{DUP_AUTHOR2}} (omit if no duplicates)
- **Conclusion**: `valid`
- **What to change**: {{DEV_CHANGES}} (exact file paths, line numbers, specific code modification)
- **How to test**: {{TEST_STRATEGY}} (specific test commands, expected output)
- **Reply after fix**: {{REPLY_KIND}} -> @{{AUTHOR}} (use endpoint from Reply Endpoints)
- **Reply to duplicate authors**: Same reply, directed to @{{DUP_AUTHOR}} via their own `in_reply_to` ID
- **Commit message**: `{{SUGGESTED_COMMIT_MESSAGE}}`
```

### Required Fields (ALL Mandatory)

Every Section A entry MUST contain: exact file paths and line numbers, code change description (specific, not general direction), test strategy (specific commands), reply target (kind + author), suggested commit message (imperative mood, matching repo conventions).

### Evidence Requirements

Evidence requirements are defined in `classification.md` (Evidence Requirements section). This section does not repeat them.

---

## Section B: Comments Requiring Reply Only

Section B captures every comment confirmed as needing a reply but no code change. No tests, no commits.

### Section B Task Template

One canonical example. For conflict resolution (rejected direction), add `- **Context**: User chose @A over @B` and set `- **Conclusion**: \`invalid\``.

```markdown
### Task {{TASK_NUM}}: Comment #{{COMMENT_ID}} -- {{SUMMARY}}
- **Source**: @{{AUTHOR}} | {{KIND}} | {{FILE_PATH}}:{{LINE}}
- **Conclusion**: `{{CONCLUSION}}` -- {{RATIONALE}}
- **Reply**: {{REPLY_KIND}} -> @{{AUTHOR}} (use endpoint from Reply Endpoints)
```

### Required Fields (ALL Mandatory)

Conclusion rationale (why no code change), reply target (kind + author), no-code-change constraint (no references to code modifications or test commands).

### Conflict Handling

When user chooses @A's approach over @B's: chosen direction goes to Section A (if code change needed) or Section B (if reply-only); rejected direction goes to Section B with `invalid` conclusion, explaining why the approach was not taken. Both options and the user choice are captured in the entry.

---

## Section C: Informational & Already-Replied Comments -- No Action

Section C captures comments that require no action. No code changes, no replies.

### Section C Table Format

```markdown
| # | Source | Kind | Summary | Reason |
|---|--------|------|---------|--------|
| {{COMMENT_ID}} | @{{AUTHOR}} | {{KIND}} | {{SUMMARY}} | {{informational / already_replied}} |
```

### Section C Rules

`informational` (praise, LGTM, emoji, FYI, nit, retraction), `already_replied` (sufficient human reply), and `minimized` by author go here. No code change, no reply, no follow-up. NOT counted as plan tasks.

---

## Duplicate Handling in Dossier

ONE task entry, ALL authors under "Also noted by", EACH author gets individual reply via own `in_reply_to` ID, same content, merge documented in Dedup & Conflict Notes. For 3+: list all IDs explicitly.

### Duplicate + Cross-File Combination

Primary entry follows cross-file escalation rules; duplicate authors follow duplicate handling. Cross-file pattern is a separate concern, not a duplicate.

## Conflict Handling in Dossier

Chosen direction goes to Section A (code change) or Section B (reply-only). Rejected direction goes to Section B with `invalid` conclusion. Document in Dedup & Conflict Notes. "What to change" references both approaches and explains the choice.

## Cross-Section Leakage Prevention

The dossier contract explicitly forbids these violations:

| Violation | What it looks like | Correct move |
|-----------|-------------------|--------------|
| Code-change task that only needs a reply | Task in Section A but conclusion says `invalid` or `already_fixed` | Move to Section B |
| Reply-only task that implies code changes | Task in Section B but description references code modifications | Move to Section A, or keep in B with note explaining no code change |
| Informational item promoted to actionable | Item in Section C but its conclusion requires action | Move to Section A or B based on conclusion |
| `partially_addressed` placed in Section B | Fix attempt exists but is insufficient -- incorrectly treated as reply-only | Move to Section A (requires code change + reply) |
| Cross-file escalation creates extra Section A tasks | Multiple Section A entries created for the same cross-file pattern | Only the primary commented file is Section A. Remaining files are scope-guardrails |

### Enforcement

The final cross-reference scan (see below) includes a dedicated check for cross-section leakage. If any item is in the wrong section, the scan blocks dossier writing.

---

## Final Cross-Reference Scan (Pre-Write)

Before writing the dossier, re-scan the final confirmed table from Step 4 against the original cross-reference results. Discussion may have changed conclusions, revealed new connections, or created new duplicates.

See below (Section 1: Pre-Dossier Scan) for the complete 8-Check Checklist. Gate enforcement follows below (Section 4: Gate Rules) -- this section defines the checks, below defines how to gate.

### Gate Rule

Any unresolved item blocks dossier writing. Return to Step 3 if blocked. If all pass, proceed. The dossier includes a results table:

```markdown
## Cross-Reference Checks
| Check | Status |
|-------|--------|
| New duplicates | {{NEW_DUP_CHECK}} |
| Stale duplicates | {{STALE_DUP_CHECK}} |
| ... (all 8 checks) | ... |
```

---

## Dependencies

When comments are causally or logically related, capture after Cross-Reference Checks. Types: `fixes_needed_before`, `may_become_unnecessary`, `should_be_grouped`.

```markdown
## Dependencies
- Task X and Y both modify `shared_type.go` -- coordinate changes
- Task A is callee of Task B -- fix callee first
- Fixing X may make Y unnecessary -- verify after X
```

---

## Scope Guardrails

Prevents scope creep. Embedded after Dependencies.

```markdown
## Scope Guardrails
| Rule | Rationale |
|------|-----------|
| {{GUARDRAIL_1}} | {{RATIONALE_1}} |
```

### Default Guardrails

No vendor/dependency refresh, no global refactors, reply-only tasks no code, cross-file: fix only commented file.

### Guardrail Sources

Cross-reference protocol (cross-file Moderate+), interaction protocol (user constraints), `platform.md` defaults.

---

## Post-Write Verification

| Check | Command/Condition |
|-------|-------------------|
| File exists | `test -f .sisyphus/notepads/pr-<N>-dossier/dossier-<TIMESTAMP>.md` |
| Valid markdown | File starts with `# Review Dossier:` |
| Counts match | Executive Summary counts = actual items in each section |
| No placeholder left | No `{{...}}` template variables remain -- all should be substituted |
| Reply endpoint correct | Each reply task uses the endpoint matching its REPLY_KIND (inline/review/top_level) |
| Reply templates referenced correctly | Reply templates are referenced by name, not duplicated inline |

If any check fails, fix and re-verify. Gate enforcement follows Validation Gates below (Section 2: Post-Write Dossier Verification and Section 4: Gate Rules). This section defines the checks; below defines how to gate.

---

## Reply Policy

This file defines the reply policy for responding to PR review comments. It covers when and how to reply, what content is required for each conclusion type, the pre-reply gate that prevents duplicate replies, and when a change summary is mandatory alongside a fix confirmation. It is responsible for ensuring every reply is correctly addressed, properly formatted, directed to the right endpoint, and never sent twice to the same thread.

### Pre-Reply Gate

**Before composing any reply, run this checklist.** The gate exists to prevent the two highest-cost reply failures: replying to a thread that already has a sufficient response, and sending an overconfident `Fixed in <sha>` for a fix that is misleading without context.

#### Gate Checklist

| # | Check | Condition to pass | Action if failed |
|---|-------|-------------------|------------------|
| 1 | **Already replied?** | Does this thread have `has_replies: true` with a substantively sufficient human reply (per cross-reference rules in analyze.md Level 2)? | Do NOT reply. The existing reply already addresses the concern. If the existing reply is insufficient, do NOT reply either -- flag for user override at Step 3. |
| 2 | **Duplicate author?** | Is this comment one of multiple that were merged as duplicates? | Compose ONE reply. Send it to EACH author individually via their own `in_reply_to` ID. Do not reply to only one author. |
| 3 | **Change summary needed?** | Does the conclusion require a change summary alongside the fix confirmation (see Change Summary Rule below)? | Add a change summary before `Fixed in <sha>`. Do not send a bare `Fixed in <sha>` alone. |
| 4 | **Conclusion still valid?** | Has the code state changed since classification (e.g., a new commit was pushed, or the diff shifted)? | Re-verify the conclusion against current HEAD. If the issue no longer exists, reclassify before replying. |

#### Gate Enforcement

If check #1 fails, the reply is blocked entirely. Do not compose, draft, or prepare a reply. Do not look for ways around the block. The existing reply stands unless the user explicitly reclassifies during Step 3.

All four checks must pass before any reply content is written. The gate is evaluated per-author: for duplicate comments, run the gate for each author individually (check #2 ensures the content is the same, but check #1 may differ per author if some threads have replies and others do not).

---

### Change Summary Rule

#### Principle

A pure `Fixed in <sha>` confirmation implies the fix speaks for itself. When the fix is misleading, partial, or directionally non-obvious without context, the commit SHA alone does not satisfy the reviewer's concern. A change summary must accompany the fix reference to explain what changed and why.

#### When `Fixed in <sha>` Alone Is Allowed

- The fix is straightforward and the change is fully described by the commit message
- The reviewer's concern was a single, unambiguous issue and the fix addresses it directly
- Example: "Rename `foo` to `bar`" -> reply "Fixed in abc123." (the commit message "Rename foo to bar" explains the fix)

#### When a Change Summary Is Mandatory

A change summary that describes what was done and why MUST accompany `Fixed in <sha>` in any of these situations:

| Situation | Example | Why pure SHA is misleading |
|-----------|---------|---------------------------|
| **Direction correction** | Reviewer asked to move `CloseAllPublishers()` AFTER `manager.StopAll()`. Current code moved it BEFORE. | The fix exists but makes the problem worse. `Fixed in <sha>` implies the concern was correctly resolved. |
| **Partial fix** | Fix addressed one location but the same pattern exists at N other locations. | The core concern is not fully resolved. `Fixed in <sha>` implies completion. The reply must explain the scope boundary. |
| **Reframed concern** | The fix takes a different approach than the reviewer suggested but achieves the same intent. | The reviewer may not recognize their concern in the alternate implementation. The reply must describe the approach taken. |
| **Non-obvious change** | The fix involves a subtle refactor, a dependency change, or multiple files. | The commit SHA alone does not convey the scope or reasoning. |
| **Cross-file pattern noted** | Only the commented file was fixed; other files with the same pattern remain. | `Fixed in <sha>` implies the pattern is resolved everywhere. The reply must clarify scope boundaries. |

#### Change Summary Format

The change summary precedes or follows the `Fixed in <sha>` line, depending on what needs explaining:

```
Fixed in abc123. The fix changes the shutdown sequence in monitor.go --
CloseAllPublishers() now runs after manager.StopAll() completes,
matching the reviewer's concern about publisher ordering.
```

For partial fixes, the summary must include the scope boundary:

```
Fixed in abc123 (monitor.go only). The same ordering issue exists in
4 other server/* files. A follow-up PR will address the remaining files.
```

For direction corrections, the summary must acknowledge the previous approach was wrong:

```
Corrected the fix direction in abc123. The previous attempt placed
CloseAllPublishers() before StopAll(), which made the ordering worse.
Now runs after StopAll() as intended.
```

---

### Reply Templates Per Conclusion

Each conclusion maps to exactly one reply template. The template is the default; the interaction protocol (Step 3) or the Change Summary Rule may override or extend it.

| Conclusion | Template | Change summary required? | Notes |
|-----------|----------|-------------------------|-------|
| valid (fixed) | `Fixed in <commit_sha>.` | See Change Summary Rule above | Bare SHA only when fix is self-explanatory. Always check the rule. |
| invalid | `This suggestion doesn't apply because <reason>.` | No | Reason is mandatory -- one sentence minimum. |
| already_fixed | `Already resolved in the current code -- no changes needed.` | No | Evidence of the existing fix must be citeable per classification protocol. |
| out_of_scope | `This is outside the scope of this PR. <follow-up>.` | No | Follow-up suggestion is optional but recommended. |
| needs_clarification | `Confirmed: <resolved direction>.` | No | Direction is resolved during Step 3 interaction, unlike auto mode where the reply asks the question. |
| partially_addressed | `Acknowledged. The existing fix at <sha> addresses <X> but does not address <Y>. <Corrected/reworked> in <sha> to <describe correct fix>.` | Yes -- always | See Partial Fix Reply section below for full requirements. |
| conflict (not chosen) | `Thanks for the suggestion. We went with @other's approach for <reason>.` | No | Reason must neutrally explain the choice without disparaging the rejected approach. |

#### Partial Fix Reply (partially_addressed)

When the classification protocol assigned `partially_addressed`, the reply MUST include three components in order:

1. **Acknowledge the existing attempt**: Cite the commit SHA and what it attempted to fix. This shows the reviewer you saw their original feedback was addressed, even if incompletely.

2. **Explain the insufficiency**: State why the existing fix does not resolve the core concern. Reference the specific code lines that remain problematic. Use neutral factual language, not blame.

3. **Describe the correct fix**: State what was done in the new fix (or what will be done). Reference the new commit SHA if the fix is already applied.

Format:

```
The fix at abc123 addressed the CloseAllPublishers() ordering by moving
it before manager.StopAll(), but the reviewer's concern was that close
should happen AFTER stop completes. This rework in def456 moves the
call to the correct position in the shutdown sequence.
```

Do NOT omit the acknowledgment. A `partially_addressed` reply that jumps straight to "Fixed in <sha>" without acknowledging the previous attempt reads as dismissive. The acknowledgment is not optional.

#### Duplicate Author Reply Strategy

When a comment was merged as a duplicate (same concern, multiple authors):

- Compose ONE reply with the same content for all authors
- Send to EACH author individually using their own `in_reply_to` ID
- Do NOT reply to only one author, even if the others are bots
- Do NOT create separate reply tasks for each author in the dossier -- one task, multiple `in_reply_to` IDs

The reply content is identical across authors. The only difference is the `in_reply_to` parameter in the API call. This is a per-`in_reply_to` dispatch, not a per-author content variation.

#### Already-Replied Blocking

When cross-reference rules in analyze.md Level 2 determines a reply is sufficient:

- The reply is blocked. Do not compose, draft, or prepare a reply.
- The existing reply stands. No override without explicit user action at Step 3.
- This applies even if the existing reply is by a different person or takes a different tone. If the reply substantively addresses the concern, it is sufficient.

When cross-reference rules in analyze.md Level 2 determines a reply is NOT sufficient:

- Default to blocked (conservative). The existing thread has activity.
- Flag the insufficiency for the user at Step 3 with a pending indicator.
- Do NOT compose a reply unilaterally. Only proceed if the user explicitly reclassifies the comment.

This two-level approach prevents the agent from overruling an existing reply while giving the user visibility into potentially unresolved threads.

---

### Endpoint Selection (Reference Only)

Endpoint commands are defined in `dossier.md` (Reply Endpoints section). This file does not repeat them.

---

## Validation Gates

This file defines the validation and regression protocol -- the checklists and gate rules that ensure dossier integrity before handoff. It covers: pre-write cross-reference scan, post-write dossier verification, gate rules (🔴 gate, confirmation gate, block procedure), and regression scenarios.

`eval-matrix.md` is the canonical scenario corpus. This file defines the verification gates; `eval-matrix.md` defines the behavioral acceptance criteria.

---

### 1. Pre-Dossier Scan: Final Cross-Reference (Pre-Write)

Before writing the dossier, re-scan the final confirmed table from Step 4 against the original cross-reference results. Discussion may have changed conclusions, revealed new connections, or created new duplicates.

#### 8-Check Checklist

| Check | What to look for | Action if found |
|-------|-----------------|-----------------|
| **New duplicates** | Two entries with same file:line but different # numbers after discussion renumbering | Merge into one entry, update counts |
| **Stale duplicates** | Two entries were merged in cross-reference, but discussion changed one conclusion (e.g., `valid` -> `invalid`) -- they may no longer be duplicates | Split back to separate entries |
| **Unresolved conflicts** | Any entry still marked with a discussion flag without a user decision recorded | **STOP. Do not proceed.** Return to Step 3 for resolution |
| **Orphaned replies** | A comment changed from `valid` to `invalid` during discussion -- does its duplicate partner still need the code change? | Verify the remaining entry is correctly classified |
| **New relations** | Discussion revealed fixing Comment #X will also fix Comment #Y (related, not duplicate) | Add dependency note |
| **Cross-section leakage** | A comment in Section A (code change) actually only needs a reply based on final discussion | Move to Section B |
| **Reply target mismatch** | Merged duplicates -- all authors listed? Each has an `in_reply_to` ID? | Verify all authors accounted for |
| **Stale already_replied** | A comment marked `already_replied` but discussion revealed the reply was insufficient or from a bot | Reclassify |

**Gate rule**: If any unresolved item remains after the scan, do NOT write the dossier. Return to Step 3.

---

### 2. Post-Write Dossier Verification

After writing the dossier file, run these checks.

#### 2.1 File Existence and Integrity

| Check | Command/Condition |
|-------|-------------------|
| File exists | `test -f .sisyphus/notepads/pr-<N>-dossier/dossier-<TIMESTAMP>.md` |
| Valid markdown | File starts with `# Review Dossier:` |
| Counts match | Executive Summary counts = actual items in each section |
| No placeholder left | No `{{...}}` template variables remain |
| Reply endpoint correct | Each reply task uses the endpoint matching its REPLY_KIND (inline/review/top_level) |

#### 2.2 No-Placeholder Leakage Check (Mandatory)

Any unfilled `{{...}}` placeholder means the dossier is incomplete and must be regenerated. Common placeholders: `{{PR_URL}}`, `{{BRANCH}}`, `{{REPO}}`, `{{TIMESTAMP}}`, `{{REPLY_TEXT}}`, `{{FILE_PATH}}`, `{{LINE}}`, `{{COMMENT_ID}}`, `{{DEV_CHANGES}}`, `{{TEST_STRATEGY}}`, `{{NEW_DUP_CHECK}}`, `{{STALE_DUP_CHECK}}`.

**Gate rule**: If any placeholder remains unfilled, do NOT hand off to Prometheus. Regenerate the dossier.

---

### 3. Capability Upgrade Checks

These checks validate that the redesigned skill's new capabilities are working correctly. Each maps to a specific regression scenario in `eval-matrix.md`:

| Capability Check | Maps To |
|------------------|---------|
| `thread_outdated` behavior | Scenarios 1 & 2 |
| `partially_addressed` | Scenario 5 |
| `cross-file` escalation | Scenario 7 |
| `zero-actionable` table | Scenario 4 |
| `duplicate-reply` prevention | Scenario 6 |

See `eval-matrix.md` for scenario-specific verification guidance.

---

### 4. Gate Rules

#### 4.1 The 🔴 Gate

If any 🔴 item remains unresolved after Step 4 interaction (conflicts unresolved, needs_clarification unanswered, high-risk valid items not acknowledged), the skill MUST NOT write the dossier. It must return to Step 3 for further discussion. This is a hard gate -- no override, no workaround.

#### 4.2 Confirmation Gate

Step 3 user confirmation is required before Step 4 dossier generation. Confirmation equivalents: "ok", "yes", "looks good", "proceed", "confirmed", or any affirmative response. If the user does not explicitly confirm, the skill must ask: "Shall I proceed with dossier generation based on this final table?" Dossier generation must not proceed without explicit confirmation.

#### 4.3 How to Block

When a check fails:
1. **State the failure**: "Validation check failed: [check name]. [Detail of what was found]."
2. **Explain the consequence**: "This means the dossier cannot be written / the handoff cannot proceed."
3. **Provide the corrective action**: "Return to Step [N] and [specific fix]."
4. **Do NOT proceed until the check passes.**

---

### 5. Regression Scenarios

`eval-matrix.md` is the canonical scenario corpus. This file defines the verification gates; `eval-matrix.md` defines the behavioral acceptance criteria. The following reference table provides a quick lookup for each scenario; the full 4-dimension specification (expected classification, reply posture, overview-table treatment, dossier escalation) lives in `eval-matrix.md`.

#### 5.1 Scenario Reference Table

| # | Token | Source | Key Failure Pattern | Validation Item |
|---|-------|--------|--------------------|-----------------|
| 1 | `thread_outdated unresolved` | PR #1215, `discussion_r3257258893` | Conflating `thread_outdated` with `minimized`; skipping code verification | Must read current code at path:line before classifying; must NOT short-circuit to `informational` |
| 2 | `thread_outdated + thread_resolved` | Synthetic | Assuming `thread_outdated` = already fixed without verifying | Both flags together still require code verification; neither flag is evidence of fix-state |
| 3 | `minimized comment` | SKILL.md Step 2 edge cases | Treating as actionable; replying to retracted comment | Must classify as `informational`; no code verification needed; no reply; no dossier entry beyond Section C |
| 4 | `zero-actionable` | Deviation analysis | Skipping mandatory overview table; omitting dossier | Overview table is MANDATORY even when zero items are actionable; header, rows, and legend must all appear; minimal dossier must still be written |
| 5 | `partial fix` | PR #1215, `discussion_r3257258893` | Accepting incomplete fix as resolved; missing direction error | Must include three-part evidence chain; must map to Section A; reply must acknowledge existing attempt |
| 6 | `duplicate reply` | PR #1215 patterns | Creating duplicate tasks; replying only once for multiple authors | One task entry; all authors listed; each author gets individual reply via own `in_reply_to` ID; same fix not applied twice |
| 7 | `cross-file` | PR #1215 deviation analysis | Scope creep; fixing uncommented files without guardrail | Fix commented file only; cross-file pattern documented as guardrail; no additional Section A tasks created; Moderate evidence requires guardrail row; Strong evidence requires dedicated section |

---

If a regression scenario check fails (Section 5), the change that caused the regression must be reverted. Regression passing is a mandatory gate, not a suggestion. The eval matrix (`eval-matrix.md`) defines the acceptance criteria; this file defines the verification procedure.
