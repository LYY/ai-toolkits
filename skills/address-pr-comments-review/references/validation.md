# Validation & Regression

This file defines the validation and regression protocol -- the checklists and gate rules that ensure dossier integrity before handoff. It covers: pre-write cross-reference scan, post-write dossier verification, gate rules (🔴 gate, confirmation gate, block procedure), and regression scenarios.

`eval-matrix.md` is the canonical scenario corpus. This file defines the verification gates; `eval-matrix.md` defines the behavioral acceptance criteria.

## Precedence

Layer 4 (templates/checklists). Called by SKILL.md Step 4 (before and after dossier write) and Step 5 (handoff verification). Validation gates are enforced by the entry skill -- if a check fails, the skill must not proceed. Validation rules reference classification, cross-reference, and dossier protocols but do not override them. No check is skippable.

---

For classification rules, see `references/classification.md`. For regression scenarios, see `references/eval-matrix.md`.

---

## 1. Pre-Dossier Scan: Final Cross-Reference (Pre-Write)

Before writing the dossier, re-scan the final confirmed table from Step 4 against the original cross-reference results. Discussion may have changed conclusions, revealed new connections, or created new duplicates.

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

## 3. Capability Upgrade Checks

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

`eval-matrix.md` is the canonical scenario corpus. This file defines the verification gates; `eval-matrix.md` defines the behavioral acceptance criteria. The following reference table provides a quick lookup for each scenario; the full 4-dimension specification (expected classification, reply posture, overview-table treatment, dossier escalation) lives in `eval-matrix.md`.

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

---

If a regression scenario check fails (Section 5), the change that caused the regression must be reverted. Regression passing is a mandatory gate, not a suggestion. The eval matrix (`eval-matrix.md`) defines the acceptance criteria; this file defines the verification procedure.
