# Eval Matrix: address-pr-comments-review

> **Behavioral acceptance criteria** for the address-pr-comments-review skill.
> Each scenario defines behavior a maintainer can regression review. Review dimensions stay close to the runtime phase being protected: current checkout binding, classification, canonical route fields, reply posture, overview-table treatment, dossier escalation, exclusive handoff shape, or route-specific post reply read-back.
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

**Description:** Multiple reviewers (e.g., a human and CodeRabbit/Copilot) flag the same or substantially overlapping concern on the same code. The agent must detect this as a duplicate, merge the entries, and produce ONE code change task with a separate canonical reply target for EACH source author.

**Origin:** PR #1215 patterns. Multiple reviewers independently flagged the publisher shutdown ordering issue. Risk of replying twice with the same information or applying the fix twice in parallel.

| Dimension | Expected Value |
|-----------|---------------|
| expected classification | Cross-reference check detects duplicate. Merged into one entry with all authors noted. If the common concern is valid, conclusion is `valid`. |
| expected reply posture | One code change. Then post one reply per source author using that target's `source_comment_id`, `root_comment_id`, `comment_kind`, `reply_mode`, `endpoint`, and `read_back_endpoint`. Inline duplicates in one thread share the root `/replies` endpoint; each target gets its own route-specific read-back. |
| expected overview-table | Merged single entry with multiple authors listed (e.g., `@copilot, @alice`). Conclusion `valid`. Note: `≡ merged (N reviews)`. |
| expected dossier escalation | Yes — Section A (one code change task). Dossier must list every duplicate source author and all six canonical route fields for each reply target. Dedup count stays in Executive Summary. |

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
| 14 | `direct-fix-pr1431 implementation-plus-verification companion` | PR #1431, implementation plus corresponding spec and focused test | Splitting one concern across tasks, using one-file eligibility, or bypassing informed confirmation and reply/read-back duties |
| 15 | `dossier accuracy grill gate` | Simple-path and ambiguous-dossier regression | Writing a dossier or brief while unresolved implementation, scope, test, or reply ambiguity remains |
| 16 | `direct fix brief retaining PR reply fields` | Direct-fix handoff regression | Losing source/root route fields, endpoint, full commit SHA body requirement, or read-back verification |
| 17 | `artifact_dir override no ignore edit` | Artifact storage decoupling | Mutating root/global ignore files or treating repo-local override as default-safe |
| 18 | `Review Dossier plan-first exclusive handoff` | Review Dossier handoff routing | Emitting a Direct Fix prompt, a second handoff, or allowing edits before explicit approval |
| 19 | `exclusive Dossier and Direct Fix handoff` | Exclusive handoff routing | Using a direct prompt for a Dossier, a plan-first prompt for Direct Fix, or requiring a second plan approval |
| 20 | `cleanup current PR artifacts` | Cleanup workflow | Deleting without preview/confirmation or missing empty parent cleanup |
| 21 | `cleanup skips repo-local override` | Cleanup safety | Deleting repo-local artifacts that were created through explicit override |
| 22 | `cleanup-all default state root` | Cleanup-all workflow | Requiring per-repo cleanup or touching non-default artifact paths |
| 23 | `cleanup-all dry-run` | Cleanup-all safety | Deleting files during a dry run |
| 24 | `cleanup-all older-than` | Cleanup-all retention | Deleting fresh artifacts when age filtering is requested |
| 31 | `direct-fix-mixed-topology` | Direct Fix topology boundary | Rejecting legal mixed singleton plus one-chain batches, hiding topology, or executing them in parallel |
| 32 | `direct-fix-invalid-complexity` | Direct Fix complexity boundary | Accepting hard blockers, invalid certificates, or unclear verification in Direct Fix |
| 33 | `direct-fix-invalid-topology` | Direct Fix topology failure cases | Accepting over-cap, nonlinear, duplicate, external, or shared-symbol graphs |

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

**Description:** The confirmed review result has Section B items and no Section A items. The runtime path should select each route from canonical source/root/kind/mode fields, send a body-only reply through its exact endpoint, and read back the posted reply through its route-specific endpoint instead of producing a code-work plan.

| Dimension | Expected Value |
|-----------|---------------|
| expected classification | All actionable follow-up items are Section B reply-only, such as `already_fixed`, `invalid`, or `needs_clarification`. |
| expected reply posture | Directly send body-only replies, then verify each with route-specific read-back. A timeout or malformed response is uncertain, not success; read back before deciding whether any POST remains. |
| expected overview-table | Section B entries stay visible in the confirmation table. |
| expected dossier escalation | No code plan. Dossier or evidence may record the reply-only result, but ownership stays with the reply-only route. |

