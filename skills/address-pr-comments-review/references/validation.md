# Validation & Regression

This file defines the validation and regression protocol -- the checklists and gate rules that ensure dossier integrity before handoff. It is responsible for defining:

- Architecture and structural checks (are reference files in place, do they have Precedence sections, is there no content overlap)
- The pre-write cross-reference scan (has the final confirmed table changed since Step 2.5 analysis)
- Decide Validity checklist (preserved from the archived validation-checklist.md for quick reference)
- Post-write dossier verification (file existence, valid markdown, count matching, no placeholder leakage, reply endpoint correctness)
- Reply integrity checks (pre-reply gate, duplicate reply prevention)
- New capability upgrade checks (thread_outdated rule, partially_addressed, cross-file escalation, zero-actionable table, duplicate reply prevention)
- Gate rules (when the skill must STOP and return to an earlier step)
- Regression scenarios (behaviors that future modifications must preserve, derived from eval-matrix.md)

## Precedence

Layer 4 (templates/checklists). Called by SKILL.md Step 4 (before and after dossier write) and Step 5 (handoff verification). Validation gates are enforced by the entry skill -- if a check fails, the skill must not proceed. Validation rules reference classification, cross-reference, and dossier protocols but do not override them. They are the last line of defense before handoff.

Validation checks take precedence over template defaults: if a check finds a structural violation (missing Precedence section, cross-file content duplication, placeholder leakage), the violation must be fixed before proceeding. No check is skippable.

---

## 1. Architecture and Structural Checks

Before any comment-level validation begins, verify the reference architecture itself is intact. These checks ensure the layered design has not been compromised by an incomplete edit, a missing file, or content drift.

### 1.1 Reference File Presence Scan

Verify every reference file exists at its expected path:

| File | Path | Criticality |
|------|------|-------------|
| overview.md | `references/overview.md` | 🔴 Missing breaks precedence model |
| classification.md | `references/classification.md` | 🔴 Missing breaks Step 2 |
| cross-reference.md | `references/cross-reference.md` | 🔴 Missing breaks Step 2.5 |
| interaction.md | `references/interaction.md` | 🔴 Missing breaks Steps 3-4 |
| dossier.md | `references/dossier.md` | 🔴 Missing breaks Step 4 |
| reply.md | `references/reply.md` | 🔴 Missing breaks downstream reply |
| platform.md | `references/platform.md` | 🟡 Missing means gh commands undocumented |
| validation.md (this file) | `references/validation.md` | 🔴 Missing means no gate enforcement |
| eval-matrix.md | `references/eval-matrix.md` | 🟡 Missing means regression coverage lost |

Action if 🔴 file is missing: STOP. Return to setup. The missing file must be created before proceeding.

### 1.2 Precedence Section Scan

Every reference file (except eval-matrix.md, which is a test suite not a protocol layer) MUST have a Precedence section at the top that states:

1. Its layer number (1/2/3/4)
2. Which SKILL.md step calls it
3. What it defers to and what defers to it
4. Any "final say" boundaries

Verify each file's Precedence section:

| File | Expected Layer | Must reference |
|------|---------------|----------------|
| overview.md | Meta (top of hierarchy) | Structure, no peers |
| classification.md | Layer 2 | SKILL.md Step 2 |
| cross-reference.md | Layer 2 | SKILL.md Step 2.5 |
| interaction.md | Layer 2 | Steps 3-4 |
| dossier.md | Layer 3 | Step 4 |
| reply.md | Layer 3 | Conclusion assignments |
| platform.md | Layer 4 | Step 1, Step 5 |
| validation.md | Layer 4 | Step 4 |

Violation scanning heuristic: if a reference file's Precedence section claims a different layer than shown above, or if it does not reference its caller step, flag as a structural defect.

### 1.3 Content Overlap Scan (No Duplicate Rules)

The layered architecture forbids the same rule from appearing in more than one reference file. If the same rule exists in two places, one is stale and the other is authoritative.

Scan these known cross-file boundaries for overlap:

