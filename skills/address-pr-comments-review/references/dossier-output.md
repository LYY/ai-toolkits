# Dossier & Reply Output Protocol

Step 4 dossier generation, reply policy, and validation gates. Produces the review dossier and governs reply behavior.

> **Prerequisite**: Dossier generation (Sections A/B) applies only when Section A > 0 (code changes needed). When Section A = 0, skip dossier generation entirely:
> - **Reply-only** (B > 0): Read §Reply Endpoints + §Direct Reply-Only Posting + §Reply Policy. Skip Dossier Structure, Sections A/B/C.
> - **Nothing actionable** (B = 0): End. No need to read this file.
> The Reply Policy and Pre-Reply Gate apply regardless of whether a dossier is generated.

---

## Dossier Structure

The dossier is the final deliverable of Phase 1. It captures every confirmed decision from Steps 2-4 and feeds Prometheus mode for execution plan generation.

Artifacts are disposable Markdown files. Unless the user provides `artifact_dir=<path>`, write dossiers and Direct Fix Briefs under `~/.local/state/ai-toolkits/pr-comments/<owner>__<repo>/pr-<N>/`. Do not write to `.omo`, `.agent`, or any repo-local directory by default. Do not edit root `.gitignore`, `.git/info/exclude`, or global gitignore.

### Generated Execution Plan Reply Contract

When Section A > 0, the dossier MUST tell Prometheus that its generated execution plan MUST include reply task(s) for every Section A and Section B item unless the Pre-Reply Gate blocks that specific item or the item belongs in Section C. Section C, `already_replied`, `minimized`, and other no-action entries are not reply tasks.

Plan order for each Section A item is mandatory:

1. Code change, targeted tests, and commit.
2. Reply task(s) using Reply Endpoints and Reply Policy. Each reply text MUST include the modification commit SHA produced in step 1.
3. Read-back verification task that proves the posted reply exists by GET/LIST read operations.

Section B entries become reply-only tasks in the generated plan, with read-back verification and no code, tests, or commit. Duplicate comments stay one logical task, but the plan MUST require a posted reply for every listed author/comment ID that passes the Pre-Reply Gate.

### Executive Summary

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
- Target checkout root: `<TARGET_WORKTREE_ROOT>` (the bound checkout; local reads and git commands run from this root)
- Artifact path: `<ARTIFACT_PATH>` (default local state path or explicit `artifact_dir` override)
- Commit style: {{COMMIT_STYLE}} (run `git -C "$TARGET_WORKTREE_ROOT" log --oneline -10`)
- Analyzed: {{TIMESTAMP}}
```

---

## Reply Endpoints

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
  -F body="{{REPLY_TEXT}}" -F commit_id=$(git -C "$TARGET_WORKTREE_ROOT" rev-parse HEAD) \
  -F path="{{FILE_PATH}}" -F line={{LINE}} -F side=RIGHT \
  -F in_reply_to={{COMMENT_ID}}

# review:
gh api repos/{{REPO}}/issues/{{PR_NUMBER}}/comments --method POST \
  -F body="@{{AUTHOR}} {{REPLY_TEXT}}"

# top_level:
gh api repos/{{REPO}}/issues/{{PR_NUMBER}}/comments --method POST \
  -F body="{{REPLY_TEXT}}"
```

