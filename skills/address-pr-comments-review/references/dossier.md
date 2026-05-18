# Dossier Contract

This file defines the dossier contract: the structure, content rules, evidence requirements, and quality checks for the review dossier generated after successful interaction (Step 4). The dossier is the final deliverable of Phase 1. It is a requirements document that captures every confirmed decision from Steps 2-4 and feeds Prometheus (Phase 2) for execution plan generation.

## Precedence

Layer 3 (decision protocols). Consumes output from classification (Step 2), cross-reference (second half of Step 2), and interaction (Steps 3-4). Dossier rules take precedence over template defaults: if the dossier contract specifies a format requirement, platform templates and reply templates must adapt. The dossier is NOT the canonical source for reply policy text. Reply policy is in `reply.md`.

---

## Scope

This file covers:

- **Executive Summary format**: category counts, dedup notes, context line
- **Reply endpoints**: inline/review/top_level with `gh api` commands (endpoints only, not reply templates)
- **Section A rules**: tasks requiring code change + reply -- structure, required fields, evidence for `partially_addressed` and cross-file escalation
- **Section B rules**: tasks requiring reply only -- structure, rationale, no-code-change constraint
- **Section C rules**: informational and already-replied -- no action, table format
- **Duplicate handling in dossier**: single task entry, multi-author listing, individual reply IDs
- **Conflict handling in dossier**: chosen direction in A/B, rejected direction in B
- **Cross-section leakage prevention**: prohibitions against moving items between sections
- **Cross-Reference Checks**: 8-item pre-write scan with gate rules
- **Dependencies**: related-task notation for plan mode
- **Scope guardrails**: anti-scope-creep constraints embedded in the dossier
- **Post-write verification**: file existence, valid markdown, count matching, placeholder completeness, reply endpoint correctness

## Out of Scope

- Classification rules -> `classification.md`
- Cross-reference logic -> `cross-reference.md`
- Interaction protocol -> `interaction.md`
- Platform-specific file paths and commands -> `platform.md`
- Validation and regression checklists -> `validation.md`
- Reply template content -> `reply.md` (dossier references reply endpoints only, not template text)

---

## Executive Summary Format

The dossier opens with an executive summary table that gives Prometheus an at-a-glance overview of all tasks:

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

Follows the executive summary:

```markdown
## Dedup & Conflict Notes
| Type | Count | Details |
|------|-------|---------|
| Duplicates merged | D | Comments #X, #Y merged into Task A due to same file:line |
| Conflicts resolved | C | Comment #X vs #Y: user chose @alice's approach over @bob's |
```

### Context Line

```markdown
## Context
- PR: {{PR_URL}}, Branch: {{BRANCH}}, Repo: {{REPO}}
- Commit style: {{COMMIT_STYLE}} (run `git log --oneline -10` in the PR branch)
- Analyzed: {{TIMESTAMP}}
```

---

## Reply Endpoints

The dossier must include a reference table of `gh api` commands for each reply kind. These are endpoint-level details (what URL to hit, what flags to pass). Reply TEMPLATES (what to say) are NOT duplicated here.

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

**Reply templates are defined in `reply.md` -- this file does not duplicate them.**

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

Every Section A entry MUST contain:

1. **Exact file paths and line numbers** -- relative to repo root, with specific lines
2. **Code change description** -- specific modification, not a general direction
3. **Test strategy** -- specific test commands and expected output
4. **Reply target** -- kind (inline/review/top_level) and author
5. **Suggested commit message** -- one line, imperative mood, matching repo conventions

### Evidence Requirements for Section A Entries

**Standard `valid` entries**: No upstream evidence beyond confirming the issue exists at the referenced `path:line` on current HEAD.

**`partially_addressed` entries**: The dossier entry MUST include the three-part evidence from the classification protocol (`classification.md`):

1. **Fix attempt citation**: "Commit `<sha>` attempted to fix by changing `<X>` at `<file>:<line>`"
2. **Remaining issue citation**: "Current code at `<file>:<line>` still shows `<problem>`"
3. **Insufficiency explanation**: "The fix addresses `<X>` but does not address `<Y>`. The reviewer asked for `<Z>`."

This evidence appears in the "What to change" section of the task entry, or as a supplementary note following the task fields. Without all three evidence items, a `partially_addressed` entry is incomplete.

**Cross-file escalation entries**: When the cross-reference protocol detected a cross-file pattern at Moderate or Strong evidence level, the dossier entry MUST include:

1. The evidence level (Moderate/Strong) from `cross-reference.md`
2. The grep command used and its results
3. The list of files with the same pattern
4. A scope guardrail stating: "Fix only the commented file in this task."

For Strong evidence, a separate `## Cross-File Pattern Detected` section is appended before Scope Guardrails:

```markdown
## Cross-File Pattern Detected

- **Grep command**: `grep -r "pattern" server/ --include="*.go"`
- **Files with same pattern**: {file list}
- **Current fix scope**: {commented file} only (Section A of this dossier)
- **Recommendation**: Create a follow-up PR to address remaining {N} files.
```

