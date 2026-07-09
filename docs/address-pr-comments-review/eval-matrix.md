# Eval Matrix: address-pr-comments-review

> **Behavioral acceptance criteria** for the address-pr-comments-review skill.
> Each scenario defines behavior a maintainer can regression review. Review dimensions stay close to the runtime phase being protected: current checkout binding, classification, reply posture, overview-table treatment, dossier escalation, generated plan shape, or post reply read-back.
> Used to verify skill behavior correctness during development and regression testing.

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

**Description:** All PR comments are informational (LGTM, emoji, praise, FYI) or already replied. Zero actionable items. The agent must still produce the overview table. No dossier is needed — the Post-Confirmation Routing gate detects Section A=0, Section B=0 and ends.

**Origin:** Deviation analysis documented this failure: AI concluded "0 actionable" and skipped the overview table entirely. User had to request the table explicitly.

| Dimension | Expected Value |
|-----------|---------------|
| expected classification | All items are `informational` or `already_replied`. No `valid` / `invalid` / `needs_clarification` items. |
| expected reply posture | No replies needed. |
| expected overview-table | **Must still produce the full table.** All items listed in Section C. Table header `| # | 来源 | 类型 | 文件 | 摘要 | 结论 | 去重/冲突 | 讨论 |` is mandatory regardless of result. |
| expected dossier escalation | No — dossier generation is skipped entirely. The Post-Confirmation Routing gate (A=0, B=0) ends without dossier. |

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

**Token-to-conclusion mapping:** The `partial fix` scenario token maps to the `partially_addressed` classification conclusion defined in `classify.md`.

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
| 4 | `zero-actionable` | Deviation analysis | Skipping mandatory overview table; generating unnecessary dossier for zero-actionable PRs |
| 5 | `partial fix` | PR #1215, `discussion_r3257258893` | Accepting incomplete fix as resolved; missing direction error |
| 6 | `duplicate reply` | PR #1215 patterns | Creating duplicate tasks; replying only once for multiple authors |
| 7 | `cross-file` | Deviation analysis, 4 server files | Scope creep; fixing uncommented files without guardrail |
| 8 | `single-worktree no prompt` | Synthetic worktree regression | Prompting unnecessarily or leaving `TARGET_WORKTREE_ROOT` unset |
| 9 | `current linked worktree default binding` | Synthetic worktree regression | Binding local reads to launch directory instead of target checkout |
| 10 | `explicit PR branch mismatch blocks collection` | Synthetic worktree regression | Collecting comments for a PR whose head branch does not match the bound checkout |
| 11 | `default local-state artifact path` | Artifact storage decoupling | Writing disposable artifacts into repo state or `.omo` by default |
| 12 | `generated-plan reply tasks for Section A/B` | Task 4 handoff design | Dropping Section B reply task items from generated plan |
| 13 | `reply-only posting and read-back` | Reply-only workflow regression | Generating needless plan or skipping post reply read-back |
| 14 | `direct-fix fast path` | PR #2166, simple proto field rename | Forcing a full Prometheus plan for a one-file low-risk change, or bypassing reply/read-back duties |
| 15 | `dossier accuracy grill gate` | Simple-path and ambiguous-dossier regression | Writing a dossier or brief while unresolved implementation, scope, test, or reply ambiguity remains |
| 16 | `direct fix brief retaining PR reply fields` | Direct-fix handoff regression | Losing comment ID, endpoint, `in_reply_to`, commit SHA requirement, or read-back verification |
| 17 | `artifact_dir override no ignore edit` | Artifact storage decoupling | Mutating root/global ignore files or treating repo-local override as default-safe |
| 18 | `generic executor handoff prompt` | Handoff decoupling | Returning only an artifact path without copy-paste execution instructions |
| 19 | `omo plan-mode handoff prompt` | Optional OMO compatibility | Making OMO mandatory or omitting copy-paste Prometheus prompt for OMO users |
| 20 | `cleanup current PR artifacts` | Cleanup workflow | Deleting without preview/confirmation or missing empty parent cleanup |
| 21 | `cleanup skips repo-local override` | Cleanup safety | Deleting repo-local artifacts that were created through explicit override |
| 22 | `cleanup-all default state root` | Cleanup-all workflow | Requiring per-repo cleanup or touching non-default artifact paths |
| 23 | `cleanup-all dry-run` | Cleanup-all safety | Deleting files during a dry run |
| 24 | `cleanup-all older-than` | Cleanup-all retention | Deleting fresh artifacts when age filtering is requested |