**Commit SHA note**: Inline replies require a valid commit SHA on the PR branch. Resolve it from the bound checkout with `git -C "$TARGET_WORKTREE_ROOT" rev-parse HEAD`. `review` and `top_level` replies do not need `commit_id`.
```

---

## Direct Reply-Only Posting

Use this section only when Section A = 0 and Section B > 0. This route skips dossier generation, but it does not stop at draft or compose text.

For each Section B item that passes the Pre-Reply Gate:

1. Select the endpoint from Reply Endpoints.
2. POST/send the reply with `gh api` using that endpoint.
3. Verify the reply by read-back with GET/LIST operations, such as `gh api repos/{owner}/{repo}/issues/{pr}/comments --paginate` for `review` and `top_level` replies, or `gh api repos/{owner}/{repo}/pulls/{pr}/comments --paginate` for `inline` replies.
4. Confirm the read-back output contains the expected reply body, author, and target thread or comment relationship.

If a POST result is unclear, do the read-back first. Retry the POST only after read-back proves the reply is absent. Do not verify by duplicate POST.

Duplicate comments require one reply POST per listed author/comment ID that passes the Pre-Reply Gate, followed by read-back verification for each posted reply.

---

## Direct-Fix Fast Path

Use this section only when Section A contains simple low-risk code work and the user explicitly chose direct fix after the final overview table. This route replaces the full Prometheus dossier with a shorter Direct Fix Brief. It does not remove reply, commit, or read-back obligations.

### Eligibility Checklist

Every checked condition must be true before writing a Direct Fix Brief:

| Check | Required Condition |
|-------|--------------------|
| Section A size | Small enough to execute directly; default limit is one Section A task unless the user explicitly allows more |
| Scope | Each code task touches one clearly named file |
| Risk | Mechanical low-risk change such as wording, comments, docs, config tweak, rename, or proto field rename with field number preserved |
| Cross-reference | No unresolved duplicate ambiguity, conflict, dependency, or Strong cross-file escalation |
| Specificity | `What to change` and `How to test` are exact enough for direct execution |
| Reply data | Comment ID, author, reply kind, endpoint, and inline target fields are complete |
| User choice | User explicitly chose direct fix; small PR fast-path consent alone is insufficient |

If any check fails, do not write a Direct Fix Brief. Use the normal Dossier Structure and Prometheus handoff.

### Dossier Accuracy Grill Gate

Run this gate before writing either a full dossier or a Direct Fix Brief. Ask only about uncertainty that remains after code inspection, comment reading, cross-reference checks, and user discussion. If there is no uncertainty, state that the gate has no questions and proceed.

Use grill-me style:

- Ask one question at a time.
- Include the recommended answer.
- Do not ask what code/comment context already answers.
- Stop as soon as the execution boundary is unambiguous.
- Do not invoke `grill-with-docs` by default. Use it only when the PR comment requires domain glossary or ADR-style decision capture.

Question triggers:

| Trigger | Question Shape |
|---------|----------------|
| Direct-fix boundary unclear | "Should this bypass Prometheus, or should it use the normal dossier? Recommended: ..." |
| Multiple valid implementations | "Which implementation should the worker apply? Recommended: ..." |
| Scope guardrail unclear | "Should this fix stay in the commented file only? Recommended: ..." |
| Test strategy unclear | "Which targeted validation is enough for this change? Recommended: ..." |
| Reply wording may mislead | "Should the reply include a change summary beyond `Fixed in <sha>`? Recommended: ..." |
| Cross-file work ambiguous | "Should same-pattern files be fixed now or deferred? Recommended: ..." |

Gate completion criterion: every trigger is either answered from existing evidence, answered by the user, or causes fallback to the normal dossier/Prometheus path.

### Direct Fix Brief Template

```markdown
# Direct Fix Brief: PR #{{PR_NUMBER}}

## Context
- PR: {{PR_URL}}
- Repo: `{{REPO}}`
- Branch: `{{BRANCH}}`
- Target checkout root: `<TARGET_WORKTREE_ROOT>`

## Comment
- Comment ID: `{{COMMENT_ID}}`
- Author: @{{AUTHOR}}
- Kind: `{{KIND}}`
- Location: `{{FILE_PATH}}:{{LINE}}`
- Conclusion: `valid`

## Change
{{DEV_CHANGES}}

## Guardrails
- {{GUARDRAIL_1}}

## Verification
{{TEST_STRATEGY}}

## Reply
- Reply kind: `{{REPLY_KIND}}`
- Endpoint: `{{REPLY_ENDPOINT}}`
- Inline target: `path={{FILE_PATH}}`, `line={{LINE}}`, `side=RIGHT`, `in_reply_to={{COMMENT_ID}}`
- Pre-Reply Gate: must pass before composing reply
- Reply commit requirement: reply text MUST reference the modification commit SHA
- Reply body: {{REPLY_TEMPLATE}}

