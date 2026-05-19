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

When a human reviewer conflicts with a bot (CodeRabbit, Copilot, etc.) on the same concern:
- Present both sides neutrally
- The human is the intended decision-maker, but the bot perspective must be accurately represented
- During Step 3, ask the user which approach to follow

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

### Purpose

Identify comments that already have a human reply and assess whether the reply is sufficient to consider the concern resolved. Prevent re-addressing already-handled feedback while surfacing threads with pending or insufficient replies.

### Detection Signal

The `has_replies` field from `list_comments.py` output. This field is `true` when the comment thread has at least one subsequent comment from a non-bot author.

| Comment kind | Detection method |
|-------------|-----------------|
| inline | Review thread has more than 1 comment AND at least one is from a non-AI author |
| review body | A subsequent issue comment or COMMENT review exists by a different non-bot author |
| top_level | Same as review body -- subsequent issue comment by a different non-bot author |

### Two-Level Assessment

**Level 1 -- Has a Reply (detection):**

Raw signal from the `has_replies` field. Boolean -- either the thread has a human reply or it does not. This is the gate condition.

**Level 2 -- Reply Is Sufficient (assessment):**

Not all replies are final. Having a reply does not guarantee the concern is resolved. The protocol must assess sufficiency:

| Reply characteristic | Sufficient? | Rationale |
|--------------------|-------------|-----------|
| PR author confirms fix ("Fixed in abc123", "Done", "Good catch") | Sufficient | The concern was addressed |
| Reviewer approves ("Resolved", "LGTM", "Thanks") | Sufficient | The reviewer accepted the resolution |
| PR author states intent ("I'll fix this", "Will address") | Not sufficient | Intent is not a fix. The concern is pending. |
| Bot-generated status update without human confirmation | Not sufficient | No human verified the fix. Flag for override. |
| Reply asks follow-up question or raises a sub-concern | Not sufficient | The thread is still active. May be a new actionable item. |
| Reply from a human is ambiguous ("ok", "noted", emoticon-only) | Not sufficient | Unclear if resolved. Default to insufficient. |

### Sufficiency Action

- `has_replies: true` AND reply is **sufficient**: classify as `already_replied` (Section C, no action). The reply genuinely resolved the concern.
- `has_replies: true` BUT reply is **not sufficient**: still default to `already_replied` conclusion conservatively, but add a pending flag in the overview table (e.g., `replied (pending)`). The user can reclassify during Step 3. This signals that the thread has activity but may not be resolved.

### Rationale for Conservative Default

Always default to `already_replied` when `has_replies: true`, even when the reply appears insufficient. This prevents the protocol from re-opening threads without explicit user consent. The user overrides during Step 3 discussion if needed. The pending flag gives the user visibility without forcing a decision.

### Duplicate Comments and Already-Replied

When a duplicate comment (same concern, different author) is detected and the primary comment has `has_replies: true`:
- If the primary comment's reply is sufficient, the duplicate is also considered already-replied
- If the primary comment's reply is not sufficient, the duplicate inherits the pending status
- In both cases, each author still gets an individual reply (or no reply, depending on sufficiency)

---

## Cross-File Escalation

### Purpose

When a review comment flags an issue in one file, and a targeted search confirms the same pattern exists in other files, escalate the concern from a single-file fix to a documented cross-file pattern. This prevents the agent from staying stuck on one file while a structural issue propagates through the codebase.

### Motivation (PR #1215)

In PR #1215, a comment on `server/monitor/monitor.go` flagged `CloseAllPublishers()` called before `manager.StopAll()`. The same shutdown ordering issue existed in 4 other `server/*` files, but the workflow treated it as a `monitor.go`-only concern. Cross-file escalation prevents this failure by requiring the agent to search and document the broader pattern.

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
| None | 0 matches | No escalation. Pattern is unique to the commented file. |
| Weak | 1 match in one other file | Observe but do not escalate. Optionally note in the dossier if relevant context suggests broader impact. |
| Moderate | 2-3 matches in different files | Escalate as a guardrail note. Add to Scope Guardrails: "Cross-file pattern detected in {file list} -- fix only the commented file in this task." |
| Strong | 4+ matches or architectural pattern (same module, same subsystem) | Full escalation. Add to Scope Guardrails AND add a "Cross-File Pattern Detected" section in the dossier with file list and follow-up recommendation. |

### Evidence Quality Rules

- Count only files where the pattern is genuinely the SAME concern (e.g., same function call at the wrong ordering point). Do NOT count files where the pattern differs structurally -- e.g., `defer CloseAllPublishers()` is NOT the same issue as bare `CloseAllPublishers()` at the wrong lifecycle point.
- Document the grep command and its exact or approximate results in the escalation note so the user can verify.
- If the pattern exists in test files only, reduce the evidence level by one tier. Test setup and teardown are structurally different from production code.

### Required Output Treatment

When cross-file escalation triggers at Moderate or Strong evidence:

1. **Primary fix**: The commented file remains a Section A task (code change + reply). This is the only code change task. Escalation does NOT create additional Section A items.

2. **Scope Guardrail** (Moderate and Strong): Add a Scope Guardrail item in the dossier:
   ```
   | Cross-file pattern detected in {file list} | Fix only the commented file in this task. Do NOT scope-creep to other files. Consider a separate follow-up PR for remaining matches. |
   ```

3. **Dossier Dedup and Conflict Notes** (Moderate and Strong): Add a row:
   ```
   | Cross-file pattern | {N} | Pattern detected in {files}. Scope-creep guardrail applied. Fix only {commented file}. |
   ```

4. **Cross-File Pattern Detected section** (Strong only): Append before the Scope Guardrails section:
   ```
   ## Cross-File Pattern Detected

   - **Grep command**: `grep -r "pattern" server/ --include="*.go"`
   - **Files with same pattern**: {comma-separated file list}
   - **Current fix scope**: {commented file} only (Section A of this dossier)
   - **Recommendation**: Create a follow-up PR to address remaining {N} files with the same pattern.
   ```

5. **Reply**: In the reply to the reviewer, optionally note the cross-file pattern: "Fixed in this file. The same pattern exists in {N} other files. Will address in a follow-up if appropriate."

### Escalation Boundaries

| Situation | Should escalate? | Rationale |
|-----------|-----------------|-----------|
| Same function call ordering in 3+ server files | Yes | Structural pattern, same module |
| Same variable naming convention in 5+ files | No | Style consistency is not a structural bug pattern |
| Single occurrence of a pattern in 1 other file | No | Weak evidence. Observe only. |
| Comment explicitly asks "fix this everywhere" | Yes | Reviewer requested global fix. All files become tasks, but user must confirm scope during Step 3. |
| Pattern exists in test files only | Reduce tier | Test setup/teardown differs structurally from production code |

### Escalation Is Not Classification

Cross-file escalation does NOT create additional classified comments. It does NOT change the conclusion of the primary comment. It is a metadata layer that:
- Records a detected pattern at a specific evidence level
- Adds a guardrail against scope creep
- Provides visibility for follow-up decisions in a separate PR

The escalation metadata is consumed by the dossier template (Section A, Scope Guardrails, Dedup and Conflict Notes) and by the user during Step 3 (to decide whether the follow-up is in scope for the current PR).
