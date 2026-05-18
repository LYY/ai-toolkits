# Validation & Regression

This file defines the validation and regression protocol -- the checklists and gate rules that ensure dossier integrity before handoff. It covers: pre-write cross-reference scan, post-write dossier verification, new capability upgrade checks, gate rules (🔴 gate, confirmation gate, block procedure), and regression scenarios (preserved behaviors from eval-matrix.md).

## Precedence

Layer 4 (templates/checklists). Called by SKILL.md Step 4 (before and after dossier write) and Step 5 (handoff verification). Validation gates are enforced by the entry skill -- if a check fails, the skill must not proceed. Validation rules reference classification, cross-reference, and dossier protocols but do not override them. No check is skippable.

---

For classification rules, see `references/classification.md`. For regression scenarios, see `references/eval-matrix.md`.

---

## 1. Pre-Dossier Scan: Final Cross-Reference (Pre-Write)

Before writing the dossier, re-scan the final confirmed table from Step 4 against the original cross-reference results. Discussion may have changed conclusions, revealed new connections, or created new duplicates. See `dossier.md` (Final Cross-Reference Scan section) for the complete 8-check checklist.

**Gate rule**: If any unresolved item remains after the scan, do NOT write the dossier. Return to Step 3.

---

## 2. Post-Write Dossier Verification

After writing the dossier file, run these checks.

### 2.1 File Existence and Integrity

| Check | Command/Condition |
|-------|-------------------|
| File exists | `test -f .sisyphus/notepads/pr-<N>-dossier/dossier-<TIMESTAMP>.md` |
| Valid markdown | File starts with `# Review Dossier:` |
| Counts match | Executive Summary counts = actual items in each section |
| No placeholder left | No `{{...}}` template variables remain |
| Reply endpoint correct | Each reply task uses the endpoint matching its REPLY_KIND (inline/review/top_level) |

### 2.2 No-Placeholder Leakage Check (Mandatory)

Any unfilled `{{...}}` placeholder means the dossier is incomplete and must be regenerated. Common placeholders: `{{PR_URL}}`, `{{BRANCH}}`, `{{REPO}}`, `{{TIMESTAMP}}`, `{{REPLY_TEXT}}`, `{{FILE_PATH}}`, `{{LINE}}`, `{{COMMENT_ID}}`, `{{DEV_CHANGES}}`, `{{TEST_STRATEGY}}`, `{{NEW_DUP_CHECK}}`, `{{STALE_DUP_CHECK}}`.

**Gate rule**: If any placeholder remains unfilled, do NOT hand off to Prometheus. Regenerate the dossier.

---

## 3. New Capability Upgrade Checks

These checks validate that the redesigned skill's new capabilities are working correctly. They supplement the core regression scenarios in Section 5.

### 3.1 thread_outdated Rule Check
When a comment has `thread_outdated: true`, verify the system did NOT:
- Classify it as `informational` by analogizing to `minimized` (known failure pattern)
- Skip code verification because "the diff is outdated"
- Default to `already_fixed` without reading the file at the referenced path:line

Expected behavior: the agent reads the current code at the comment's path:line on branch tip, then classifies based on what it finds. The classification MUST be accompanied by a verification note: "Verified against current HEAD at `<file>:<line>` -- `<finding>`."

### 3.2 partially_addressed Rule Check
When a comment has a visible fix attempt that is incomplete or wrong, verify the system:
- Did NOT classify as `already_fixed` (fix is not complete)
- Did NOT classify as `valid` without acknowledging the existing attempt
- DID include the three-part evidence chain: fix attempt citation, remaining issue citation, insufficiency explanation
- DID map to dossier Section A (requires code change + reply), not Section B
- DID include a reply that acknowledges the existing fix attempt before describing the correct direction

### 3.3 cross-file Escalation Check
When a comment flags a structural concern that exists in multiple files, verify the system:
- Performed a targeted search (grep or similar) for the same pattern in other files
- Applied the correct evidence-level action (observe at Weak, guardrail at Moderate, full escalation at Strong)
- Did NOT create additional Section A tasks for the uncommented files
- DID add a Scope Guardrail: "Fix only the commented file in this task"
- At Strong evidence: DID append a "Cross-File Pattern Detected" section

### 3.4 zero-actionable Table Check
When every comment is `informational`, `already_replied`, or `minimized`, verify:
- THE OVERVIEW TABLE STILL APPEARS. A statement like "0 actionable" is NOT a substitute.
- The table header `| # | 来源 | 类型 | 文件 | 摘要 | 结论 | 去重/冲突 | 讨论 |` is present
- All items are listed in the table (Section C treatment)
- A minimal dossier is still written (even if it contains Section C only)
- The executive summary shows 0 items in Sections A and B