| Rule type | Authoritative file | Must NOT appear in |
|-----------|-------------------|--------------------|
| Conclusion logic (valid/invalid/...) | classification.md | dossier.md, reply.md, interaction.md |
| Dedup detection logic | cross-reference.md | classification.md, interaction.md |
| Overview table format | interaction.md | dossier.md, classification.md |
| Reply template content | reply.md | dossier.md (contains endpoints only) |
| gh CLI commands | platform.md | Any other file |
| Validation checks | validation.md | SKILL.md (references by name only) |

If overlap is found between two files, the file at the LOWER layer in the precedence table defers -- but the rule should still be removed from the non-authoritative file to prevent drift.

### 1.4 Artifact Integrity Check

The `list_comments.py` script must be present at the skill root:

```bash
test -f skills/address-pr-comments-review/scripts/list_comments.py
```

If the script is missing, comment collection is impossible and the skill cannot proceed.

---

## 2. Decide Validity (Preserved from Archive)

This section is preserved from the archived `validation-checklist.md` as a quick-reference checklist for classifying individual comments. The authoritative classification rules live in `classification.md`; this section provides a condensed operational version for use during verification.

### 2.1 Conclusion Categories

Mark each comment as one of (mapping to classification.md conclusions):

| Category | When to use | Action |
|----------|-------------|--------|
| `valid` | Technically correct, in-scope, still applies to current HEAD | Code change + reply + commit |
| `invalid` | Incorrect claim, unsafe recommendation, contradicts conventions | Reply only |
| `already_fixed` | Issue no longer present at current HEAD | Reply only (cite evidence) |
| `already_replied` | `has_replies: true` with sufficient human reply | Skip -- no reply needed |
| `out_of_scope` | Valid concern but unrelated to PR scope | Reply only |
| `needs_clarification` | Ambiguous ask or missing acceptance criteria | Reply only (ask for direction) |
| `partially_addressed` | Fix attempted but incomplete or directionally wrong | Code change + reply (rework) |
| `informational` | Praise, LGTM, emoji, nit, retraction | No action |

**Distinctions to verify:**

- `thread_outdated` alone is NEVER `informational`. It requires code verification before classification. Only `minimized` allows skipping verification.
- `already_fixed` requires STRONG evidence: specific code citation or commit evidence. `thread_outdated: true` or `thread_resolved: true` are NOT evidence.
- `partially_addressed` requires the three-part evidence chain: fix attempt citation, remaining issue citation, insufficiency explanation.

### 2.2 Validate Bot Comments

For bot comments (CodeRabbit, Copilot, etc.):

1. Read any embedded "Prompt for AI Agents" block
2. Verify each suggested file/line exists on current HEAD
3. Reproduce or reason about the claimed issue
4. Apply only changes that improve correctness/safety/maintainability
5. Ignore purely mechanical changes that conflict with local conventions

### 2.3 Validate Human Comments

1. Identify intent (bug risk, style, scope, product behavior)
2. Confirm current behavior in code at the referenced path:line
3. Validate side effects and regressions of the suggested change
4. Prefer the reviewer's intent over literal wording when they differ

### 2.4 Evidence Requirements (Preserved)

Before marking any actionable conclusion (`valid`, `already_fixed`, `partially_addressed`), collect at least one form of evidence:

- File + line proof from current code at branch tip
- Failing check, warning, or linter output
- Reproducible behavior path

For `already_fixed` specifically, the evidence must be a specific code citation or commit reference. Speculative evidence ("looks different", "probably fixed") is insufficient.

---

## 3. Pre-Dossier Scan: Final Cross-Reference (Pre-Write)

Before writing the dossier, re-scan the final confirmed table (from Step 4) against the original cross-reference results (from Step 2.5). Discussion may have changed conclusions, revealed new connections, or created new duplicates.

### 3.1 8-Check Checklist

See `dossier.md` (Final Cross-Reference Scan section) for the complete 8-check checklist covering new duplicates, stale duplicates, unresolved conflicts, orphaned replies, new relations, cross-section leakage, reply target mismatch, and stale already_replied items.

### 3.2 Gate Rule