## Read-Back Verification
GET/LIST the matching comment thread or PR comments and confirm the posted reply body, author, and target relationship. Do not verify by repeating POST.
```

For non-inline comments, replace `Inline target` with the `review` or `top_level` target from Reply Endpoints. Do not remove `Comment ID`, `Author`, `Reply kind`, `Endpoint`, `Pre-Reply Gate`, `Reply commit requirement`, or `Read-Back Verification`.

---

## Section A: Comments Requiring Code Change + Reply

Section A captures every comment confirmed as requiring a code change and a reply. Each comment becomes one task entry.

### Section A Task Template

All fields mandatory. No generic descriptions — exact paths, line numbers, specific commands.

```markdown
### Task {{TASK_NUM}}: Comment #{{COMMENT_ID}} -- {{SUMMARY}}
- **Source**: @{{AUTHOR}} | {{KIND}} | {{FILE_PATH}}:{{LINE}}
- **Also noted by**: @{{DUP_AUTHOR1}}, @{{DUP_AUTHOR2}} (omit if no duplicates)
- **Conclusion**: `valid`
- **What to change**: {{DEV_CHANGES}} (exact file paths, line numbers, specific code modification)
- **How to test**: {{TEST_STRATEGY}} (specific test commands, expected output)
- **Reply after fix**: {{REPLY_KIND}} -> @{{AUTHOR}} (use endpoint from Reply Endpoints)
- **Reply commit requirement**: Reply text MUST reference the modification commit SHA created for this task, e.g. `Fixed in <commit_sha>.` Add the required change summary from Reply Policy when the fix is partial, direction-correcting, or non-obvious.
- **Reply to duplicate authors**: Same reply, directed to @{{DUP_AUTHOR}} via their own `in_reply_to` ID
- **Plan order**: code/test/commit first, then reply task(s), then read-back verification
- **Commit message**: `{{SUGGESTED_COMMIT_MESSAGE}}` (imperative mood, matching repo conventions)
```

---

## Section B: Comments Requiring Reply Only

Section B captures every comment confirmed as needing a reply but no code change. These entries become reply-only tasks in the Prometheus execution plan. No tests, no commits.

### Section B Task Template

```markdown
### Task {{TASK_NUM}}: Comment #{{COMMENT_ID}} -- {{SUMMARY}}
- **Source**: @{{AUTHOR}} | {{KIND}} | {{FILE_PATH}}:{{LINE}}
- **Conclusion**: `{{CONCLUSION}}` -- {{RATIONALE}}
- **Reply**: {{REPLY_KIND}} -> @{{AUTHOR}} (use endpoint from Reply Endpoints)
- **Read-back verification**: GET/LIST the matching comment thread or issue comments and confirm the posted reply body and author
```

For conflict resolution (rejected direction), add `- **Context**: User chose @A over @B` and set `- **Conclusion**: \`invalid\``.

### Required Fields (ALL Mandatory)

Conclusion rationale (why no code change), reply target (kind + author), no-code-change constraint (no references to code modifications or test commands).
For duplicates, every listed author/comment ID must appear in the reply task target list unless the Pre-Reply Gate blocks that individual target.

### Conflict Handling

When user chooses @A's approach over @B's: chosen direction goes to Section A (if code change needed) or Section B (if reply-only); rejected direction goes to Section B with `invalid` conclusion, explaining why the approach was not taken. Both options and the user choice are captured in the entry.

---

## Section C: Informational & Already-Replied Comments -- No Action

```markdown
| # | Source | Kind | Summary | Reason |
|---|--------|------|---------|--------|
| {{COMMENT_ID}} | @{{AUTHOR}} | {{KIND}} | {{SUMMARY}} | {{informational / already_replied}} |
```

`informational` (praise, LGTM, emoji, FYI, nit, retraction), `already_replied` (sufficient human reply), and `minimized` by author go here. No code change, no reply, no follow-up. NOT counted as plan tasks.

---

## Duplicate Handling in Dossier

ONE task entry, ALL authors under "Also noted by", EACH author gets individual reply via own `in_reply_to` ID, same content, merge documented in Dedup & Conflict Notes. For 3+: list all authors and comment IDs explicitly. The generated plan MUST include reply tasks that cover every listed author/comment ID unless the Pre-Reply Gate blocks that individual target.

### Duplicate + Cross-File Combination