---

### 8. single-worktree no prompt

**Description:** The repository has one linked worktree that matches the active PR branch. The agent must resolve it as `TARGET_WORKTREE_ROOT` and continue without asking the user to choose between identical options.

| Dimension | Expected Value |
|-----------|---------------|
| expected target worktree | The single current checkout is bound before PR verification. |
| expected reply posture | No reply behavior yet. This scenario only covers Step 0 selection. |
| expected overview-table | Not reached until after PR verification and comment collection. |
| expected dossier escalation | Not reached. Later local reads and git commands must remain bound to that checkout; artifacts default to local state unless `artifact_dir` is explicit. |

**Failure pattern guarded:** Asking for unnecessary confirmation in the common one-worktree path, or proceeding with an unset `TARGET_WORKTREE_ROOT`.

---

### 9. current linked worktree default binding

**Description:** The agent starts inside the linked worktree that owns the PR branch. It should bind the current checkout as `TARGET_WORKTREE_ROOT` and continue without asking for confirmation solely because other linked worktrees exist.

| Dimension | Expected Value |
|-----------|---------------|
| expected target worktree | Current linked worktree is bound as `TARGET_WORKTREE_ROOT`. |
| expected reply posture | No reply behavior yet. |
| expected overview-table | Uses files read from the bound worktree once collection starts. |
| expected dossier escalation | Any dossier uses the default local-state artifact path unless `artifact_dir` is explicit; local reads and git commands still use the bound worktree. |

**Failure pattern guarded:** Resolving the repo root from the agent launch directory instead of the current linked worktree.

---

### 10. explicit PR branch mismatch blocks collection

**Description:** The agent starts in `/prj1` on `main` but the operator explicitly asks for a PR whose `headRefName` is `feat/dev`, which is checked out in `/prj1-feat-dev`. The agent must detect the mismatch and stop before comment collection until the operator reruns from the matching worktree or explicitly confirms using the current checkout.

| Dimension | Expected Value |
|-----------|---------------|
| expected target worktree | Current checkout remains bound, but collection is blocked until the branch/PR mismatch is resolved. |
| expected reply posture | No reply behavior yet. |
| expected overview-table | Not produced while branch/PR identity is unresolved. |
| expected dossier escalation | Blocked while branch/PR identity is unresolved. |

**Failure pattern guarded:** Pulling review comments for one branch while reading files or writing dossier artifacts from another checkout.

---

### 11. default local-state artifact path

**Description:** After checkout binding, dossier and Direct Fix Brief output must default to user-local state outside the repository, not to `.omo`, `.agent`, the agent launch directory, or another checkout.

| Dimension | Expected Value |
|-----------|---------------|
| expected target worktree | `TARGET_WORKTREE_ROOT` still governs local code reads and git commands, but disposable artifacts default outside the repo. |
| expected reply posture | Reply tasks are recorded in the dossier when Section A or Section B exists. |
| expected overview-table | Confirmed items map into dossier sections normally. |
| expected dossier escalation | Yes when Section A exists. Section B-only work uses the direct reply-only posting route, not a separate handoff branch. Artifact path defaults to `~/.local/state/ai-toolkits/pr-comments/<owner>__<repo>/pr-<N>/`. |

**Failure pattern guarded:** Writing disposable artifacts into repo-managed paths by default, modifying ignore files, or treating `.omo` as mandatory.

---