If any unresolved item remains after the scan, do NOT write the dossier. Return to Step 3. If all checks pass, proceed to write.

---

## 4. Post-Write Dossier Verification

After writing the dossier file, run these checks.

### 4.1 File Existence and Integrity

| Check | Command/Condition |
|-------|-------------------|
| File exists | `test -f .sisyphus/notepads/pr-<N>-dossier/dossier-<TIMESTAMP>.md` |
| Valid markdown | File starts with `# Review Dossier:` |
| Counts match | Executive Summary counts = actual items in each section (Section A + Section B + Section C = total items) |
| No placeholder left | No `{{...}}` template variables remain -- all should be substituted |
| Reply endpoint correct | Each reply task uses the endpoint matching its `{{REPLY_KIND}}` (inline/review/top_level) |
| Reply templates referenced correctly | Reply templates are referenced by name, not duplicated inline |
| Duplicate author coverage | Every merged entry lists all authors in the "Also noted by" field |
| Cross-file guardrail present | If cross-file escalation was triggered at Moderate+ evidence, a Scope Guardrail row exists |

### 4.2 No-Placeholder Leakage Check (Mandatory)

The dossier post-write check MUST scan for `{{...}}` template variables. Any unfilled placeholder means the dossier is incomplete and must be regenerated. This prevents Prometheus from receiving a dossier with gaps.

Common placeholders that must be filled:

- `{{PR_URL}}`, `{{BRANCH}}`, `{{REPO}}`, `{{TIMESTAMP}}`
- `{{REPLY_TEXT}}`, `{{FILE_PATH}}`, `{{LINE}}`, `{{COMMENT_ID}}`
- `{{DEV_CHANGES}}`, `{{TEST_STRATEGY}}`
- `{{NEW_DUP_CHECK}}`, `{{STALE_DUP_CHECK}}` (from the Cross-Reference Checks table)

---

## 5. Reply Integrity Checks

### 5.1 Pre-Reply Gate Verification

Before any reply is composed, verify:

| Check | Condition to pass | Action if failed |
|-------|-------------------|------------------|
| Already replied? | Thread has `has_replies: true` with sufficient human reply per cross-reference Level 2 | Block reply. Do not compose. |
| Duplicate author? | Comment is one of multiple merged as duplicates | Compose ONE reply, send to EACH author individually |
| Change summary needed? | Conclusion requires explanation alongside `Fixed in <sha>` (direction correction, partial fix, reframed concern, non-obvious change, cross-file pattern) | Add change summary before the SHA reference |
| Conclusion still valid? | Code state has not changed since classification (no new commits, no diff shift) | Re-verify conclusion against current HEAD |

### 5.2 Duplicate Reply Prevention

This is a pre-composition gate, evaluated BEFORE writing any reply content:

- If the thread already has a sufficient human reply: do NOT reply. The existing reply stands. This applies even if the existing reply is from a different person or takes a different tone.
- If the thread has an insufficient reply: default to blocked. Flag the insufficiency at Step 3 interaction. Do NOT proceed without explicit user override.
- If the comment is one of a merged duplicate set: compose ONE reply with identical content, send to EACH author via their own `in_reply_to` ID. Never reply to only one author of a duplicate set.

---

## 6. New Capability Upgrade Checks

These checks validate that the redesigned skill's new capabilities are working correctly. They supplement the core regression scenarios in Section 8.

### 6.1 thread_outdated Rule Check

When a comment has `thread_outdated: true`, verify the system did NOT:

- Classify it as `informational` by analogizing to `minimized` (known failure pattern)
- Skip code verification because "the diff is outdated"
- Default to `already_fixed` without reading the file at the referenced path:line

Expected behavior: the agent reads the current code at the comment's path:line on branch tip, then classifies based on what it finds. The classification MUST be accompanied by a verification note: "Verified against current HEAD at `<file>:<line>` -- `<finding>`."

### 6.2 partially_addressed Rule Check

When a comment has a visible fix attempt that is incomplete or wrong, verify the system:

- Did NOT classify as `already_fixed` (fix is not complete)
- Did NOT classify as `valid` without acknowledging the existing attempt
- DID include the three-part evidence chain: fix attempt citation, remaining issue citation, insufficiency explanation
- DID map to dossier Section A (requires code change + reply), not Section B
- DID include a reply that acknowledges the existing fix attempt before describing the correct direction

### 6.3 cross-file Escalation Check

When a comment flags a structural concern that exists in multiple files, verify the system:

- Performed a targeted search (grep or similar) for the same pattern in other files
- Applied the correct evidence-level action (observe at Weak, guardrail at Moderate, full escalation at Strong)
- Did NOT create additional Section A tasks for the uncommented files
- DID add a Scope Guardrail: "Fix only the commented file in this task"
- At Strong evidence: DID append a "Cross-File Pattern Detected" section

### 6.4 zero-actionable Table Check

When every comment is `informational`, `already_replied`, or `minimized`, verify:

- THE OVERVIEW TABLE STILL APPEARS. A statement like "0 actionable" is NOT a substitute.
- The table header `| # | 来源 | 类型 | 文件 | 摘要 | 结论 | 去重/冲突 | 讨论 |` is present
- All items are listed in the table (Section C treatment)
- A minimal dossier is still written (even if it contains Section C only)
- The executive summary shows 0 items in Sections A and B

### 6.5 duplicate-reply Prevention Check

When a duplicate concern exists across multiple reviewers, verify:

- Duplicates were detected and merged into one entry (Step 2.5)
- The dossier has ONE task entry for the merged concern, not separate tasks
- ALL authors are listed in the "Also noted by" field
- EACH author's `in_reply_to` ID is recorded in the dossier
- The reply policy composes ONE reply and sends it to each author individually
- The same fix is NOT applied twice

---

## 7. Gate Rules

### 7.1 The 🔴 Gate

If any 🔴 item remains unresolved after Step 4 interaction (conflicts unresolved, needs_clarification unanswered, high-risk valid items not acknowledged), the skill MUST NOT write the dossier. It must return to Step 3 for further discussion.

This is a hard gate -- no override, no workaround. The 🔴 status is determined by the interaction protocol (Step 3.5, Discussion Gating table).

### 7.2 Confirmation Gate

Step 3 user confirmation is required before Step 4 dossier generation. Confirmation equivalents:

- "ok", "yes", "looks good", "proceed", "confirmed"
- Any affirmative response

If the user does not explicitly confirm, the skill must ask: "Shall I proceed with dossier generation based on this final table?" Dossier generation must not proceed without explicit confirmation.

### 7.3 How to Block

When a check fails:

1. **State the failure**: "Validation check failed: [check name]. [Detail of what was found]."
2. **Explain the consequence**: "This means the dossier cannot be written / the handoff cannot proceed."
3. **Provide the corrective action**: "Return to Step [N] and [specific fix]."
4. **Do NOT proceed until the check passes.**

---

## 8. Regression Scenarios

The following scenarios must continue to work correctly after any protocol change. They are derived from the eval matrix (`eval-matrix.md`) and cover both preserved behaviors from the old system and new capabilities from the redesign.

### 8.1 Scenario Reference Table

| # | Token | Source | Key Failure Pattern | Validation Item |
|---|-------|--------|--------------------|-----------------|
| 1 | `thread_outdated unresolved` | PR #1215, `discussion_r3257258893` | Conflating `thread_outdated` with `minimized`; skipping code verification | Must read current code at path:line before classifying; must NOT short-circuit to `informational` |
| 2 | `thread_outdated + thread_resolved` | Synthetic | Assuming `thread_outdated` = already fixed without verifying | Both flags together still require code verification; neither flag is evidence of fix-state |
| 3 | `minimized comment` | SKILL.md Step 2 edge cases | Treating as actionable; replying to retracted comment | Must classify as `informational`; no code verification needed; no reply; no dossier entry beyond Section C |
| 4 | `zero-actionable` | Deviation analysis | Skipping mandatory overview table; omitting dossier | Overview table is MANDATORY even when zero items are actionable; header, rows, and legend must all appear; minimal dossier must still be written |
| 5 | `partially_addressed` | PR #1215, `discussion_r3257258893` | Accepting incomplete fix as resolved; missing direction error | Must include three-part evidence chain; must map to Section A; reply must acknowledge existing attempt |
| 6 | `duplicate reply` | PR #1215 patterns | Creating duplicate tasks; replying only once for multiple authors | One task entry; all authors listed; each author gets individual reply via own `in_reply_to` ID; same fix not applied twice |
| 7 | `cross-file` | PR #1215 deviation analysis | Scope creep; fixing uncommented files without guardrail | Fix commented file only; cross-file pattern documented as guardrail; no additional Section A tasks created; Moderate evidence requires guardrail row; Strong evidence requires dedicated section |