For Moderate evidence, the cross-file information is captured as a Scope Guardrail row and a Dedup & Conflict Notes row. The Section A entry for the primary file references the scope guardrail by name.

The cross-file escalation evidence is consumed from the cross-reference protocol output (`cross-reference.md` Section 5). The dossier does NOT re-detect cross-file patterns; it documents what cross-reference found.

---

## Section B: Comments Requiring Reply Only

Section B captures every comment confirmed as needing a reply but no code change. No tests, no commits.

### Section B Task Templates

**Standard reply-only entry**:

```markdown
### Task {{TASK_NUM}}: Comment #{{COMMENT_ID}} -- {{SUMMARY}}
- **Source**: @{{AUTHOR}} | {{KIND}} | {{FILE_PATH}}:{{LINE}}
- **Conclusion**: `{{CONCLUSION}}` -- {{RATIONALE}}
- **Reply**: {{REPLY_KIND}} -> @{{AUTHOR}} (use endpoint from Reply Endpoints)
```

**Conflict resolution entry** (rejected direction):

```markdown
### Task {{TASK_NUM}}: Comment #{{COMMENT_ID}} -- Conflict resolution: {{SUMMARY}}
- **Source**: @{{REJECTED_AUTHOR}} (vs @{{CHOSEN_AUTHOR}}) | {{KIND}} | {{FILE_PATH}}:{{LINE}}
- **Context**: User chose @{{CHOSEN_AUTHOR}}'s approach over @{{REJECTED_AUTHOR}}'s conflicting suggestion.
- **Conclusion**: `invalid` (conflicting approach not taken)
- **Reply**: {{REPLY_KIND}} -> @{{REJECTED_AUTHOR}} (use endpoint from Reply Endpoints)
```

### Required Fields (ALL Mandatory)

Every Section B entry MUST contain:

1. **Conclusion rationale** -- why the concern does not need a code change
2. **Reply target** -- kind and author
3. **No-code-change constraint** -- implicit in Section B, but the entry must not reference code modifications or test commands

### Conflict Handling in Section B

When the user resolves a conflict (choosing @A's approach over @B's):

- The chosen direction goes to Section A (if it requires a code change) or Section B (if reply-only)
- The rejected direction goes to Section B as a reply-only item with conclusion `invalid`
- The reply explains to the rejected reviewer why their approach was not taken
- The conflict context (both options, user choice) is captured in the entry

---

## Section C: Informational & Already-Replied Comments -- No Action

Section C captures comments that require no action at all. No code changes, no replies.

### Section C Table Format

```markdown
| # | Source | Kind | Summary | Reason |
|---|--------|------|---------|--------|
| {{COMMENT_ID}} | @{{AUTHOR}} | {{KIND}} | {{SUMMARY}} | {{informational / already_replied}} |
```

### Section C Rules

- Comments classified as `informational` (praise, LGTM, emoji-only, FYI, nit, retraction) go here
- Comments classified as `already_replied` (has a sufficient human reply) go here
- Comments that were `minimized` by their author go here
- No code change, no reply, no follow-up
- Section C items are NOT counted as plan tasks in the executive summary

---

## Duplicate Handling in Dossier

When the cross-reference protocol identified duplicates (same file:line, same issue), the dossier follows these rules:

1. **ONE task entry** in Section A or B for the merged concern
2. **ALL authors listed** in the task entry under "Also noted by"
3. **EACH author receives an individual reply** via their own `in_reply_to` ID (not a shared ID)
4. **Same reply content** for all duplicate authors (the fix was applied / the conclusion stands)
5. **Merge documented** in the Dedup & Conflict Notes table

For 3+ duplicates: list all IDs explicitly in the task entry so plan mode can iterate.

### Duplicate + Cross-File Combination

When a duplicate concern also triggers cross-file escalation:
- The primary entry (commented file) follows cross-file escalation rules
- Duplicate authors of the primary comment follow duplicate handling rules
- The cross-file pattern is documented as a separate concern, not as a duplicate of the primary entry

---

## Conflict Handling in Dossier

When the cross-reference protocol detected conflicting advice:

1. **Chosen direction**: Goes to Section A (if code change needed) or Section B (if reply-only) with its conclusion
2. **Rejected direction**: Goes to Section B as a reply-only item with conclusion `invalid`
3. **Conflict context**: Documented in the Dedup & Conflict Notes table
4. **Both options neutrally presented**: The "What to change" section references both approaches and explains why the chosen one was selected

---

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

Before writing the dossier, re-scan the final confirmed table (from Step 4) against the original cross-reference results. Discussion may have changed conclusions, revealed new connections, or created new duplicates.

### 8-Check Checklist

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

### Gate Rule

If any unresolved item remains after the scan, do NOT write the dossier. Return to Step 3. If all checks pass, proceed to write.

The dossier includes a check results table:

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

When comments are causally or logically related (call chain, shared type, sequential workflow), the dossier captures dependency metadata after the Cross-Reference Checks section.

```markdown
## Dependencies

If related comments exist (call chain, shared type), note here:
- Task X and Task Y both modify `shared_type.go` -- coordinate changes.
- Task A is a callee of Task B's caller -- order: fix callee first, then caller.
- Fixing Task X may make Task Y unnecessary -- verify after X is complete.
```

