# Reply Policy

This file defines the reply policy for responding to PR review comments. It covers when and how to reply, what content is required for each conclusion type, the pre-reply gate that prevents duplicate replies, and when a change summary is mandatory alongside a fix confirmation. It is responsible for ensuring every reply is correctly addressed, properly formatted, directed to the right endpoint, and never sent twice to the same thread.

## Precedence

Layer 3 (decision protocols). Consumes conclusion assignments from classification and cross-reference protocols. Reply templates are selected by conclusion type (assigned in Step 2). Reply endpoints are selected by comment kind (assigned in Step 1, documented in dossier). Template defaults can be overridden by explicit instructions from the interaction protocol (Step 3).

**Reply policy is subordinate to the cross-reference protocol's already-replied assessment.** If cross-reference determines a reply is sufficient, this policy prevents a new reply from being sent. If cross-reference flags a reply as insufficient, this policy requires user override before composing a new reply.

---

## Scope

This file covers:

- **Pre-Reply Gate**: mandatory checks before composing any reply
- **Change Summary Rule**: when `Fixed in <sha>` alone is insufficient
- **Reply templates per conclusion**: valid (fixed), invalid, already_fixed, out_of_scope, needs_clarification, partially_addressed, conflict (not chosen)
- **Endpoint kinds**: inline, review, top_level (reference only -- commands in dossier.md)
- **Duplicate author reply strategy**: same content, per-author `in_reply_to` IDs
- **Partial fix reply**: acknowledging the attempt, explaining insufficiency, describing the correct direction
- **Already-replied blocking**: when an existing reply prevents a new reply from being composed

## Out of Scope

- Conclusion assignment -> `classification.md`
- Duplicate and conflict detection -> `cross-reference.md`
- Dossier structure and endpoint commands -> `dossier.md` (contains `gh api` commands)
- Platform-specific `gh` installation or authentication -> `platform.md`
- Interaction protocol for resolving needs_clarification or conflicts -> `interaction.md`

---

## Pre-Reply Gate

**Before composing any reply, run this checklist.** The gate exists to prevent the two highest-cost reply failures: replying to a thread that already has a sufficient response, and sending an overconfident `Fixed in <sha>` for a fix that is misleading without context.

### Gate Checklist

| # | Check | Condition to pass | Action if failed |
|---|-------|-------------------|------------------|
| 1 | **Already replied?** | Does this thread have `has_replies: true` with a substantively sufficient human reply (per cross-reference protocol Level 2)? | Do NOT reply. The existing reply already addresses the concern. If the existing reply is insufficient, do NOT reply either -- flag for user override at Step 3. |
| 2 | **Duplicate author?** | Is this comment one of multiple that were merged as duplicates? | Compose ONE reply. Send it to EACH author individually via their own `in_reply_to` ID. Do not reply to only one author. |
| 3 | **Change summary needed?** | Does the conclusion require a change summary alongside the fix confirmation (see Change Summary Rule below)? | Add a change summary before `Fixed in <sha>`. Do not send a bare `Fixed in <sha>` alone. |
| 4 | **Conclusion still valid?** | Has the code state changed since classification (e.g., a new commit was pushed, or the diff shifted)? | Re-verify the conclusion against current HEAD. If the issue no longer exists, reclassify before replying. |

### Gate Enforcement

If check #1 fails, the reply is blocked entirely. Do not compose, draft, or prepare a reply. Do not look for ways around the block. The existing reply stands unless the user explicitly reclassifies during Step 3.