### 8.2 Detailed Scenario Checks

#### Scenario 1: thread_outdated unresolved

A comment with `thread_outdated: true` where the issue still exists in current code.

| Check | Expected | Verification method |
|-------|----------|---------------------|
| Classification | `valid` (not `informational`) | Verify agent read current code at path:line before deciding |
| Code verification | Must read file at referenced path:line on current HEAD | Look for verification note in output |
| Verification note | "Verified against current HEAD at `<file>:<line>` -- issue still present" | Present in classification reasoning or dossier entry |
| Dossier section | Section A (code change + reply) | Dossier task in Section A |
| Regression guard | Does NOT conflate `thread_outdated` with `minimized` | Apply 6.1 thread_outdated Rule Check |

#### Scenario 2: thread_outdated + thread_resolved

A thread is both outdated AND resolved, and the code at branch tip has actually been fixed.

| Check | Expected | Verification method |
|-------|----------|---------------------|
| Classification | `already_fixed` (not `valid`) | Must verify against current code first |
| Code verification | Must read current code at path:line | Look for code citation in evidence |
| Reply | Reply only (no code change) | Dossier entry in Section B |
| Evidence | Specific code citation showing the fix | Must cite exact file:line or commit sha |
| Regression guard | `thread_resolved` alone is NOT evidence of fix | Evidence must be code-based, not metadata-based |

#### Scenario 3: minimized comment

A comment minimized (hidden) by its author.

| Check | Expected | Verification method |
|-------|----------|---------------------|
| Classification | `informational` | No code verification performed |
| Reply | No reply | No reply entry in dossier |
| Dossier section | Section C only | Not in Section A or B |
| Overview table | Listed with `(minimized)` note | Row exists in overview table |
| Regression guard | `minimized` and `thread_outdated` are NOT conflated | Agent treats them as completely different signals |

#### Scenario 4: zero-actionable

All comments are `informational`, `already_replied`, or `minimized`.

| Check | Expected | Verification method |
|-------|----------|---------------------|
| Overview table present | Full table with header row | Visual inspection of output |
| Table header | `| # | 来源 | 类型 | 文件 | 摘要 | 结论 | 去重/冲突 | 讨论 |` | Must match exactly |
| Executive summary | Shows 0 in Sections A and B | Counts in dossier |
| Dossier written | Minimal dossier exists with Section C only | File existence check |
| Reply count | 0 replies composed | None skipped, none written |
| Regression guard | "0 actionable" never substitutes for the table | Table is always produced regardless of count |

#### Scenario 5: partial fix (partially_addressed)

A fix attempt exists but is incomplete or directionally wrong.

| Check | Expected | Verification method |
|-------|----------|---------------------|
| Classification | `partially_addressed` | Not `already_fixed` or `valid` |
| Three-part evidence | Fix attempt citation, remaining issue citation, insufficiency explanation | All three present in dossier entry |
| Dossier section | Section A (code change + reply) | Task in Section A |
| Reply content | Acknowledges existing fix attempt, explains insufficiency, describes correct fix direction | Follows reply.md Section 2 format |
| Regression guard | Does NOT jump to "Fixed in <sha>" without context | Change summary is present |

#### Scenario 6: duplicate reply

Multiple reviewers flag the same or overlapping concern.