**Failure pattern guarded:** Generating an unnecessary plan for reply-only work, or claiming replies were posted without read-back evidence.

**QA wording:** This scenario intentionally includes `reply-only`, `send replies`, `post replies`, and read-back for search-based regression checks.

---

### 14. direct-fix-pr1431 implementation-plus-verification companion

**Description:** PR #1431 contains one root concern with one local behavioral outcome: a controller implementation path, its directly corresponding spec path, and one exact focused test. The implementation and verification paths belong to one `local-behavior` task, not separate tasks. The task has a complete typed complexity certificate, exact change, canonical reply fields, and no hard blockers. The agent may select Direct Fix only after the final table discloses the route and consequences, then receives valid informed confirmation.

**Origin:** PR #1431. The implementation path and corresponding spec path are direct companions for one behavior, with a focused test as verification. This replaces the old one-file shortcut and guards against splitting one concern into multiple Direct Fix tasks.

| Dimension | Expected Value |
|-----------|---------------|
| expected classification | `valid` Section A. One `local-behavior` task owns one root concern, one behavioral outcome, and one implementation locus. |
| expected reply posture | Code change, focused implementation-plus-spec/test validation, commit, body-only reply through the target's exact endpoint, full task-specific 40-character commit SHA in fixed or partially addressed body text, and route-specific read-back verification. |
| expected overview-table | One Section A task, batch shape `1/5`, ordered chains `0/1`, maximum chain length none, complexity `local-behavior`, implementation and verification paths disclosed, serial execution and fallback reason inventory disclosed, no conflicts or duplicates, and no 🔴 discussion items. |
| expected dossier escalation | Direct Fix Brief is allowed only after informed final-table confirmation. With no prior Direct Fix preference, generic `proceed` confirms classification only and does not authorize Direct Fix. A valid explicit Direct Fix selection after disclosure is sufficient; a declined or ambiguous route uses the normal Review Dossier path. |

**Failure pattern guarded:** Splitting implementation and direct verification companions into separate tasks, treating one file as the eligibility rule, or treating Direct Fix as code-only work and dropping informed confirmation or reply/read-back requirements.

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

**Description:** A Direct Fix Brief is shorter than a dossier but must preserve every field needed for implementation and PR reply completion. It must preserve source/root/kind/mode/endpoint/read-back routing, not diff coordinates or nested-reply metadata.

| Dimension | Expected Value |
|-----------|---------------|
| expected classification | Only confirmed Section A items eligible for direct-fix are represented in the brief. |
| expected reply posture | The brief includes source author, `source_comment_id`, nullable `root_comment_id`, `comment_kind`, `reply_mode`, `endpoint`, `read_back_endpoint`, Reply kind, Pre-Reply Gate, full commit SHA body requirement for fixed or partially addressed conclusions, and read-back verification. Threaded POST payload is exactly `{body}` and rejects `commit_id`, `path`, `line`, `side`, and `in_reply_to`. |
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

### 18. Review Dossier plan-first exclusive handoff

**Description:** After saving a Review Dossier, the current user-visible final response must contain exactly one plan-first handoff block. The executor must stop and wait for explicit user approval before editing. Persisted artifact completeness and response completion are separate checks.

| Dimension | Expected Value |
|-----------|---------------|
| expected classification | Confirmed conclusions are preserved in the artifact. |
| expected reply posture | The plan-first Dossier handoff preserves code change, verification, commit, PR replies, and read-back requirements. |
| expected overview-table | Final routing is visible before handoff. |
| expected dossier escalation | Review Dossier response includes actual artifact path, exactly one plan-first prompt that waits for explicit approval before editing, and cleanup target. |

**Failure pattern guarded:** Artifact file is complete but the current user-visible final response returns only `Dossier saved to ...`, emits a Direct Fix or second prompt, or allows editing before explicit approval.

---

### 19. exclusive Dossier and Direct Fix handoff

**Description:** Handoff mode is determined by artifact type. Review Dossier emits one plan-first prompt and waits for explicit approval before editing. Direct Fix Brief emits one direct execution prompt after explicit Direct Fix selection and does not add a second plan-approval prompt.

| Dimension | Expected Value |
|-----------|---------------|
| expected classification | Classification is unchanged. |
| expected reply posture | Both exclusive prompts preserve Section A and Section B reply tasks, commit SHA requirements, and read-back verification. Direct Fix additionally preserves the bounded `N/5` summary, per-task commit, and serial fail-stop policy. |
| expected overview-table | Final routing identifies the artifact path. |
| expected dossier escalation | Review Dossier remains plan-first. Direct Fix remains direct execution after explicit selection. Neither artifact emits the other artifact's handoff or requires a second plan approval. |