### 12. generated-plan reply tasks for Section A/B

**Description:** A dossier contains both Section A code-change items and Section B reply-only items. The generated plan must include reply task entries for both sections.

| Dimension | Expected Value |
|-----------|---------------|
| expected classification | Section A items remain code change plus reply. Section B items remain reply task only. |
| expected reply posture | Every actionable or reply-only comment has an explicit reply task in the generated plan. |
| expected overview-table | Section A and Section B are visible before dossier handoff. |
| expected dossier escalation | Yes. The generated plan must not drop Section B because it has no code changes. |

**Failure pattern guarded:** Treating generated plan output as implementation-only work and losing reply tasks.

---

### 13. reply-only posting and read-back

**Description:** The confirmed review result has Section B items and no Section A items. The runtime path should send replies directly and read back the posted replies instead of producing a code-work plan.

| Dimension | Expected Value |
|-----------|---------------|
| expected classification | All actionable follow-up items are Section B reply-only, such as `already_fixed`, `invalid`, or `needs_clarification`. |
| expected reply posture | Directly send replies, then read back posted replies to verify. |
| expected overview-table | Section B entries stay visible in the confirmation table. |
| expected dossier escalation | No code plan. Dossier or evidence may record the reply-only result, but ownership stays with the reply-only route. |

**Failure pattern guarded:** Generating an unnecessary plan for reply-only work, or claiming replies were posted without read-back evidence.

**QA wording:** This scenario intentionally includes `reply-only`, `send replies`, `post replies`, and read-back for search-based regression checks.

---

### 14. direct-fix fast path

**Description:** A confirmed Section A item is a simple, low-risk change: one code-change task, one file, no conflicts, no dependencies, no cross-file pattern, exact edit known, and reply target complete. The agent may skip Prometheus only after explicit user confirmation and a successful dossier accuracy grill gate.

**Origin:** PR #2166 (`peatio/hub`). Copilot asked to rename `HasInvestCompletedResponse.exists` to `has_invest_completed` in `protos/peatio/coffer/v1/welfare/eligibility/eligibility.proto`, preserving field number `1` and not manually editing generated `.pb.go` files.

| Dimension | Expected Value |
|-----------|---------------|
| expected classification | `valid` Section A. The issue is a concrete field-name clarity fix. |
| expected reply posture | Code change, targeted validation, commit, inline reply with commit SHA, and read-back verification. |
| expected overview-table | One Section A item, no conflicts, no duplicates, no 🔴 discussion items. |
| expected dossier escalation | Optional direct-fix fast path. If the user chooses direct fix, generate a Direct Fix Brief instead of the full Prometheus dossier. If the user does not choose direct fix, use the normal dossier/Prometheus path. |

**Failure pattern guarded:** Treating every Section A item as requiring a full Prometheus plan even when the task is mechanically clear, or treating direct-fix as code-only work and dropping reply/read-back requirements.

---

### 15. dossier accuracy grill gate

**Description:** Before writing a dossier or Direct Fix Brief, the agent checks whether unresolved ambiguity remains. It uses grill-me-style questioning only for uncertainty: one question at a time, each with a recommended answer, and only when code/comment context cannot answer the question. It does not invoke `grill-with-docs` by default.

| Dimension | Expected Value |
|-----------|---------------|
| expected classification | Existing classification stays unchanged unless the grill gate reveals new evidence requiring reclassification. |
| expected reply posture | Reply posture is confirmed before writing the final artifact if reply wording, target, or commit-SHA wording could mislead. |
| expected overview-table | Any conclusion, scope, dependency, or conflict change from the grill gate must be reflected in the final overview before artifact writing. |
| expected dossier escalation | If the grill gate exposes ambiguity, conflict, cross-file scope, architectural choice, or unclear test strategy, use the normal dossier/Prometheus path. If no ambiguity remains and direct-fix criteria pass, Direct Fix Brief is allowed. |