Primary entry follows cross-file escalation rules; duplicate authors follow duplicate handling. Cross-file pattern is a separate concern, not a duplicate.

## Conflict Handling in Dossier

Chosen direction goes to Section A (code change) or Section B (reply-only). Rejected direction goes to Section B with `invalid` conclusion. Document in Dedup & Conflict Notes. "What to change" references both approaches and explains the choice.

## Cross-Section Rule

Every item's dossier section MUST match its conclusion per the Section Mapping table in `classify.md`. If a conclusion changes during Step 3 interaction, re-assign the section. The pre-write cross-reference scan (see Validation Gates) catches any section misplacement automatically.

---

## Dependencies

When comments are causally or logically related (detected per `cross-reference.md`), capture after Cross-Reference Checks. Types: `fixes_needed_before`, `may_become_unnecessary`, `should_be_grouped`.

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

## Cross-File Pattern Detected (Strong escalation only)

Inserted before Scope Guardrails when cross-reference escalation confirms Strong evidence (4+ matches or same subsystem):

```markdown
## Cross-File Pattern Detected
- **Grep**: `grep -rn "<pattern>" <dir>/ --include="*.<ext>"` → N matches
- **Files**: <file1>, <file2>, ...
- **Scope**: Fix <commented file> only (Section A)
- **Follow-up**: Address remaining N files in separate PR
```

---

## Reply Policy

Governs when and how to reply to PR comments.

### Pre-Reply Gate

**Before composing any reply, run this checklist.** The gate exists to prevent the two highest-cost reply failures: replying to a thread that already has a sufficient response, and sending an overconfident `Fixed in <sha>` for a fix that is misleading without context.

#### Gate Checklist

| # | Check | Condition to pass | Action if failed |
|---|-------|-------------------|------------------|
| 1 | **Already replied?** | Does this thread have `has_replies: true` with a substantively sufficient human reply? Verify: reply author is human (not bot), reply is substantive (not "Good point" / "I'll check"), reply is not your own from a previous pass. | Do NOT reply. The existing reply already addresses the concern. If the existing reply is insufficient, flag for user override at Step 3. |
| 2 | **Duplicate author?** | Is this comment one of multiple that were merged as duplicates? | Compose ONE reply. Send it to EACH author individually via their own `in_reply_to` ID. Do not reply to only one author. |
| 3 | **Change summary needed?** | Does the conclusion require a change summary alongside the fix confirmation (see Change Summary Rule below)? | Add a change summary before `Fixed in <sha>`. Do not send a bare `Fixed in <sha>` alone. |
| 4 | **Conclusion still valid?** | Has the code state changed since classification (e.g., a new commit was pushed, or the diff shifted)? | Re-verify the conclusion against current HEAD. If the issue no longer exists, reclassify before replying. |

#### Gate Enforcement

If check #1 fails, the reply is blocked entirely. Do not compose, draft, or prepare a reply. Do not look for ways around the block. The existing reply stands unless the user explicitly reclassifies during Step 3.