| Check | Expected | Verification method |
|-------|----------|---------------------|
| Duplicate detection | Cross-reference Step 2.5 identified the merge | Duplicate entry in overview table with `≡ merged` |
| Dossier entry | One task entry, not two | Single Section A entry |
| Author listing | All authors listed in "Also noted by" | Field present in dossier task entry |
| Individual reply IDs | Each author's `in_reply_to` ID recorded | Listed in dossier or reply plan |
| Reply strategy | One reply, sent to each author individually | One composition, N API calls |
| Same fix | Applied exactly once | One code change task |
| Regression guard | Never creates separate tasks for duplicates | Counts reflect merged total, not raw number |

#### Scenario 7: cross-file

Same pattern exists in multiple files; agent must fix only the commented file.

| Check | Expected | Verification method |
|-------|----------|---------------------|
| Classification | `valid` for the commented file | Section A task for one file |
| Additional tasks | NO additional Section A tasks for other files | Only one code-change task |
| Scope Guardrail | Present at Moderate evidence: "Fix only the commented file" | Guardrail row exists in dossier |
| Cross-File section | Present at Strong evidence with file list and follow-up recommendation | Section exists in dossier before Scope Guardrails |
| Reply | Optionally notes the cross-file pattern | Reply mentions N other files with same pattern |
| Cross-file search | Targeted grep or similar search was performed | Evidence of search in cross-reference output |
| Regression guard | Does NOT scope-creep to fix uncommented files | No additional code changes beyond the one commented file |

### 8.3 Scenario Reference Map (from eval-matrix.md)

| # | Token | Source | Key Risk |
|---|-------|--------|----------|
| 1 | `thread_outdated unresolved` | PR #1215, `discussion_r3257258893` | Conflating `thread_outdated` with `minimized`; skipping code verification |
| 2 | `thread_outdated + thread_resolved` | Synthetic | Assuming `thread_outdated` = already fixed without verifying |
| 3 | `minimized comment` | SKILL.md Step 2 edge cases | Treating as actionable; replying to retracted comment |
| 4 | `zero-actionable` | Deviation analysis | Skipping mandatory overview table; omitting dossier |
| 5 | `partial fix` | PR #1215, `discussion_r3257258893` | Accepting incomplete fix as resolved; missing direction error |
| 6 | `duplicate reply` | PR #1215 patterns | Creating duplicate tasks; replying only once for multiple authors |
| 7 | `cross-file` | PR #1215 deviation analysis | Scope creep; fixing uncommented files without guardrail |

---

## Key Design Decisions

### Two-Phase Verification

Verification happens in two distinct phases:

1. **Pre-write scan** (before dossier generation): Cross-reference the final confirmed table against original cross-reference results. This catches changes that happened during discussion.
2. **Post-write checks** (after dossier write): Verify the dossier file itself is complete and correct. This catches generation errors.

Both phases must pass. The entry skill enforces this.

### Validation Is the Last Line of Defense

The validation protocol is the final quality gate before handoff. Every upstream protocol -- classification, cross-reference, interaction, dossier, reply -- has its own rules and quality standards. Validation does NOT re-check those rules. It checks for failures that can only be detected at the aggregate level: structural integrity, cross-file consistency, placeholder completeness, and regression coverage.

### Structural Checks Guard Against Architecture Decay

The file presence, Precedence section, and content overlap scans (Section 1) exist to prevent the layered architecture from degrading through repeated edits. Without these checks, a new contributor could add a rule to the wrong file, omit a Precedence section, or duplicate content across layers. These checks are the architectural immune system.

### Archived Material Preserved as Operational Checklist

The Decide Validity section (Section 2) is preserved from the archived `validation-checklist.md`. Its purpose has shifted: it is no longer the canonical source of truth for classification (that role moved to `classification.md`). Instead, it serves as a quick-reference operational checklist for verification tasks. This prevents regression from the old system while correctly reflecting the new layered architecture.

### Regression Is a Hard Block

If a regression scenario check fails (Section 8), the change that caused the regression must be reverted. Regression passing is a mandatory gate, not a suggestion. The eval matrix (`eval-matrix.md`) defines the acceptance criteria; this file defines the verification procedure.