**Failure pattern guarded:** Generating an apparently precise dossier while `What to change`, test strategy, scope guardrails, or reply behavior still require a decision.

---

### 16. direct fix brief retaining PR reply fields

**Description:** A Direct Fix Brief is shorter than a dossier but must preserve every field needed for implementation and PR reply completion.

| Dimension | Expected Value |
|-----------|---------------|
| expected classification | Only confirmed Section A items eligible for direct-fix are represented in the brief. |
| expected reply posture | The brief includes comment author, comment ID, reply kind, endpoint, inline target fields (`path`, `line`, `side`, `in_reply_to`), Pre-Reply Gate, commit SHA requirement, and read-back verification. |
| expected overview-table | The final overview must explain that the item is routed to Direct Fix Brief rather than full dossier only after explicit user choice. |
| expected dossier escalation | No full dossier is generated for the direct-fix item, but the brief is blocked if required reply fields are missing. |

**Failure pattern guarded:** Producing a concise brief that lets the worker modify code but lacks enough information to reply to the PR comment safely.

---

### 17. artifact_dir override no ignore edit

**Description:** The operator provides `artifact_dir=<path>`, possibly inside the repository. The skill must use the explicit path but must not edit root `.gitignore`, `.git/info/exclude`, or global gitignore.

| Dimension | Expected Value |
|-----------|---------------|
| expected classification | Classification is unaffected by artifact location. |
| expected reply posture | Reply obligations remain intact. |
| expected overview-table | Final table is unchanged. |
| expected dossier escalation | Artifact is written to the override path. If the path is repo-local and not ignored, the skill warns it may appear in `git status` and continues only if the user accepts. |

**Failure pattern guarded:** Mutating ignore files to hide local artifacts, or silently assuming `.agent` / `.omo` are disposable.

---

### 18. generic executor handoff prompt

**Description:** After saving a dossier or Direct Fix Brief, the skill must print a copy-paste-ready generic executor prompt in addition to the artifact path.

| Dimension | Expected Value |
|-----------|---------------|
| expected classification | Confirmed conclusions are preserved in the artifact. |
| expected reply posture | Prompt requires code change, verification, optional commit, PR replies, and read-back verification. |
| expected overview-table | Final routing is visible before handoff. |
| expected dossier escalation | Handoff includes a fenced prompt that tells an executor to read the artifact and follow the execution contract. |

**Failure pattern guarded:** Returning only `Dossier saved to ...`, leaving the user to invent execution instructions.

---

### 19. omo plan-mode handoff prompt

**Description:** OMO remains optional. If the user wants OMO/Prometheus, the handoff includes a copy-paste plan-mode prompt that preserves reply tasks and read-back checks.

| Dimension | Expected Value |
|-----------|---------------|
| expected classification | Classification is unchanged. |
| expected reply posture | Prompt explicitly preserves Section A and Section B reply tasks, commit SHA requirement, and read-back verification. |
| expected overview-table | Final routing identifies the artifact path. |
| expected dossier escalation | OMO prompt is offered as compatibility text, not as the only path or default storage location. |

**Failure pattern guarded:** Coupling the skill to Prometheus, or generating an OMO plan prompt that drops PR reply duties.

---

### 20. cleanup current PR artifacts

**Description:** `/address-pr-comments-review cleanup` removes the default artifact directory for one PR after preview and confirmation.

| Dimension | Expected Value |
|-----------|---------------|
| expected classification | Not applicable. Cleanup routes before comment classification. |
| expected reply posture | Not applicable. Cleanup must not post replies. |
| expected overview-table | Not produced. Cleanup is a maintenance route, not review classification. |
| expected dossier escalation | Lists files under `~/.local/state/ai-toolkits/pr-comments/<owner>__<repo>/pr-<N>/`, asks for confirmation, deletes that PR directory, then removes the repo directory only if empty. |

**Failure pattern guarded:** Running full review flow for cleanup, deleting without confirmation, or requiring users to manually locate each generated file.

---