**Failure pattern guarded:** Coupling handoff behavior to a runtime, emitting dual prompts, or generating a handoff that drops PR reply duties.

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

### 25. inline root 101 threaded_inline

**Description:** An inline root comment with `source_comment_id=101` and `root_comment_id=101` must use the threaded inline route.

| Dimension | Expected Value |
|-----------|---------------|
| expected classification | `valid` Section A or a confirmed Section B reply-only item, according to existing classification evidence. |
| expected reply posture | `reply_mode=threaded_inline`; POST to `repos/{owner}/{repo}/pulls/{pr}/comments/101/replies`; payload key set exactly `{body}`; read back PR review comments and match actor, full body, target PR, and `in_reply_to_id=101`. |
| expected overview-table | Preserves source 101, root 101, kind `inline`, mode `threaded_inline`, POST endpoint, and read-back endpoint. |
| expected dossier escalation | Follows Section A/B classification. Missing route fields block before POST. |

**Failure pattern guarded:** Posting a generic inline comment, using a child target, or including commit or diff metadata in the threaded request.

---

### 26. inline child 202 sibling_inline

**Description:** An inline child comment with `source_comment_id=202` and `root_comment_id=101` must create a sibling under root 101, never a nested reply under child 202.

| Dimension | Expected Value |
|-----------|---------------|
| expected classification | Existing classification is unchanged. |
| expected reply posture | `reply_mode=sibling_inline`; POST to `repos/{owner}/{repo}/pulls/{pr}/comments/101/replies`, not `/comments/202/replies`; payload key set exactly `{body}`; read back against root 101. |
| expected overview-table | Preserves source 202, root 101, kind `inline`, mode `sibling_inline`, POST endpoint, and read-back endpoint. |
| expected dossier escalation | Follows the selected Section A/B route. Unknown or missing root blocks before POST. |

**Failure pattern guarded:** Targeting child ID 202 or inventing a fourth classification kind.

---

### 27. review-level 303 timeline

**Description:** A review-level comment with source 303 and no diff thread must receive a PR issue timeline comment.

| Dimension | Expected Value |
|-----------|---------------|
| expected classification | Existing classification is unchanged. |
| expected reply posture | `comment_kind=review`, `root_comment_id=null`, `reply_mode=timeline`; POST and read back through `repos/{owner}/{repo}/issues/{pr}/comments`; payload key set exactly `{body}`. |
| expected overview-table | Shows source 303, kind `review`, mode `timeline`, issue-comment endpoint, and matching read-back endpoint. |
| expected dossier escalation | Follows the selected Section A/B route; no inline root is fabricated. |

---

### 28. top-level 404 timeline

**Description:** A top-level PR timeline comment with source 404 must receive a PR issue timeline comment.

| Dimension | Expected Value |
|-----------|---------------|
| expected classification | Existing classification is unchanged. |
| expected reply posture | `comment_kind=top_level`, `root_comment_id=null`, `reply_mode=timeline`; POST and read back through `repos/{owner}/{repo}/issues/{pr}/comments`; payload key set exactly `{body}`. |
| expected overview-table | Shows source 404, kind `top_level`, mode `timeline`, issue-comment endpoint, and matching read-back endpoint. |
| expected dossier escalation | Follows the selected Section A/B route; no diff coordinates are required. |

---

### 29. threaded body-only payload

**Description:** Every threaded inline POST must reject `commit_id`, `path`, `line`, `side`, and `in_reply_to`. Fixed and partially addressed reply bodies still include the full task-specific 40-character commit SHA after commit and remote reachability checks.

| Dimension | Expected Value |
|-----------|---------------|
| expected classification | Existing conclusion remains unchanged. |
| expected reply posture | Request body is exactly `{body}`. Forbidden fields block the request. Full SHA appears in rendered fixed or partially addressed body text, not request metadata. |
| expected overview-table | Retains canonical route fields and commit-SHA requirement. |
| expected dossier escalation | Section A keeps commit, remote reachability, reply, and read-back order. Section B has no code-change fields but keeps reply and read-back gates. |

**Failure pattern guarded:** Treating diff coordinates or commit metadata as valid threaded request fields.

---

### 30. read-back uncertainty no retry

**Description:** A timeout or malformed POST response is uncertain. Read back current remote state first. One exact match verifies the reply; zero exact matches become blocked absent; multiple exact matches become blocked ambiguous. None authorizes a second POST.