All four checks must pass before any reply content is written. The gate is evaluated per-author: for duplicate comments, run the gate for each author individually (check #2 ensures the content is the same, but check #1 may differ per author if some threads have replies and others do not).

---

## Change Summary Rule

### Principle

A pure `Fixed in <sha>` confirmation implies the fix speaks for itself. When the fix is misleading, partial, or directionally non-obvious without context, the commit SHA alone does not satisfy the reviewer's concern. A change summary must accompany the fix reference to explain what changed and why.

### When `Fixed in <sha>` Alone Is Allowed

- The fix is straightforward and the change is fully described by the commit message
- The reviewer's concern was a single, unambiguous issue and the fix addresses it directly
- Example: "Rename `foo` to `bar`" -> reply "Fixed in abc123." (the commit message "Rename foo to bar" explains the fix)

### When a Change Summary Is Mandatory

A change summary that describes what was done and why MUST accompany `Fixed in <sha>` in any of these situations:

| Situation | Example | Why pure SHA is misleading |
|-----------|---------|---------------------------|
| **Direction correction** | Reviewer asked to move `CloseAllPublishers()` AFTER `manager.StopAll()`. Current code moved it BEFORE. | The fix exists but makes the problem worse. `Fixed in <sha>` implies the concern was correctly resolved. |
| **Partial fix** | Fix addressed one location but the same pattern exists at N other locations. | The core concern is not fully resolved. `Fixed in <sha>` implies completion. The reply must explain the scope boundary. |
| **Reframed concern** | The fix takes a different approach than the reviewer suggested but achieves the same intent. | The reviewer may not recognize their concern in the alternate implementation. The reply must describe the approach taken. |
| **Non-obvious change** | The fix involves a subtle refactor, a dependency change, or multiple files. | The commit SHA alone does not convey the scope or reasoning. |
| **Cross-file pattern noted** | Only the commented file was fixed; other files with the same pattern remain. | `Fixed in <sha>` implies the pattern is resolved everywhere. The reply must clarify scope boundaries. |

### Change Summary Format

The change summary precedes or follows the `Fixed in <sha>` line, depending on what needs explaining:

```
Fixed in abc123. The fix changes the shutdown sequence in monitor.go —
CloseAllPublishers() now runs after manager.StopAll() completes,
matching the reviewer's concern about publisher ordering.
```

For partial fixes, the summary must include the scope boundary:

```
Fixed in abc123 (monitor.go only). The same ordering issue exists in
4 other server/* files. A follow-up PR will address the remaining files.
```

For direction corrections, the summary must acknowledge the previous approach was wrong:

```
Corrected the fix direction in abc123. The previous attempt placed
CloseAllPublishers() before StopAll(), which made the ordering worse.
Now runs after StopAll() as intended.
```

---

## Reply Templates Per Conclusion

Each conclusion maps to exactly one reply template. The template is the default; the interaction protocol (Step 3) or the Change Summary Rule may override or extend it.

| Conclusion | Template | Change summary required? | Notes |
|-----------|----------|-------------------------|-------|
| valid (fixed) | `Fixed in <commit_sha>.` | See Change Summary Rule above | Bare SHA only when fix is self-explanatory. Always check the rule. |
| invalid | `This suggestion doesn't apply because <reason>.` | No | Reason is mandatory -- one sentence minimum. |
| already_fixed | `Already resolved in the current code — no changes needed.` | No | Evidence of the existing fix must be citeable per classification protocol. |
| out_of_scope | `This is outside the scope of this PR. <follow-up>.` | No | Follow-up suggestion is optional but recommended. |
| needs_clarification | `Confirmed: <resolved direction>.` | No | Direction is resolved during Step 3 interaction, unlike auto mode where the reply asks the question. |
| partially_addressed | `Acknowledged. The existing fix at <sha> addresses <X> but does not address <Y>. <Corrected/reworked> in <sha> to <describe correct fix>.` | Yes -- always | See Partial Fix Reply section below for full requirements. |
| conflict (not chosen) | `Thanks for the suggestion. We went with @other's approach for <reason>.` | No | Reason must neutrally explain the choice without disparaging the rejected approach. |

### Partial Fix Reply (partially_addressed)

When the classification protocol assigned `partially_addressed`, the reply MUST include three components in order:

1. **Acknowledge the existing attempt**: Cite the commit SHA and what it attempted to fix. This shows the reviewer you saw their original feedback was addressed, even if incompletely.

2. **Explain the insufficiency**: State why the existing fix does not resolve the core concern. Reference the specific code lines that remain problematic. Use neutral factual language, not blame.

3. **Describe the correct fix**: State what was done in the new fix (or what will be done). Reference the new commit SHA if the fix is already applied.

Format:

```
The fix at abc123 addressed the CloseAllPublishers() ordering by moving
it before manager.StopAll(), but the reviewer's concern was that close
should happen AFTER stop completes. This rework in def456 moves the
call to the correct position in the shutdown sequence.
```

Do NOT omit the acknowledgment. A `partially_addressed` reply that jumps straight to "Fixed in <sha>" without acknowledging the previous attempt reads as dismissive. The acknowledgment is not optional.

### Duplicate Author Reply Strategy

When a comment was merged as a duplicate (same concern, multiple authors):

- Compose ONE reply with the same content for all authors
- Send to EACH author individually using their own `in_reply_to` ID
- Do NOT reply to only one author, even if the others are bots
- Do NOT create separate reply tasks for each author in the dossier -- one task, multiple `in_reply_to` IDs

The reply content is identical across authors. The only difference is the `in_reply_to` parameter in the API call. This is a per-`in_reply_to` dispatch, not a per-author content variation.

### Already-Replied Blocking

When cross-reference protocol Level 2 determines a reply is sufficient:

- The reply is blocked. Do not compose, draft, or prepare a reply.
- The existing reply stands. No override without explicit user action at Step 3.
- This applies even if the existing reply is by a different person or takes a different tone. If the reply substantively addresses the concern, it is sufficient.

When cross-reference protocol Level 2 determines a reply is NOT sufficient:

- Default to blocked (conservative). The existing thread has activity.
- Flag the insufficiency for the user at Step 3 with a pending indicator.
- Do NOT compose a reply unilaterally. Only proceed if the user explicitly reclassifies the comment.

This two-level approach prevents the agent from overruling an existing reply while giving the user visibility into potentially unresolved threads.

---

## Endpoint Selection (Reference Only)

Endpoint commands are documented in `dossier.md` (the `gh api` commands with all required parameters). This file only maps conclusion kinds to endpoint kinds.

| Comment kind | Endpoint | Key parameter |
|-------------|----------|---------------|
| inline | `repos/{owner}/{repo}/pulls/{pr}/comments` | `in_reply_to=<comment_id>` |
| review body | `repos/{owner}/{repo}/issues/{pr}/comments` | mention @author in body |
| top_level | `repos/{owner}/{repo}/issues/{pr}/comments` | -- |

**Commit SHA note**: Inline replies require a valid commit SHA on the PR branch. Review and top_level replies do not need `commit_id`.

See `dossier.md` Reply Endpoints section for exact `gh api` command syntax with all flags.

---

## Key Design Decisions

### Pre-Reply Gate Is a Hard Stop

The Pre-Reply Gate is not a suggestion or a "best practice" reminder. It is a hard stop. If any check fails, the reply is blocked. The gate exists because the cost of a duplicate reply or an overconfident `Fixed in <sha>` is higher than the cost of a delayed reply. The gate prevents the two highest-frequency failure modes identified in production (PR #1215 / discussion_r3257258893 and duplicate-thread patterns).

### Change Summary > Fixed in <sha> by Default

When in doubt, add a change summary. The default should NOT be `Fixed in <sha>` alone. The default should be `Fixed in <sha> -- <one-line summary>`. If the change is truly obvious, the summary can be dropped. This inverts the default from the natural inclination of "just cite the SHA" to "always add context unless the context is obvious."

### Partial Fix Requires Bounded Explanation

The `partially_addressed` reply must be bounded: explain what the existing fix did, why it is insufficient, and what the correct fix does. Do NOT speculate about why the partial fix happened. Do NOT assign blame. Do NOT write an essay. Three sentences maximum for each of the three components.

### Duplicate-Reply Prevention Is a Pre-Reply Decision

Duplicate-reply prevention (checking whether this thread already has a sufficient reply) is evaluated BEFORE composing any reply, not during the reply composition step. This is a deliberate ordering: the gate runs first, so no tokens are wasted drafting a reply that will never be sent. The two-level assessment (has a reply vs reply is sufficient) comes from the cross-reference protocol, not from reply.md -- this file only enforces the block.