### 3.5 duplicate-reply Prevention Check
When a duplicate concern exists across multiple reviewers, verify:
- Duplicates were detected and merged into one entry
- The dossier has ONE task entry for the merged concern, not separate tasks
- ALL authors are listed in the "Also noted by" field
- EACH author's `in_reply_to` ID is recorded in the dossier
- The reply policy composes ONE reply and sends it to each author individually
- The same fix is NOT applied twice

---

## 4. Gate Rules

### 4.1 The 🔴 Gate
If any 🔴 item remains unresolved after Step 4 interaction (conflicts unresolved, needs_clarification unanswered, high-risk valid items not acknowledged), the skill MUST NOT write the dossier. It must return to Step 3 for further discussion. This is a hard gate -- no override, no workaround.

### 4.2 Confirmation Gate
Step 3 user confirmation is required before Step 4 dossier generation. Confirmation equivalents: "ok", "yes", "looks good", "proceed", "confirmed", or any affirmative response. If the user does not explicitly confirm, the skill must ask: "Shall I proceed with dossier generation based on this final table?" Dossier generation must not proceed without explicit confirmation.

### 4.3 How to Block
When a check fails:
1. **State the failure**: "Validation check failed: [check name]. [Detail of what was found]."
2. **Explain the consequence**: "This means the dossier cannot be written / the handoff cannot proceed."
3. **Provide the corrective action**: "Return to Step [N] and [specific fix]."
4. **Do NOT proceed until the check passes.**

---

## 5. Regression Scenarios
The following scenarios must continue to work correctly after any protocol change. They are derived from the eval matrix (`eval-matrix.md`) and cover both preserved behaviors from the old system and new capabilities from the redesign.

### 5.1 Scenario Reference Table

| # | Token | Source | Key Failure Pattern | Validation Item |
|---|-------|--------|--------------------|-----------------|
| 1 | `thread_outdated unresolved` | PR #1215, `discussion_r3257258893` | Conflating `thread_outdated` with `minimized`; skipping code verification | Must read current code at path:line before classifying; must NOT short-circuit to `informational` |
| 2 | `thread_outdated + thread_resolved` | Synthetic | Assuming `thread_outdated` = already fixed without verifying | Both flags together still require code verification; neither flag is evidence of fix-state |
| 3 | `minimized comment` | SKILL.md Step 2 edge cases | Treating as actionable; replying to retracted comment | Must classify as `informational`; no code verification needed; no reply; no dossier entry beyond Section C |
| 4 | `zero-actionable` | Deviation analysis | Skipping mandatory overview table; omitting dossier | Overview table is MANDATORY even when zero items are actionable; header, rows, and legend must all appear; minimal dossier must still be written |
| 5 | `partially_addressed` | PR #1215, `discussion_r3257258893` | Accepting incomplete fix as resolved; missing direction error | Must include three-part evidence chain; must map to Section A; reply must acknowledge existing attempt |
| 6 | `duplicate reply` | PR #1215 patterns | Creating duplicate tasks; replying only once for multiple authors | One task entry; all authors listed; each author gets individual reply via own `in_reply_to` ID; same fix not applied twice |
| 7 | `cross-file` | PR #1215 deviation analysis | Scope creep; fixing uncommented files without guardrail | Fix commented file only; cross-file pattern documented as guardrail; no additional Section A tasks created; Moderate evidence requires guardrail row; Strong evidence requires dedicated section |

### 5.2 Detailed Scenario Checks
#### Scenario 1: thread_outdated unresolved
A comment with `thread_outdated: true` where the issue still exists in current code.

| Check | Expected | Verification method |
|-------|----------|---------------------|
| Classification | `valid` (not `informational`) | Verify agent read current code at path:line before deciding |
| Code verification | Must read file at referenced path:line on current HEAD | Look for verification note in output |
| Verification note | "Verified against current HEAD at `<file>:<line>` -- issue still present" | Present in classification reasoning or dossier entry |
| Dossier section | Section A (code change + reply) | Dossier task in Section A |
| Regression guard | Does NOT conflate `thread_outdated` with `minimized` | Apply 3.1 thread_outdated Rule Check |

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
| Overview table present | Full table with header row | Verify table header is present in output |
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
| Duplicate detection | Cross-reference identified the merge | Duplicate entry in overview table with `≡ merged` |
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

### 5.3 Scenario Reference Map (from eval-matrix.md)

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


If a regression scenario check fails (Section 5), the change that caused the regression must be reverted. Regression passing is a mandatory gate, not a suggestion. The eval matrix (`eval-matrix.md`) defines the acceptance criteria; this file defines the verification procedure.
