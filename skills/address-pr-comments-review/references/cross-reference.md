# Cross-Reference Protocol

Step 2b duplicate, conflict, relation, and already-replied detection across the full classified comment set. Also covers cross-file pattern escalation. Performed AFTER individual classification in `classify.md`.

## Duplicate Detection

### Purpose

Find two or more comments that point to the same or substantially overlapping concern. Prevent duplicate work and duplicate replies.

### Detection Signals

| Signal | Criteria | Example |
|--------|----------|---------|
| Exact match | Same `path:line` + same semantic issue | Both @copilot and @alice flag `foo.ts:42` for the same null-check concern |
| Proximity match | Different line, same function or method body | `foo.ts:42` and `foo.ts:47` are both in `handleSubmit()` and both flag error handling gaps |
| Semantic match | Same conceptual concern on related code | "Add input validation" on the entry point and "missing sanitization" on the data sink -- both describe the same validation gap |

### Duplicate Boundaries

| Situation | Verdict | Rationale |
|-----------|---------|-----------|
| Same `path:line`, different wording | Duplicate | Same location + same concern, regardless of wording |
| Same `path:line`, genuinely different concern | Not duplicate | E.g., "rename this variable" + "add null check" on same line -- different issues |
| Same function, different lines, same concern | Duplicate | Lines within the same function body addressing the same issue |
| Same function, different lines, different concerns | Not duplicate | E.g., "handleSubmit needs error boundary" + "handleSubmit returns wrong type" |
| Same semantic concern across different functions | Not duplicate | E.g., "add null check in submit()" and "add null check in validate()" -- different contexts. Flag as related (see Related Detection) instead. |

### Merge Action

When duplicates are found:
1. Create ONE entry in the overview table with all authors listed (format: `@copilot, @alice`)
2. Assign the most specific common conclusion (e.g., `valid` from `valid` + `valid`, or surface conflict if conclusions differ)
3. In the dossier, produce ONE task with all authors listed
4. Reply to each author individually using their own `in_reply_to` ID

### False Positive Guard

Similar-sounding wording does not equal same concern. "The error handling is wrong" and "the error message is misspelled" are on the same code but are different concerns. When in doubt, do NOT merge -- flag as related instead.

---

## Conflict Detection

### Purpose

Find comments that give opposing or incompatible recommendations on the same code. Surface the disagreement for human decision.

### Detection Signals

| Type | Criteria | Example |
|------|----------|---------|
| Direct conflict | Opposite changes on same code | @alice: "use `const`" vs @bob: "use `let`" |
| Approach conflict | Incompatible strategies | @copilot: "extract to helper function" vs @alice: "inline for readability" |
| Conclusion conflict | Different conclusions on same concern | @bot: `valid` (needs fixing) vs @human: `invalid` (does not apply) |

### Conflict Action

1. Merge into one entry in the overview table
2. Mark with a red flag in the discussion column
3. Present both options neutrally -- do NOT weight by source popularity, seniority, or who commented first
4. In the dossier: chosen direction goes to Section A or B, rejected direction goes to Section B as a reply-only item

### Human vs Bot Conflicts

When a human reviewer conflicts with an AI bot on the same concern:
- Present both sides neutrally. Do not weight by source type.
- The human is the intended decision-maker, but the bot perspective must be accurately represented.
- During Step 3, ask the user which approach to follow.

### Conclusion Conflicts

When comments on the same concern have different conclusions (e.g., one says `valid`, another says `invalid`):
- Both conclusions are preserved in the merged entry
- The overview table conclusion becomes `conflict` (not `valid` or `invalid`)
- The user resolves during Step 3 discussion

---

## Related Detection

### Purpose

Find comments that are causally or logically connected across different files or lines. Enable plan mode to order dependent tasks correctly.

### Detection Signals

| Type | Criteria | Example |
|------|----------|---------|
| Call chain | Comment A is on a callee, Comment B is on a caller | A flags `validateInput()` for refactoring, B flags the caller `handleSubmit()` for error handling -- fix callee first |
| Shared type or interface | Both comments touch the same type definition | Both flag changes to the same `UserProfile` struct in different files |
| Sequential workflow | Fixing A may resolve or change B's concern | Adding the validation function that A asked for may address B's concern about missing error handling upstream |
| Logical group | Comments that should be addressed together for consistency | Same naming convention or error handling style across multiple files |

### Relation Action

1. Note the relationship in the overview table (e.g., "Depends on #3")
2. In the dossier, add dependency metadata:
   - `fixes_needed_before`: Tasks that must be completed first
   - `may_become_unnecessary`: Tasks whose concern may be resolved by another task
   - `should_be_grouped`: Tasks that should be addressed in the same commit