Dependency types consumed from the cross-reference protocol:
- `fixes_needed_before`: Tasks that must be completed first
- `may_become_unnecessary`: Tasks whose concern may be resolved by another task
- `should_be_grouped`: Tasks that should be addressed in the same commit

---

## Scope Guardrails

The dossier embeds scope guardrails after the Dependencies section. These constraints prevent scope creep during plan execution.

```markdown
## Scope Guardrails

These constraints prevent scope creep. Prometheus bakes them into every task.

| Rule | Rationale |
|------|-----------|
| {{GUARDRAIL_1}} | {{RATIONALE_1}} |
| {{GUARDRAIL_2}} | {{RATIONALE_2}} |
```

### Common Guardrails

- No vendor/ dependency refresh beyond the fix
- No global refactors or renames beyond the specific change
- Reply-only tasks must not modify code or run tests
- Cross-file pattern detected: fix only the commented file (see cross-file escalation rules)

### Guardrail Sources

Guardrails come from:
1. The cross-reference protocol (cross-file escalation at Moderate or Strong evidence)
2. The interaction protocol (user-specified constraints during Step 3 discussion)
3. Default platform constraints from `platform.md`

---

## Post-Write Verification

After writing the dossier, run this verification checklist:

| Check | Command/Condition |
|-------|-------------------|
| File exists | `test -f .sisyphus/notepads/pr-<N>-dossier/dossier-<TIMESTAMP>.md` |
| Valid markdown | File starts with `# Review Dossier:` |
| Counts match | Executive Summary counts = actual items in each section |
| No placeholder left | No `{{...}}` template variables remain -- all should be substituted |
| Reply endpoint correct | Each reply task uses the endpoint matching its `{{REPLY_KIND}}` (inline/review/top_level) |
| Reply templates referenced correctly | Reply templates are referenced by name, not duplicated inline |

If any check fails, fix and re-verify. The validation protocol (`validation.md`) provides the definitive gate rules.

---

## Key Design Decisions

### Dossier Is Not a Plan

The dossier is a requirements document, not an execution plan. Plan generation happens in Phase 2 via interactive Prometheus conversation. The dossier provides enough detail for Prometheus to ask informed follow-up questions. The dossier must not contain execution logic, dependency graphs, or scheduling decisions. Those belong in Phase 2.

### Duplicate Task Structure

When comments are merged (same file:line, same issue):
- ONE task entry in the dossier
- ALL authors listed in the task
- EACH author gets an individual reply via their own `in_reply_to` ID
- Dedup & Conflict Notes section documents the merge

### Cross-Section Leakage Prevention

The dossier contract explicitly forbids:
- Code-change tasks that only need a reply (move from A to B)
- Reply-only tasks that imply code changes (keep in B, add note)
- Informational items being promoted to actionable (stay in C)
- `partially_addressed` items placed in Section B (they require code changes)

### Final Cross-Reference Scan

Before writing, run the 8-check scan defined in this document. Any unresolved item blocks dossier writing.

### Evidence Requirements Are Protocol-First

Dossier entries for `partially_addressed` and cross-file escalation MUST include evidence from the upstream classification and cross-reference protocols. The dossier does NOT re-evaluate evidence; it documents what upstream protocols found. This ensures:
- Traceability: every dossier claim has an upstream source
- Verifiability: a reader can trace from dossier back to raw comment
- No spurious entries: evidence requirements prevent undocumented assertions

### Reply Templates Deferred to `reply.md`

The dossier contains reply ENDPOINTS (URLs, flags, gh commands) because those are platform-level details needed for plan execution. Reply TEMPLATES (what to say for each conclusion) are defined in `reply.md`. The dossier references reply templates by name but does not duplicate their content. This prevents drift between the two files and keeps the dossier focused on structure and evidence, not wording.

---

## Reliability and Compatibility

### Downstream Consumers

The dossier feeds Prometheus (Phase 2). Changes to the dossier structure must account for:
- Prometheus parses the executive summary for task counts
- Prometheus creates one implementation task per Section A entry
- Prometheus creates one reply task per Section B entry
- Section C entries are informational only and generate no tasks

### Section A/B/C Compatibility

Section A, Section B, and Section C have fixed semantics:

| Section | Semantics | Action |
|---------|-----------|--------|
| Section A | Code change + reply | Tests, commit, reply inline |
| Section B | Reply only | No code changes, reply explains decision |
| Section C | No action | Skip entirely |

These semantics must NOT be renamed or reordered. Any change to Section A/B/C semantics must be coordinated with SKILL.md (the canonical mapping), `reply.md` (template selection), and Prometheus (plan generation).

### Regression Boundaries

The following behaviors must survive any dossier structure change:
- `partially_addressed` entries include three-part evidence from classification
- Cross-file escalation at Moderate+ evidence includes scope guardrail
- Duplicate handling produces one entry with all authors and individual replies
- Conflict handling places chosen direction in A/B and rejected direction in B
- Cross-section leakage scan catches misplaced entries
- Post-write verification detects unfilled placeholders
- Reply endpoints are included but reply templates are not duplicated
