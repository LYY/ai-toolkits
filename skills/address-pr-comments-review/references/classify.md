# Comment Classification Protocol

Step 2a individual comment classification. Determine source, intent, and conclusion for each comment. Cross-reference (duplicate/conflict/relation detection) happens in Step 2b — see `cross-reference.md`.

## Source Detection

Every comment must be classified as either `@human` or `@bot` based on its author.

### @bot Indicators

A comment is `@bot` if ANY of these match:

- Author login matches known bot patterns: `coderabbit`, `coderabbitai[bot]`, `github-actions[bot]`, `copilot`, `dependabot[bot]`, `renovate[bot]`, `semantic-release-bot`, `codecov[bot]`, `lgtm-com[bot]`, `sonarcloud[bot]`, `snyk-bot`
- Author login ends with `[bot]` (GitHub's standard bot suffix)
- Author `type` is `Bot` in the JSON output from `list_comments.py`
- The comment body contains verified AI review signatures (CodeRabbit's structured prompt blocks, Copilot's numbered recommendation lists with AI disclaimers)

### @human Indicators

A comment is `@human` if ALL of these are true:

- Author login does NOT match any bot pattern
- Author `type` is `User` in the JSON output
- The comment body is free of AI-generated formatting signatures

### Multi-Author Threads

When a comment thread has multiple authors (e.g., a human replied to a bot), classify based on the AUTHOR OF THE ORIGINAL COMMENT. Subsequent replies are handled by the `has_replies` field and the cross-reference protocol, not by source detection.

### Ambiguous Source

If source is ambiguous (unrecognized login, no type field), default to `@human`. False-positive human is safer than false-positive bot. A wrongly classified bot comment gets skipped and may miss an actionable review item.

---

## Intent Assessment

Every comment must be assessed as `actionable` or `informational`. This determines whether it enters the conclusion pipeline or goes directly to Section C.

### actionable Indicators

A comment is `actionable` if it contains ANY of:

- A direct code suggestion with a specific change, refactor, rename, or extraction
- A question about logic, correctness, or behavior that requires a code change or explanation
- A reported bug, edge case, or performance concern
- A request for additional tests, documentation, or error handling
- A recommendation accompanied by a code block or diff
- A follow-up question to a previous reply that demands further action
- A stated requirement for change before approval (blocking review item)
- A concern phrased as a question that reveals a misunderstanding of the code -- if correcting the misunderstanding requires a code change, this is actionable

### informational Indicators

A comment is `informational` if it contains ONLY:

- Praise or acknowledgment ("LGTM", "Nice catch", "Great work", "Agreed")
- A simple question about rationale that does not demand a code change ("What was the reasoning behind this?")
- A non-blocking observation phrased as optional ("Consider...", "Maybe...", "Nit:")
- An emoji-only or single-word reply ("Done", "👍")
- A retraction or self-correction ("Never mind", "Ignore this, I misread")
- A mention or @-notification without substantive content

### Ambiguous Cases

When intent cannot be cleanly determined:

- Default to `actionable` unless clearly informational. Missed actionable items cause bugs. Missed informational items waste a reply.
- Comments with BOTH informational and actionable content are fully `actionable`. The actionable part must be addressed.
- A question that reveals the reviewer misunderstood the code is `informational` if the misunderstanding can be resolved with an explanation alone. It is `actionable` if the code is genuinely unclear and needs a comment or structural change.

---

## Conclusion Taxonomy

### valid

**When to apply:** The comment identifies a real issue that should be addressed in this PR. The concern is correct, applies to the current code at branch tip, and requires a code change.

**Evidence required:** None beyond reading the current code at the referenced `path:line` and confirming the issue is present. If the issue was already fixed, use `already_fixed`. If partially addressed, use `partially_addressed`.

**Action:** Code change + test + reply + commit. Maps to dossier Section A.

---

### invalid

**When to apply:** The comment does not apply to the current code. Common reasons: the reviewer misunderstood the code, the concern is based on a reading error, or the suggestion would break other behavior.

**Evidence required:** A brief reason must be stated. If the reason is "the code already handles this differently," that is `already_fixed`, not `invalid`. The distinction: `invalid` means the concern itself does not apply; `already_fixed` means the concern was valid but has been resolved.

**Action:** Reply only (explain why). Maps to dossier Section B.

---

### already_fixed

**When to apply:** The issue raised by the comment has already been resolved in the current branch tip code. The fix exists at the time of classification.

**Evidence required: STRONG evidence required.** You MUST read the current code at the comment's `path:line` and confirm the fix is in place. If you cannot find the fix in current code, this is NOT `already_fixed` -- reclassify as `valid`, `invalid`, or `partially_addressed`.

Acceptable evidence:

- Current code at `path:line` matches the reviewer's requested fix (cite specific lines)
- A subsequent commit visible in `git log --oneline` for the referenced file that explicitly addresses the concern (cite the commit hash and what it changed)

NOT acceptable evidence:

- `thread_outdated: true` -- the diff context shifted but the code may still have the same issue
- `thread_resolved: true` -- someone collapsed the thread, that does not mean the code was fixed
- A bot replied "Good catch, let's fix this" -- no code change was made
- A different file was fixed but the commented file was not

**Action:** Reply only (confirm already fixed). Maps to dossier Section B.

---

### already_replied

**When to apply:** The comment thread already has a human reply that substantively addresses the concern. No further action is needed from this pass.

**Evidence required:** Primary signal is `has_replies: true` from the JSON output. However, you must verify:

- The reply author is human (bot replies to bot comments do not count)
- The reply is not your own previous reply from an earlier pass
- The reply substantively addresses the comment ("I'll look into this" or "Good point" are NOT sufficient -- those should be `needs_clarification` or `valid`)

**Override:** The user can reclassify at Step 3 if they believe the existing reply is insufficient.

**Action:** No action (skip). Maps to dossier Section C.

---

### out_of_scope

**When to apply:** The comment raises a valid concern that is outside the scope of the current PR. Examples: suggests a feature unrelated to the PR's intent, flags pre-existing code unrelated to the diff, requests a refactor that belongs in a separate PR.

**Evidence required:** The concern must be genuinely valid (not `invalid`) but belong elsewhere. If the concern is both invalid AND out of scope, prefer `invalid`. The `out_of_scope` label implies the concern is real but should not be addressed in this PR.

**Action:** Reply only (explain why out of scope, optionally suggest a follow-up). Maps to dossier Section B.

---

### needs_clarification

**When to apply:** The comment raises a question or concern that cannot be classified without additional input from the reviewer or PR author. Examples: a question about intent, a suggestion that depends on unstated requirements, a concern about behavior you cannot reproduce.

**Evidence required:** The ambiguity must originate from the comment itself, not from your own confusion. If the comment is clear but you are confused, that is a different conclusion. You must be able to state the specific question that needs answering.

**Action:** Reply only (with resolved direction after clarification). Maps to dossier Section B. Marked with a 🔴 discussion flag.

---

### partially_addressed

**When to apply:** A code change was applied in response to the review comment, but the fix is incomplete, insufficient, or directionally wrong. The reviewer's core concern is not fully resolved despite a visible fix attempt.

This conclusion bridges `valid` (no fix attempted) and `already_fixed` (concern fully resolved). It acknowledges effort while requiring further work.

**Applicable conditions (ALL three must be met):**

1. There is evidence of a fix attempt -- a commit or code change that appears to respond to the reviewer's concern
2. The fix does NOT fully resolve the reviewer's core concern -- the issue or a meaningful part of it persists in the current code
3. The remaining issue is substantive, not cosmetic -- it requires genuine rework, not a touch-up

**When NOT to apply:**

- If no fix was attempted at all -> classify as `valid` directly (do not use `partially_addressed` as a softer `valid`)
- If the fix fully resolves the concern -> classify as `already_fixed`
- If the fix is cosmetic or minor AND the core concern IS resolved -> classify as `already_fixed` (mention the remaining minor issue in the reply text, not as a separate conclusion)
- If the concern genuinely cannot be fixed (constraint, dependency, external limitation) -> classify as `invalid` with an explanation

**Sub-types with examples:**

| Sub-type | Description | Example |
|----------|-------------|---------|
| Incomplete scope | Fix addressed one location but the same pattern exists elsewhere | Fixed `CloseAllPublishers()` ordering in `monitor.go` but not in 4 other `server/` files |
| Wrong direction | Fix exists but makes the problem worse | Added `CloseAllPublishers()` BEFORE `manager.StopAll()` when close should happen AFTER stop |
| Partial logic | Fix handles the happy path but misses edge cases | Added null check for one input parameter but not for related parameters |
| Insufficient margin | Fix reduces the risk but does not eliminate it | Reduced timeout from 30s to 10s but remaining 10s window still causes races |

**Evidence required (ALL three):**

1. Citation of the existing fix attempt: "Commit `<sha>` attempted to fix by changing `<X>` at `<file>:<line>`"
2. Citation of the remaining issue: "Current code at `<file>:<line>` still shows `<problem>`"
3. Explanation of insufficiency: "The fix addresses `<X>` but does not address `<Y>`. The reviewer asked for `<Z>`."

**Action:** Code change + reply. The reply must acknowledge the existing fix attempt, explain why it is insufficient, and describe the correct fix direction. Maps to dossier Section A.

---

## Edge Cases

### minimized

**Definition:** The comment's `minimized` field is `true`. The author hid the comment in the GitHub UI, typically because they retracted or replaced it.

**Classification:** `informational`. Do NOT read current code. Do NOT assign any actionable conclusion. The author explicitly withdrew the comment, and that decision must be respected.

**Distinction from thread_outdated:** `minimized` is an author action. The person who wrote the comment chose to hide it. `thread_outdated` is a GitHub platform action -- the diff context shifted, but the comment itself remains valid. These signals are fundamentally different and must NEVER be conflated. Treating `thread_outdated` as `informational` (by analogizing to `minimized`) is a known failure pattern that causes real bugs to be missed.

---

### thread_outdated

**Definition:** The comment's `thread_outdated` field is `true`. The PR diff has changed since the comment was posted, and GitHub can no longer highlight the exact context inline. The comment still exists and represents a valid review concern. Only the UI context shifted.

**Classification rule: `thread_outdated` is NOT a classification. It is a signal that triggers a mandatory code verification step BEFORE any conclusion can be assigned.**

Follow this three-step process:

1. **Read** the current code at the comment's `path:line` on the branch tip
2. **Compare** the current code against the reviewer's concern
3. **Classify** based on what you find:
   - Issue still exists in current code -> `valid`
   - Issue was fixed in current code -> `already_fixed` (requires evidence of the fix, not just the outdated flag)
   - Issue was partially addressed -> `partially_addressed`
   - Concern does not apply to current code -> `invalid`

**CRITICAL:** Do NOT shortcut this verification. `thread_outdated` does NOT mean the issue was fixed or resolved. It means the diff moved. The only way to determine actual state is to read the file at the referenced line on current HEAD.

**Evidence requirement:** Any classification resulting from a `thread_outdated` comment MUST be accompanied by a verification note: "Verified against current HEAD at `<file>:<line>` -- `<finding>`."

**Distinction from minimized:** `thread_outdated` is NOT `minimized`. The author did not retract the comment. The comment still represents a valid review concern. Treat it with the same seriousness as any non-outdated comment, with the extra verification step on top.

---

### thread_resolved

**Definition:** The thread is marked as "resolved" in the GitHub UI. A human (usually the PR author or reviewer) clicked "Resolve conversation."

**Classification rule:** `thread_resolved` is a weak signal. It means someone considered the conversation done. It does NOT mean the code issue was fixed. The resolver may have collapsed the thread to reduce visual noise, or may have resolved it after a discussion that did not result in a code change.

**Combined with thread_outdated:** When a comment has BOTH `thread_outdated: true` AND `thread_resolved: true`, the resolution signal is still NOT proof of fix-state. You MUST read the current code to determine the actual state:

- Issue fully fixed -> `already_fixed`
- Issue persists -> `valid`
- Issue partially addressed -> `partially_addressed`

**thread_resolved alone (without thread_outdated):** Same rule applies. Check if a code change was actually made. If only discussion happened and no code changed, the thread may be resolved conversationally but the code concern may still exist.

---

### has_replies

**Definition:** The `has_replies` field from `list_comments.py` is `true`. The comment thread has one or more replies in addition to the original comment.

**Primary classification:** `already_replied`. However, you must verify these conditions:

1. **Author is human.** If the only reply is from a bot, do NOT classify as `already_replied`. Bot replies to bot comments do not resolve the thread.
2. **Reply is substantive.** A reply that says "Good point" or "I'll check this" does not actually address the concern. Such replies should result in a `needs_clarification` or `valid` classification depending on whether you can proceed without the author's input.
3. **Reply is not yours.** If you are re-processing a PR and the reply is from a previous pass of the same agent, treat it as not yet replied.

**Override at Step 3:** The user can reclassify any `already_replied` item if they believe the existing reply is insufficient.

**Action:** No action (skip). Maps to dossier Section C.

---

### Ghost Author / Empty Body

**Ghost Author** — deleted account, `author` field is `null` (GitHub displays "ghost"): Classify normally by comment body content. If the comment is actionable, the reply still goes to the thread. The thread exists even if the author's account is gone.

**Empty Body** — body field is empty, whitespace-only, or contains only a newline: Classify as `informational`. No content to act on. The comment may have been a quick reaction or an accidental post.

---

### Self-Review

**Definition:** The comment author is the same as the PR author.

**Classification:** Classify by content using the same rules as any other comment. Self-review notes can be `informational` (author noting something for awareness) or `actionable` (author flagging an issue they identified themselves). Do NOT dismiss self-review comments. They often contain the most accurate insights since the author knows the code best.

---

## Evidence Requirements

This section defines what constitutes acceptable evidence for high-risk conclusions. These conclusions require proof beyond a reasonable doubt because misclassifying them has a high cost.

### already_fixed

**Requires ONE of these evidence forms:**

1. **Direct code citation:** "Current code at `<file>:<line>` shows `<correct code>`. The reviewer's concern about `<X>` no longer applies." The citation must be specific enough that someone reading it can verify the fix independently.
2. **Commit evidence:** "Commit `<sha>` applied the fix at `<file>:<line>`. Before the commit, `<old behavior>`. After the commit, `<new behavior>`."

**Forbidden as evidence:**

- `thread_outdated: true` -- not proof
- `thread_resolved: true` -- not proof
- A bot reply saying "Good catch" or "Let's fix this" -- not proof
- "The code looks different now" without specific citation -- not proof
- A human said "I fixed this" in a comment but the code does not reflect it -- not proof

### partially_addressed

**Requires ALL three evidence forms:**

1. Citation of the existing fix attempt: what changed, where, and in which commit
2. Citation of the remaining issue: the specific code lines or behavior that still do not match the reviewer's request
3. Explanation of insufficiency: why the attempted fix does not resolve the core concern, stated in terms of what the reviewer asked for vs what was done

### already_replied

**Requires:**

1. `has_replies: true` confirmed in the JSON output
2. Verification that the reply author is human, not a bot
3. (Recommended but not required) A quote from the reply that shows the concern was substantively addressed

---

## Dossier Section Mapping

The following table maps every classification conclusion to its dossier section and required action:

| Intent | Conclusion | Dossier Section | Action |
|--------|-----------|-----------------|--------|
| actionable | `valid` | Section A | Code change + test + reply + commit |
| actionable | `invalid` | Section B | Reply only (explain why) |
| actionable | `already_fixed` | Section B | Reply only (confirm already fixed) |
| actionable | `already_replied` | Section C | No action -- already handled |
| actionable | `out_of_scope` | Section B | Reply only (suggest follow-up if needed) |
| actionable | `needs_clarification` | Section B | Reply only (with resolved direction) |
| actionable | `partially_addressed` | Section A | Code change + reply (rework or extend existing fix) |
| informational | -- | Section C | No action at all |

This mapping is authoritative. Section assignment MUST match this table. Cross-section leakage is checked by the pre-write scan in `dossier-output.md` (see Validation Gates).
