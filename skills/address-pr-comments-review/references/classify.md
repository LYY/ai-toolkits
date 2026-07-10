# Comment Classification Protocol

Step 2a builds an evidence ledger for actionable comments. Step 2b assigns conclusions from that evidence. Determine source, intent, concern verdict, reviewer suggestion fit, and conclusion for each comment. Cross-reference (duplicate/conflict/relation detection) happens after classification — see `cross-reference.md`.

## Source Detection

Every comment must be classified as either `@human` or `@bot` based on its author.

### @bot Indicators

A comment is `@bot` if ANY of these match:

- `is_ai` is `true` in the JSON output from `list_comments.py` (primary signal — covers CodeRabbit, Copilot, and other known AI reviewers)
- Author login ends with `[bot]` (GitHub's standard bot suffix)
- Author `type` is `Bot` in the JSON output

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

## Evidence Ledger Gate

Before assigning any conclusion to an `actionable` comment, create an evidence ledger entry. The ledger separates the reviewer's concern from the reviewer's proposed fix.

### Required Fields

| Field | Required content |
|-------|------------------|
| **Reviewer concern** | The underlying bug, risk, behavior gap, missing test, or maintainability issue being raised. Do not copy the suggested patch as the concern. |
| **Current code evidence** | Current branch tip code location(s), with `file:line`, showing whether the concern exists now. Read current HEAD, not stale diff context. |
| **Local pattern evidence** | Nearby code, sibling implementation, caller/callee, tests, API contract, or repository convention relevant to choosing the conclusion and fix direction. |
| **Concern verdict** | One of `real`, `not_real`, `already_resolved`, `partially_resolved`, or `unclear`. |
| **Reviewer suggestion fit** | One of `accept`, `modify`, or `reject`, with one-line reason. |
| **Fix direction** | Minimal correct code direction when a code change is needed. This comes from evidence, not from the raw review suggestion. |
| **Verification target** | Specific test, build, static check, or manual verification needed after implementation. |

### Gate Rule

If any required field is missing for an actionable comment, classify it as `needs_clarification` with discussion flag `🔴 insufficient_code_evidence`. Do not place it in Section A and do not generate a code-change task.

### Concern Verdict Mapping

| Concern verdict | Allowed conclusion |
|-----------------|--------------------|
| `real` | `valid`, unless outside PR scope |
| `not_real` | `invalid` |
| `already_resolved` | `already_fixed` |
| `partially_resolved` | `partially_addressed` |
| `unclear` | `needs_clarification` |

### Reviewer Suggestion Fit

The suggestion fit is independent from the concern verdict. A reviewer can identify a real concern and still propose the wrong implementation.

| Fit | Meaning | Section A behavior |
|-----|---------|--------------------|
| `accept` | The suggested fix matches current code evidence and local patterns. | Use the suggestion as the fix direction. |
| `modify` | The concern is real, but the implementation should differ. | Use the evidence-derived fix direction and explain the difference. |
| `reject` | The suggestion is stale, harmful, conflicts with local patterns, or does not address the concern. | Do not use the suggestion. If the concern is real, provide an alternate fix direction; otherwise use Section B. |

Any `modify` or `reject` fit on an actionable comment must be visible in the Step 3 table evidence column. Flag it for discussion when the alternate fix direction is non-mechanical, behavior-changing, or scope-sensitive.

---

## Conclusion Taxonomy

### valid

**When to apply:** The comment identifies a real issue that should be addressed in this PR. The concern is correct, applies to the current code at branch tip, and requires a code change.

**Evidence required:** Complete Evidence Ledger Gate with `Concern verdict: real`. `valid` means the concern is real and needs a code change. It does NOT mean the reviewer's proposed fix should be applied as written. If already fixed, use `already_fixed`. If partially addressed, use `partially_addressed`.

**Action:** Code change + test + reply + commit. Maps to dossier Section A.

---

### invalid

**When to apply:** The comment does not apply to the current code. Common reasons: the reviewer misunderstood the code, the concern is based on a reading error, or the suggestion would break other behavior.

**Evidence required:** Complete Evidence Ledger Gate with `Concern verdict: not_real`, plus one-sentence reason. If the code already handles the concern differently → `already_fixed`, not `invalid`.

**Action:** Reply only (explain why). Maps to dossier Section B.

---

### already_fixed

**When to apply:** The issue raised by the comment has already been resolved in the current branch tip code. The fix exists at the time of classification.

**Evidence required: STRONG evidence required.** Complete Evidence Ledger Gate with `Concern verdict: already_resolved`. Acceptable: current code matches fix, or `git log` shows a commit addressing the concern (cite SHA + what changed). NOT acceptable: `thread_outdated: true`, `thread_resolved: true`, bot acknowledgment, or a fix in a different file.

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

**Evidence required:** Complete Evidence Ledger Gate. Concern must be valid (not `invalid`) but out of this PR's scope. If both invalid and out of scope → `invalid`.

**Action:** Reply only (explain why out of scope, optionally suggest a follow-up). Maps to dossier Section B.

---

### needs_clarification

**When to apply:** The comment raises a question or concern that cannot be classified without additional input from the reviewer or PR author. Examples: a question about intent, a suggestion that depends on unstated requirements, a concern about behavior you cannot reproduce.

**Evidence required:** The ambiguity must originate from the comment itself, or from an incomplete Evidence Ledger Gate that cannot be completed from code/comment context. If the comment is clear but you are confused, read more code before using this conclusion. You must be able to state the specific question that needs answering.

**Action:** Reply only (with resolved direction after clarification). Maps to dossier Section B. Marked with a 🔴 discussion flag.

---

### partially_addressed

**When to apply:** A code change was applied in response to the review comment, but the fix is incomplete, insufficient, or directionally wrong. The reviewer's core concern is not fully resolved despite a visible fix attempt.

This conclusion bridges `valid` (no fix attempted) and `already_fixed` (concern fully resolved). It acknowledges effort while requiring further work.

**Evidence required (ALL four):**

1. Complete Evidence Ledger Gate with `Concern verdict: partially_resolved`.
2. Citation of the existing fix attempt: "Commit `<sha>` attempted to fix by changing `<X>` at `<file>:<line>`"
3. Citation of the remaining issue: "Current code at `<file>:<line>` still shows `<problem>`"
4. Explanation of insufficiency: "The fix addresses `<X>` but does not address `<Y>`."

Common patterns: incomplete scope (same pattern elsewhere), wrong direction (fix makes it worse), partial logic (misses edge cases), insufficient margin (reduces but doesn't eliminate). If no fix was attempted → `valid`. If fix fully resolves → `already_fixed`. If fix is cosmetic + concern resolved → `already_fixed`.

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

**thread_resolved:** Same verification rules as thread_outdated apply. `thread_resolved` means someone closed the conversation thread — it does NOT mean the code was fixed. Read current code to determine actual state.

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