All four checks must pass before any reply content is written. The gate is evaluated per-author: for duplicate comments, run the gate for each author individually (check #2 ensures the content is the same, but check #1 may differ per author if some threads have replies and others do not).

---

### Change Summary Rule

A bare `Fixed in <sha>` implies the fix speaks for itself. When the fix is misleading, partial, or non-obvious without context, a 1-2 sentence change summary MUST accompany the SHA.

`Fixed in <sha>` alone is allowed only when the fix is straightforward and the commit message fully describes the change (e.g., rename, typo fix). In ALL other cases, a change summary is mandatory:

| Situation | Why pure SHA is misleading |
|-----------|---------------------------|
| **Direction correction or reframed approach** | The fix takes a different path than suggested. `Fixed in <sha>` implies the concern was resolved as-requested. |
| **Partial fix** | The core concern is not fully resolved (scope boundary, same pattern elsewhere). `Fixed in <sha>` implies completion. |
| **Non-obvious change** | Subtle refactor, dependency change, or multi-file fix. The SHA alone doesn't convey scope or reasoning. |

Format: precede or follow `Fixed in <sha>` with a 1-2 sentence description:

```
Fixed in abc123. The fix reorders the initialization sequence — cleanup()
now runs after process() completes.
```

For partial fixes, add scope boundary: `"Fixed in abc123 (src/auth/login.go only). Same issue in N other files — follow-up PR to follow."`
For direction corrections: `"Corrected the fix direction in abc123. Previous attempt placed X before Y; now correctly runs after."`

---

### Reply Templates Per Conclusion

Each conclusion maps to exactly one reply template. The template is the default; the interaction protocol (Step 3) or the Change Summary Rule may override or extend it.

| Conclusion | Template | Change summary required? | Notes |
|-----------|----------|-------------------------|-------|
| valid (fixed) | `Fixed in <commit_sha>.` + change summary IF partial/direction-correction/non-obvious | See Change Summary Rule | Bare SHA only when fix is self-explanatory. Always check the rule. |
| invalid | `This suggestion doesn't apply because <reason>.` | No | Reason is mandatory -- one sentence minimum. |
| already_fixed | `Already resolved in the current code -- no changes needed.` | No | Evidence of the existing fix must be citeable per `classify.md`. |
| out_of_scope | `This is outside the scope of this PR. <follow-up>.` | No | Follow-up suggestion is optional but recommended. |
| needs_clarification | `Confirmed: <resolved direction>.` | No | Direction is resolved during Step 3 interaction. |
| partially_addressed | `Acknowledged. The existing fix at <sha> addresses <X> but does not address <Y>. <Corrected/reworked> in <sha> to <describe correct fix>.` | Yes -- always | See Partial Fix Reply section below. |
| conflict (not chosen) | `Thanks for the suggestion. We went with @other's approach for <reason>.` | No | Reason must neutrally explain the choice without disparaging the rejected approach. |

#### Partial Fix Reply (partially_addressed)

When the classification protocol assigned `partially_addressed`, the reply MUST include three components in order:

1. **Acknowledge the existing attempt**: Cite the commit SHA and what it attempted to fix.
2. **Explain the insufficiency**: State why the existing fix does not resolve the core concern. Reference the specific code lines. Use neutral factual language.
3. **Describe the correct fix**: State what was done in the new fix (or what will be done). Reference the new commit SHA.

Format:

```
The fix at abc123 addressed the cleanup ordering by moving it before
process(), but the reviewer's concern was that cleanup should happen
AFTER process completes. This rework in def456 moves the
call to the correct position in the execution sequence.
```

Do NOT omit the acknowledgment. A `partially_addressed` reply that jumps straight to "Fixed in <sha>" without acknowledging the previous attempt reads as dismissive.

#### Duplicate Author Reply Strategy

When a comment was merged as a duplicate (same concern, multiple authors):

- Compose ONE reply with the same content for all authors
- Send to EACH author individually using their own `in_reply_to` ID
- Do NOT reply to only one author, even if the others are bots
- Do NOT create separate dossier tasks for each author. The one logical task carries every author/comment ID, every POST/send action, and every read-back verification.

The reply content is identical across authors. The only difference is the `in_reply_to` parameter in the API call.

---

## Validation Gates

Checks and gate rules that ensure dossier integrity before handoff.

### 1. Pre-Dossier Scan: Final Cross-Reference (Pre-Write)

Before writing the dossier, re-scan the final confirmed table from Step 4 against the original cross-reference results. Discussion may have changed conclusions, revealed new connections, or created new duplicates.

#### 7-Check Checklist

| Check | What to look for | Action if found |
|-------|-----------------|-----------------|
| **New duplicates** | Two entries with same file:line but different # numbers after discussion renumbering | Merge into one entry, update counts |
| **Duplicate state shift** | Discussion changed one merged comment's conclusion (e.g., `valid` → `invalid`) — entries may no longer be duplicates, or the remaining partner needs re-verification | Split or re-verify as appropriate |
| **Unresolved conflicts** | Any entry still marked with a discussion flag without a user decision recorded | **STOP. Do not proceed.** Return to Step 3 for resolution |
| **New relations** | Discussion revealed fixing Comment #X will also fix Comment #Y (related, not duplicate) | Add dependency note |
| **Cross-section leakage** | A comment in Section A (code change) actually only needs a reply based on final discussion | Move to Section B |
| **Reply target mismatch** | Merged duplicates — all authors listed? Each has an `in_reply_to` ID? | Verify all authors accounted for |
| **Stale already_replied** | A comment marked `already_replied` but discussion revealed the reply was insufficient or from a bot | Reclassify |

**Gate rule**: If any unresolved item remains after the scan, do NOT write the dossier. Return to Step 3.

---

### 2. Post-Write Dossier Verification

After writing the dossier file, run these checks.

#### 2.1 File Existence and Integrity

| Check | Command/Condition |
|-------|-------------------|
| File exists | `test -f "$ARTIFACT_PATH"` |
| Valid markdown | File starts with `# Review Dossier:` |
| Counts match | Executive Summary counts = actual items in each section |
| No placeholder left | No `{{...}}` template variables remain |
| Reply endpoint correct | Each reply task uses the endpoint matching its REPLY_KIND (inline/review/top_level) |
| Section A reply commit requirement present | Every Section A task includes `Reply commit requirement` requiring the reply text to reference the modification commit SHA |
| Artifact path correct | Dossier lives under the selected artifact directory: default `~/.local/state/ai-toolkits/pr-comments/<owner>__<repo>/pr-<N>/` or explicit `artifact_dir=<path>` |
| Handoff prompts present | Output includes generic executor prompt and OMO / Prometheus prompt from `platform.md` |

**Gate rule**: If an explicit repo-local `artifact_dir` is not ignored, warn that it may appear in `git status` and continue only if the user accepts. Do not edit `.gitignore`, `.git/info/exclude`, or any ignore file in this step.

#### 2.2 No-Placeholder Leakage Check (Mandatory)

Any unfilled `{{...}}` placeholder means the dossier is incomplete and must be regenerated. Common placeholders: `{{PR_URL}}`, `{{BRANCH}}`, `{{REPO}}`, `{{TIMESTAMP}}`, `{{REPLY_TEXT}}`, `{{FILE_PATH}}`, `{{LINE}}`, `{{COMMENT_ID}}`, `{{DEV_CHANGES}}`, `{{TEST_STRATEGY}}`.

**Gate rule**: If any placeholder remains unfilled, do NOT hand off to Prometheus. Regenerate the dossier.

#### 2.3 Direct Fix Brief Completeness

When using the Direct-Fix Fast Path, verify the brief contains every required execution and reply field:

| Required Field | Why |
|----------------|-----|
| PR URL, repo, branch, and target checkout root | Ensures direct execution uses the bound checkout |
| Comment ID, author, kind, file path, and line | Preserves the review target |
| Exact code change and guardrails | Prevents scope creep |
| Targeted verification | Prevents unverified direct edits |
| Reply kind and endpoint | Enables correct POST target |
| Inline `path`, `line`, `side`, and `in_reply_to` when kind is `inline` | Enables correct threaded inline reply |
| Pre-Reply Gate | Prevents duplicate or stale replies |
| Commit SHA reply requirement | Ensures reviewer can trace the fix |
| Read-back verification | Proves the reply exists without duplicate POST |
| Direct execution prompt | Ensures the user can copy-paste the brief into an executor without inventing instructions |

**Gate rule**: If any required field is missing, do NOT hand off the Direct Fix Brief. Either regenerate it or use the normal dossier/Prometheus path.

---

### 3. Gate Rules

#### 3.1 The 🔴 Gate

If any 🔴 item remains unresolved after Step 4 interaction (conflicts unresolved, needs_clarification unanswered, high-risk valid items not acknowledged), the skill MUST NOT write the dossier. It must return to Step 3 for further discussion. This is a hard gate -- no override, no workaround.

#### 3.2 Confirmation Gate

Step 3 user confirmation is required before dossier generation. Dossier generation must not proceed without explicit confirmation.

#### 3.3 How to Block

When a check fails:
1. **State the failure**: "Validation check failed: [check name]. [Detail of what was found]."
2. **Explain the consequence**: "This means the dossier cannot be written / the handoff cannot proceed."
3. **Provide the corrective action**: "Return to Step [N] and [specific fix]."
4. **Do NOT proceed until the check passes.**

---

If a regression scenario check fails, revert the change that caused the regression. Regression passing is a mandatory gate.