### 21. cleanup skips repo-local override

**Description:** A previous run wrote artifacts to a repo-local `artifact_dir`. Default cleanup must not delete those files unless the user explicitly passes `--artifact-dir <path>` and confirms.

| Dimension | Expected Value |
|-----------|---------------|
| expected classification | Not applicable. |
| expected reply posture | Not applicable. |
| expected overview-table | Not produced. |
| expected dossier escalation | Default cleanup only targets the local-state PR directory. Repo-local paths such as `.omo/notepads/...`, `.agent/...`, or custom `artifact_dir` are skipped unless explicitly named. |

**Failure pattern guarded:** Cleanup deleting user-managed repo files that may be intended for commit or handoff.

---

### 22. cleanup-all default state root

**Description:** `/address-pr-comments-review cleanup-all` removes all default local-state PR comment artifacts after preview and confirmation.

| Dimension | Expected Value |
|-----------|---------------|
| expected classification | Not applicable. Cleanup-all routes before comment classification. |
| expected reply posture | Not applicable. Cleanup-all must not post replies. |
| expected overview-table | Not produced. |
| expected dossier escalation | Scans `~/.local/state/ai-toolkits/pr-comments/`, groups by `<owner>__<repo>/pr-<N>/`, shows repo count, PR count, file count, total size, asks for confirmation, then deletes only default-state artifacts. |

**Failure pattern guarded:** Forcing one-repo-at-a-time cleanup or deleting repo-local override artifacts.

---

### 23. cleanup-all dry-run

**Description:** `/address-pr-comments-review cleanup-all --dry-run` previews cleanup-all without deleting anything.

| Dimension | Expected Value |
|-----------|---------------|
| expected classification | Not applicable. |
| expected reply posture | Not applicable. |
| expected overview-table | Not produced. |
| expected dossier escalation | Prints the same grouped preview and totals as cleanup-all, then stops with no deletion. |

**Failure pattern guarded:** Treating dry-run as a normal cleanup after preview.

---

### 24. cleanup-all older-than

**Description:** `/address-pr-comments-review cleanup-all --older-than 7d` only removes default-state artifacts older than the specified age.

| Dimension | Expected Value |
|-----------|---------------|
| expected classification | Not applicable. |
| expected reply posture | Not applicable. |
| expected overview-table | Not produced. |
| expected dossier escalation | Preview and deletion set include only PR artifact directories older than the age threshold. Fresh artifacts are listed as skipped or omitted from deletion. |

**Failure pattern guarded:** Deleting fresh artifacts during age-filtered cleanup.

## QA Check Tokens

The following tokens MUST appear in this file for automated QA:

- `thread_outdated unresolved`
- `thread_outdated + thread_resolved`
- `minimized comment`
- `zero-actionable`
- `partial fix`
- `duplicate reply`
- `cross-file`
- `single-worktree no prompt`
- `current linked worktree default binding`
- `explicit PR branch mismatch blocks collection`
- `default local-state artifact path`
- `generated-plan reply tasks for Section A/B`
- `reply-only posting and read-back`
- `direct-fix fast path`
- `dossier accuracy grill gate`
- `direct fix brief retaining PR reply fields`
- `artifact_dir override no ignore edit`
- `generic executor handoff prompt`
- `omo plan-mode handoff prompt`
- `cleanup current PR artifacts`
- `cleanup skips repo-local override`
- `cleanup-all default state root`
- `cleanup-all dry-run`
- `cleanup-all older-than`
- `expected classification`
- `expected reply posture`
- `expected overview-table`
- `expected dossier escalation`
- `TARGET_WORKTREE_ROOT`
- `generated plan`
- `reply task`
- `reply-only`
- `Direct Fix Brief`
- `grill-me`
- `grill-with-docs`
- `OMO optional`
- `reply fields`
- `~/.local/state/ai-toolkits/pr-comments`
- `artifact_dir`
- `cleanup-all`
- `--dry-run`
- `--older-than`
