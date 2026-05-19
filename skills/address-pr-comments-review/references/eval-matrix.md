# Eval Matrix: address-pr-comments-review

> **Canonical scenario corpus** for the address-pr-comments-review skill. This file is the authoritative source for the seven regression scenarios and QA tokens referenced by `validation.md`.
>
> **RED Phase artifact.** Defines expected behavior the redesign must preserve and the failure modes it must newly cover.
> Each scenario specifies 4 dimensions: expected classification, expected reply posture, expected overview-table treatment, and whether dossier escalation is required.

---

## Required Scenarios

### 1. thread_outdated unresolved

**Description:** A comment has `thread_outdated: true` (GitHub indicates PR diff context shifted), but the issue still exists in the current code at branch tip. The agent must NOT conflate `thread_outdated` with `minimized`. It must read the actual file at the referenced `path:line` on current HEAD before classifying.

**Origin:** PR #1215 (`peatio/coffer`, `discussion_r3257258893`). Comment on `server/monitor/monitor.go:47` flagged `CloseAllPublishers()` called before `manager.StopAll()`. `thread_outdated: true`. Actual code at branch tip still had the same bug.

| Dimension | Expected Value |
|-----------|---------------|
| expected classification | `valid` — must first verify by reading current code at the comment's `path:line`. If issue persists, classify as `valid`. |
| expected reply posture | Reply confirming fix applied after code change. |
| expected overview-table | Section A entry, conclusion `valid`, with a note: "thread_outdated verified against current HEAD — issue still present." |
| expected dossier escalation | Yes — Section A (code change + reply). Must include exact file path, line, and specific code modification. |

**Failure pattern (observed):** AI classified as `informational` by analogizing to `minimized` without reading current code. Missing `thread_outdated` rule in edge cases table.

---

### 2. thread_outdated + thread_resolved

**Description:** A thread is simultaneously `thread_outdated` (diff context shifted) AND the code at branch tip has actually been fixed. The issue no longer exists. The agent must read current code to determine that the concern is moot.

**Origin:** Synthetic scenario — the ` + ` combination of both flags. `thread_outdated` alone does not mean the fix was applied; only code verification can confirm.

| Dimension | Expected Value |
|-----------|---------------|
| expected classification | `already_fixed` — must verify against current code first, then classify as resolved. |
| expected reply posture | Reply only (no code changes). Confirm the concern is already addressed in current code. |
| expected overview-table | Section B entry, conclusion `already_fixed`, with note: "Outdated thread — code at HEAD already addresses this concern." |
| expected dossier escalation | No — Section B (reply only). No code change, no test, no commit. |

**Key rule:** `thread_outdated` is NEVER a shortcut to skip code verification. Always read current code first. Only `minimized` allows skipping verification.

---

### 3. minimized comment

**Description:** A comment is minimized (hidden) by its author in the GitHub UI. This means the author retracted or replaced the comment. No action is needed.

**Origin:** Documented in current SKILL.md Step 2 edge cases. Preserved as a regression guard.

| Dimension | Expected Value |
|-----------|---------------|
| expected classification | `informational` — no code verification needed. The author explicitly retracted the comment. |
| expected reply posture | No reply. The comment was withdrawn by its author. |
| expected overview-table | Section C entry, listed as informational with a `(minimized)` note. |
| expected dossier escalation | No — Section C (informational, no action). |

**Distinction from thread_outdated:** `minimized` = author explicitly withdrew. `thread_outdated` = diff context shifted; code must be verified. These are NOT the same and must never be conflated.

---

### 4. zero-actionable

**Description:** All PR comments are informational (LGTM, emoji, praise, FYI) or already replied. Zero actionable items. The agent must still produce the overview table and a minimal dossier.

**Origin:** Deviation analysis documented this failure: AI concluded "0 actionable" and skipped the overview table entirely. User had to request the table explicitly.

| Dimension | Expected Value |
|-----------|---------------|
| expected classification | All items are `informational` or `already_replied`. No `valid` / `invalid` / `needs_clarification` items. |
| expected reply posture | No replies needed. |
| expected overview-table | **Must still produce the full table.** All items listed in Section C. Table header `| # | 来源 | 类型 | 文件 | 摘要 | 结论 | 去重/冲突 | 讨论 |` is mandatory regardless of result. |
| expected dossier escalation | No — Section C only. But a minimal dossier must still be written with the note that nothing is actionable. |

**Failure pattern (observed):** AI concluded nothing to do and skipped the mandatory overview table. "0 actionable" is NOT a valid reason to omit the table.

---

### 5. partial fix

**Description:** A code change was applied in response to a review comment, but the fix is incomplete or directionally wrong. The issue is partially addressed but not fully resolved.

**Origin:** PR #1215 (`discussion_r3257258893`). The dev added `CloseAllPublishers()` before `manager.StopAll()`, but the real problem is the opposite ordering — publishers should close AFTER stop completes. The fix exists but worsens the underlying issue.

