# Dossier Contract

This file defines the dossier contract: the structure, content rules, evidence requirements, and quality checks for the review dossier generated after successful interaction (Step 4). The dossier is the final deliverable of Phase 1. It is a requirements document that captures every confirmed decision from Steps 2-4 and feeds Prometheus (Phase 2) for execution plan generation.

## Precedence

Layer 3 (decision protocols). Consumes output from classification (Step 2), cross-reference (second half of Step 2), and interaction (Steps 3-4). Dossier rules take precedence over template defaults. Reply policy source is `reply.md`.

---

## Scope

This file covers: Executive Summary format, Reply endpoints (gh api commands only), Section A/B/C rules with required fields and evidence, Duplicate/Conflict handling, Cross-section leakage prevention, 8-check Cross-Reference Scan, Dependencies, Scope guardrails, and Post-write verification.

### Out of Scope

Classification -> `classification.md`. Cross-reference logic -> `cross-reference.md`. Interaction -> `interaction.md`. Platform paths -> `platform.md`. Validation checks -> `validation.md`. Reply template content -> `reply.md`.

---

## Executive Summary Format

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


See `validation.md` (Section 1: Pre-Dossier Scan) for the complete 8-Check Checklist.

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

If any check fails, fix and re-verify. The validation protocol (`validation.md`) provides the definitive gate rules.

---
## Key Design Decisions
### Dossier Is Not a Plan

A requirements document, not an execution plan. Phase 2 generates plans via Prometheus. No execution logic, dependency graphs, or scheduling decisions.

### Evidence Requirements Are Protocol-First

Dossier entries for `partially_addressed` and cross-file escalation MUST include evidence from upstream protocols, not re-evaluate it. Ensures traceability (every claim has an upstream source) and prevents undocumented assertions.

## Reliability and Compatibility

### Downstream Consumers

Prometheus parses executive summary for task counts, one implementation task per Section A, one reply per Section B. Section C generates no tasks.

### Section A/B/C Compatibility

Fixed semantics -- must NOT be renamed or reordered. Coordinate changes with SKILL.md, `reply.md`, and Prometheus.

| Section | Semantics | Action |
|---------|-----------|--------|
| Section A | Code change + reply | Tests, commit, reply inline |
| Section B | Reply only | No code changes, reply explains decision |
| Section C | No action | Skip entirely |

### Regression Boundaries

The following behaviors must survive any dossier structure change:
- `partially_addressed` entries include three-part evidence from classification
- Cross-file escalation at Moderate+ evidence includes scope guardrail
- Duplicate handling produces one entry with all authors and individual replies
- Conflict handling places chosen direction in A/B and rejected direction in B
- Cross-section leakage scan catches misplaced entries
- Post-write verification detects unfilled placeholders
- Reply endpoints are included but reply templates are not duplicated