| Dimension | Expected Value |
|-----------|---------------|
| expected classification | Existing classification is unchanged. |
| expected reply posture | Route-specific GET/LIST read-back checks actor, full body, target PR, and root relationship for inline, or actor, full body, and target PR for timeline. |
| expected overview-table | Records uncertain, reconciled, blocked absent, or blocked ambiguous outcome with read-back evidence. |
| expected dossier escalation | Resume and repeated interruption remain blocked until evidence is unambiguous. The workflow preserves at most one POST attempt. |

**Failure pattern guarded:** Blind retry, treating zero or multiple matches as success, or skipping read-back after timeout or malformed output.

---

### 31. direct-fix-mixed-topology

**Description:** A Direct Fix batch contains legal mixed topology: three independent singleton tasks plus one ordered chain `task-4 -> task-5`. A boundary variant contains two singleton tasks plus one ordered chain `task-3 -> task-4 -> task-5`. Every task is `mechanical` or `local-behavior`, each has one root concern, one behavioral outcome, and one implementation locus, implementation and direct verification companions share a task, every typed complexity certificate passes, and no hard blocker remains.

| Dimension | Expected Value |
|-----------|---------------|
| expected classification | All Section A tasks are eligible after individual complexity, certificate, identity, and topology checks. |
| expected reply posture | Each task keeps its own distinct commit SHA, canonical reply target, full fixed or partially addressed SHA requirement, and route-specific read-back. |
| expected overview-table | The table discloses total `5/5`, ordered-chain count `1/1`, chain length `2/3`, dependency-first order, serial execution, complexity classes, implementation/verification paths, and fallback reason inventory. |
| expected dossier escalation | Direct Fix is allowed only after valid informed final-table confirmation. Generic `proceed` without a pending restated preference confirms classification only. |

**Failure pattern guarded:** Rejecting legal mixed batches because they are not all independent, executing an ordered chain in parallel, exceeding the one-chain or three-node limit, or hiding topology and execution consequences before confirmation.

---

### 32. direct-fix-invalid-complexity

**Description:** A Section A task has a closed-list hard blocker such as `architecture`, `cross-module-state`, `public-interface`, `authorization`, `schema-or-data`, `dependency-introduction`, `concurrency`, `transaction`, or `retry-or-recovery`; alternatively its complexity class or typed certificate is missing, invalid, duplicated, reordered, malformed, or has empty evidence. Verification may also be unclear.

| Dimension | Expected Value |
|-----------|---------------|
| expected classification | Section A remains actionable, but Direct Fix eligibility fails closed and every failed eligibility condition is named. |
| expected reply posture | No Direct Fix edit, commit, push, reply POST, or read-back side effect occurs. The eventual Review Dossier preserves required reply work. |
| expected overview-table | The table records the rejected Direct Fix route, complexity class, hard-blocker or certificate evidence, verification failure, and fallback reason inventory. |
| expected dossier escalation | Route to Review Dossier. A generic `proceed` confirms classification only, regardless of any stale Direct Fix preference. |

**Failure pattern guarded:** Treating a file count, familiar file type, or generic low-risk label as sufficient, accepting an incomplete or untyped certificate, or allowing a hard-blocked task into Direct Fix.

---

### 33. direct-fix-invalid-topology

**Description:** A proposed batch violates Direct Fix topology through six Section A tasks, a four-node chain, two ordered chains, a branch, a merge, a cycle, duplicate task IDs or edges, a self-edge, an external dependency target, a Section B dependency, or a shared production symbol/hunk. The batch may otherwise contain mechanically clear tasks.

| Dimension | Expected Value |
|-----------|---------------|
| expected classification | Direct Fix eligibility fails closed, and every failed topology or identity condition is named. |
| expected reply posture | No Direct Fix edit, commit, push, reply POST, or read-back side effect occurs. Review Dossier remains available for valid ordered work. |
| expected overview-table | The table discloses the actual task graph, failed cap or graph condition, deterministic-order impact, and fallback route before any execution confirmation. |
| expected dossier escalation | Route to Review Dossier. Any prior Direct Fix confirmation is invalidated by a topology update and cannot authorize the changed batch. |

**Failure pattern guarded:** Treating a nonlinear graph as one chain, silently dropping dependencies, accepting a second chain, extending a chain beyond three nodes, or executing before topology preflight.

---

### 34. direct-fix route prompt progression

**Description:** The transcript must show the complete user-visible progression from Step 3 classification confirmation through final route disclosure and route selection. The scenario covers generic `proceed`, prior Direct Fix preference state, explicit route choices, and a single otherwise eligible `local-behavior` task whose only Direct Fix blocker is `authorization`. Static checks may confirm wording and table structure, but they do not prove this behavior. Transcript evaluation is mandatory.