| Dimension | Expected Value |
|-----------|---------------|
| expected classification | `partially_addressed` — the fix attempt does not resolve the concern. Re-classify as `partially_addressed` requiring a corrected fix. |
| expected reply posture | Reply explaining the current fix is insufficient and the direction needs correction. Then code change + reply. |
| expected overview-table | Section A entry, conclusion `valid`, with note: "Partial fix applied but direction is incorrect — requires redo." |
| expected dossier escalation | Yes — Section A (rework the fix: code change + reply). Must describe the correct fix direction and the specific file/line to change. |

**Edge case within partial fix:** If the partial fix actually resolves the concern partially and the remaining issue is cosmetic/minor, it could be `already_fixed` for the resolved part plus a new `valid` for the remainder. Default to `partially_addressed` unless the core concern is genuinely resolved.

**Token-to-conclusion mapping:** The `partial fix` scenario token maps to the `partially_addressed` classification conclusion defined in `classification.md`.

---

### 6. duplicate reply

**Description:** Multiple reviewers (e.g., a human and CodeRabbit/Copilot) flag the same or substantially overlapping concern on the same code. The agent must detect this as a duplicate, merge the entries, and produce ONE code change task with replies to EACH author individually.

**Origin:** PR #1215 patterns. Multiple reviewers independently flagged the publisher shutdown ordering issue. Risk of replying twice with the same information or applying the fix twice in parallel.

| Dimension | Expected Value |
|-----------|---------------|
| expected classification | Cross-reference check detects duplicate. Merged into one entry with all authors noted. If the common concern is valid, conclusion is `valid`. |
| expected reply posture | One code change. Then reply to EACH author individually using their own `in_reply_to` ID. Same reply content for all duplicate authors. |
| expected overview-table | Merged single entry with multiple authors listed (e.g., `@copilot, @alice`). Conclusion `valid`. Note: `≡ merged (N reviews)`. |
| expected dossier escalation | Yes — Section A (one code change task). Dossier must list ALL duplicate authors and their individual `in_reply_to` IDs. Dedup count in Executive Summary. |

**Critical rule:** Never create separate Section A tasks for duplicate comments. Never reply to one author without replying to the others. Never apply the same fix twice.

---

### 7. cross-file

**Description:** A review comment flags an issue in one file, but the same pattern exists in multiple other files across the codebase. The agent must fix the commented file and document the cross-file pattern as a guardrail note — but must NOT scope-creep by fixing all occurrences unless explicitly instructed.

**Origin:** Deviation analysis (PR #1215): `CloseAllPublishers()` ordering issue existed in `server/monitor/monitor.go` (commented file) plus 4 other files in `server/`. The agent identified the cross-file pattern but needed guardrails to scope the fix to the commented file only.

| Dimension | Expected Value |
|-----------|---------------|
| expected classification | `valid` for the commented file. Cross-file pattern noted as a dossier guardrail — NOT additional actionable items. |
| expected reply posture | Fix the commented file + reply. In the reply, note that the same pattern exists in other files and offer to address in a follow-up. |
| expected overview-table | Section A entry for the commented file. No additional entries for other files (they are noted in dossier guardrails, not as tasks). |
| expected dossier escalation | Yes — Section A for the commented file. Dossier must include a Scope Guardrail item: "Cross-file pattern detected in [file list] — fix only the commented file in this task. Do not scope-creep to other files. Consider a separate follow-up PR." |

**Edge case within cross-file:** If all instances are trivial changes and the comment explicitly asks "fix this everywhere", the agent may classify additional files as duplicates or extensions. Default is to scope-creep guardrail unless the user or reviewer explicitly requests global fix.

---

## Scenario Reference Map

| # | Token | Source | Key Risk |
|---|-------|--------|----------|
| 1 | `thread_outdated unresolved` | PR #1215, `discussion_r3257258893` | Conflating `thread_outdated` with `minimized`; skipping code verification |
| 2 | `thread_outdated + thread_resolved` | Synthetic | Assuming `thread_outdated` = already fixed without verifying |
| 3 | `minimized comment` | SKILL.md Step 2 edge cases | Treating as actionable; replying to retracted comment |
| 4 | `zero-actionable` | Deviation analysis | Skipping mandatory overview table; omitting dossier |
| 5 | `partial fix` | PR #1215, `discussion_r3257258893` | Accepting incomplete fix as resolved; missing direction error |
| 6 | `duplicate reply` | PR #1215 patterns | Creating duplicate tasks; replying only once for multiple authors |
| 7 | `cross-file` | Deviation analysis, 4 server files | Scope creep; fixing uncommented files without guardrail |

## QA Check Tokens

The following tokens MUST appear in this file for automated QA:

- `thread_outdated unresolved`
- `thread_outdated + thread_resolved`
- `minimized comment`
- `zero-actionable`
- `partial fix`
- `duplicate reply`
- `cross-file`
- `expected classification`
- `expected reply posture`
- `expected overview-table`
- `expected dossier escalation`