3. Plan mode uses this metadata to order tasks and group related changes

### Related vs Duplicate Boundary

Two comments are related, not duplicates, when:
- They touch different code locations
- They address different aspects of a shared concern
- Fixing one has implications for the other
- But they do NOT describe the same issue at the same location

---

## Already-Replied Detection

See `classify.md` §has_replies and §already_replied for the detection protocol and conclusion rules. This section only covers the cross-reference interaction: when duplicates share a reply, and conservative default behavior for insufficient replies.

### Duplicate Comments and Already-Replied

When a duplicate comment (same concern, different author) is detected and the primary comment has `has_replies: true`:
- If the primary comment's reply is sufficient, the duplicate is also considered already-replied
- If the primary comment's reply is not sufficient, the duplicate inherits the pending status
- In both cases, each author still gets an individual reply (or no reply, depending on sufficiency)

### Conservative Default

Always default to `already_replied` when `has_replies: true`, even when the reply appears insufficient. This prevents re-opening threads without explicit user consent. The user overrides during Step 3 discussion. Flag insufficient replies with `replied (pending)` in the overview table.

---

## Cross-File Escalation

When a reviewer flags a structural issue and a targeted search finds the same pattern in sibling files, escalate from single-file fix to documented cross-file pattern. Without escalation, the workflow treats it as a single-file concern, leaving the broader pattern unfixed.

### Detection Method

Cross-file escalation is a **manual targeted search** performed by the agent during the cross-reference pass of Step 2. It is NOT automated clustering or static analysis.

When a classified comment flags a structural concern (ordering, initialization, shutdown, concurrency, pattern consistency) in a single file:

1. Identify the key code pattern -- function call, ordering sequence, code block structure
2. Run `grep` or similar search within the codebase for the same pattern
3. Count occurrences across files (excluding the already-commented file)
4. Compare each match to ensure it is genuinely the same pattern (not coincidental)

### Evidence Threshold

Escalation is gated by the number of confirmed matches beyond the original file:

| Evidence level | Matches beyond commented file | Action |
|--------------|-------------------------------|--------|
| None | 0 | No escalation |
| Weak | 1 | Observe only. Optionally note in dossier. |
| Moderate | 2-3 | Guardrail: "Cross-file pattern in {files} — fix only commented file" |
| Strong | 4+ or same subsystem | Full escalation: Guardrail + "Cross-File Pattern Detected" section |

### Evidence Quality Rules

- Count only files where the pattern is genuinely the SAME concern (e.g., same function call at the wrong point in a lifecycle). Do NOT count files where the pattern differs structurally — e.g., `try { cleanup() }` is NOT the same issue as bare `cleanup()` at the wrong lifecycle point.
- Document the grep command and its exact or approximate results in the escalation note so the user can verify.
- If the pattern exists in test files only, reduce the evidence level by one tier. Test setup and teardown are structurally different from production code.

### Required Output Treatment

When escalation triggers at Moderate (2-3 matches) or Strong (4+ matches):

| Trigger | Dossier additions |
|---------|------------------|
| **Moderate+** | **Scope Guardrail**: `\| Cross-file pattern detected in {files} \| Fix only the commented file. Do NOT scope-creep. \|` + Dedup Note row listing files and guardrail |
| **Strong** | Above + **"Cross-File Pattern Detected" section** (format: `dossier-output.md` §Cross-File Pattern Detected) |
| **Reply (optional)** | Note in reply to reviewer: "Fixed in this file. Same pattern in {N} other files — follow-up if appropriate." |

The commented file remains the only Section A code-change task. Escalation does NOT create additional Section A items.

### Escalation Boundaries

| Situation | Escalate? | Rationale |
|-----------|-----------|-----------|
| Same function call ordering in 3+ files, same module | Yes | Structural pattern |
| Comment explicitly asks "fix this everywhere" | Yes | Reviewer requested global fix — user must confirm scope during Step 3 |
| Same naming convention across many files | No | Style consistency ≠ structural bug |
| Single occurrence in 1 other file | No | Weak evidence |
| Pattern exists only in test files | Reduce one tier | Test setup/teardown differs structurally from production |

### Escalation Is Not Classification

Cross-file escalation does NOT create additional classified comments. It does NOT change the conclusion of the primary comment. It is a metadata layer that:
- Records a detected pattern at a specific evidence level
- Adds a guardrail against scope creep
- Provides visibility for follow-up decisions in a separate PR

The escalation metadata is consumed by the dossier template (Section A, Scope Guardrails, Dedup and Conflict Notes) and by the user during Step 3 (to decide whether the follow-up is in scope for the current PR).