**Origin:** Route Confirmation Contract and Consent State Matrix in `skills/address-pr-comments-review/references/interaction.md`, including the distinction between classification confirmation, route authorization, and Direct Fix eligibility failure.

| Dimension | Expected Value |
|-----------|---------------|
| expected classification | Step 3 classification is confirmed before route selection. The transcript must preserve the distinction between no route authorization and a failed Direct Fix eligibility condition. |
| expected reply posture | No edit, commit, push, reply POST, or read-back is authorized by Step 3 `proceed` or by a generic affirmative without a pending restated Direct Fix preference. Explicit Direct Fix authorizes only the disclosed eligible batch; explicit Review Dossier authorizes no Direct Fix side effect. |
| expected overview-table | Final disclosure is user-visible and includes the selected or recommended route, batch shape, complexity, implementation and verification paths, serial execution, plan-approval consequence, and fallback reason inventory. |
| expected dossier escalation | An eligible single `local-behavior` task with only the `authorization` blocker recommends Review Dossier and records fallback reason inventory exactly `authorization`; it must not invent a second failed condition. |

#### Transcript Evidence Table

| # | Input or state | Matrix / routing source | Expected user-visible outcome |
|---|----------------|-------------------------|-------------------------------|
| 1 | Step 3 response: `proceed` | Stage 3: Classification-Only Confirmation | Confirms classifications and silent consent only. Agent runs eligibility preflight, then shows final table and route disclosure. No route is promised and no side effect is authorized. |
| 2 | Final disclosure, no prior preference, generic affirmative | Consent State Matrix: `none` + `disclosed` + `generic-affirmative` -> `classification-only`; Stage 4 route contract | Remains `classification-only` with no selected route and `Fallback reason inventory: none`; asks user to explicitly choose `Direct Fix` or `Review Dossier`. This is no route authorization, not an eligibility failure. |
| 3 | Prior Direct Fix preference, final disclosure restated, generic affirmative | Consent State Matrix: `pending-direct-fix` + `disclosed-and-restated` + `generic-affirmative` -> `direct-fix-once` | Reconfirms the disclosed batch and authorizes Direct Fix once, without requiring a second `Direct Fix` keyword. |
| 4 | Final disclosure, explicit `Direct Fix` | Consent State Matrix: `any` + `disclosed` + `explicit-direct-fix` -> `direct-fix-once`; Post-Confirmation Routing eligible-batch row | Selects Direct Fix for the disclosed batch, then permits pre-write scan, grill gate, Direct Fix Brief, and serial execution without a second plan approval. |
| 5 | Final disclosure, explicit `Review Dossier` | Stage 4: Disclosure and Route Selection: `any` + `disclosed` + `explicit-review-dossier` -> Select Review Dossier; Post-Confirmation Routing default/failure row | Selects Review Dossier and grants no Direct Fix authority. The plan-first dossier handoff remains the route, even if the batch is otherwise eligible. |
| 6 | Single `local-behavior` task passes all checks except hard blocker `authorization` | Direct Fix invalid-complexity boundary plus Post-Confirmation Routing direct-fix-criteria-fail row | Recommends Review Dossier. Fallback reason inventory is exactly `authorization`, with no second invented failure. Transcript must show no Direct Fix side effect. |

**Failure pattern guarded:** Treating Step 3 `proceed` as route authorization, treating generic final consent as Direct Fix authorization without a pending restated preference, collapsing explicit Review Dossier into Direct Fix, or disguising an authorization eligibility failure as missing route consent. Static source checks are insufficient; the evaluator must inspect a transcript containing all six rows and their resulting user-visible route/state.

---

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
- `direct-fix-pr1431 implementation-plus-verification companion`
- `direct-fix-mixed-topology`
- `direct-fix-invalid-complexity`
- `direct-fix-invalid-topology`
- `direct-fix route prompt progression`
- `dossier accuracy grill gate`
- `direct fix brief retaining PR reply fields`
- `inline root 101 threaded_inline`
- `inline child 202 sibling_inline`
- `review-level 303 timeline`
- `top-level 404 timeline`
- `threaded body-only payload`
- `read-back uncertainty no retry`
- `malformed_input`
- `cancel_resume`
- `repeated_interruption`
- `artifact_dir override no ignore edit`
- `Review Dossier plan-first exclusive handoff`
- `exclusive Dossier and Direct Fix handoff`
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
- `exclusive handoff`
- `reply fields`
- `~/.local/state/ai-toolkits/pr-comments`
- `artifact_dir`
- `cleanup-all`
- `--dry-run`
- `--older-than`
