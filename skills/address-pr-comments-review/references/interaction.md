# Interaction Protocol

This file defines the interaction protocol for the interactive review confirmation phase. It governs the conversation flow between the AI analyst and the user during Steps 3 and 4: overview table presentation, silent consent, discussion of flagged items, and final confirmation.

---

## Step 3: Overview Table (MANDATORY)

Every invocation MUST produce the overview table. **Even when there are zero actionable comments, the table is mandatory.**

### Table Format

```
## PR #N Comment Analysis -- X total (Y raw), Z actionable (after dedup)

### Overview
| # | 来源 | 类型 | 文件 | 摘要 | 结论 | 去重/冲突 | 讨论 |
|---|------|------|------|------|------|-----------|------|
| 1 | @alice, @copilot | inline | foo.ts:42 | var → const | valid | ≡ merged (2 reviews) | |
| 2 | @bot   | inline | bar.ts:15 | rename suggestion | invalid | | |
| 3 | @alice vs @bob | inline | baz.ts:8 | const vs let choice | ⚠️ conflict | ↯ conflicting advice | 🔴 resolve |
| 4 | @human | inline | qux.ts:3 | logic question | needs_clarification | | 🔴 needs input |
| 5 | @reviewer | review | — | LGTM but note on perf | already_replied | ↩ already replied | |
```

### Legend

- `≡ merged` -- duplicate comments combined into one entry
- `↯ conflict` -- opposing recommendations, user must choose
- `↩ already replied` -- comment already has a human reply; skipped by default
- `🔴 resolve` -- needs user decision before proceeding

### Zero-Actionable MUST Still Produce the Table

When every comment is `informational`, `already_replied`, or otherwise non-actionable, the table must still appear with all items listed. A statement like "0 actionable" is NOT a substitute for the table. The table header, rows, and legend are mandatory regardless of the number of actionable items.

### Self-Check (Do Not Skip)

**SELF-CHECK**: Before proceeding, verify your output contains a table with the header `| # | 来源 | 类型 | 文件 | 摘要 | 结论 | 去重/冲突 | 讨论 |`. If the table is missing, you have NOT completed this step. Stop and regenerate the table.

---

## Step 3.5: Interactive Discussion

Present the table, then guide discussion in this order:

### 1. Discuss 🔴 Items First

Expand each 🔴 item with context. For conflicts, present both sides:

**Comment #3 -- Conflict on baz.ts:8**:
- @alice suggests: `const result = await fetch()` (immutable)
- @bob suggests: `let result = await fetch()` (may reassign later)
- Current code uses `var`. Both agree it should change, disagree on replacement.
- Which approach? (const / let / other)

For `needs_clarification` items, state what information is missing and what decision is needed:

**Comment #4 -- Question on qux.ts:3**:
- @human asks: "Is this edge case handled?"
- Current code is missing a guard for empty input.
- How should this be handled? (add guard / it's intentional / defer to follow-up)

### 2. Discussion Gating

🔴 items are blocking. They must be resolved before proceeding to Step 4 and dossier generation:

| Item Type | Gating Rule |
|-----------|-------------|
| `🔴 resolve` (conflict) | User must choose one option before proceeding |
| `🔴 needs_clarification` | User must provide direction before proceeding |
| `🔴 high-risk` | User must acknowledge or override before proceeding |
| No 🔴 | No blocking discussion needed; proceed directly |

All 🔴 items must be resolved (conclusion changed or confirmed) before the final confirmation table is produced. The validation protocol (`validation.md`) enforces this.

### 3. Silent Consent for Non-🔴 Items

Items without 🔴 are accepted as-is per AI conclusion. The following all count as consent:

- User says "continue", "ok", "go ahead"
- User does not object to an item
- User explicitly agrees ("yes", "that's right", "correct")
- User only discusses 🔴 items without mentioning non-🔴 ones

The AI may prompt: "The remaining M items are accepted by silent consent unless you object. Shall we proceed?"

Any item can be objected to by number at any point. If the user objects, move that item into discussion and update the conclusion as needed.

### 4. Scaling for Large PRs (20+ Actionable Comments)

| Problem | Solution |
|---------|----------|
| Overview table too long | Show 🔴 items inline, collapse 📝 items to a summary line: "12 silent-consent items (see dossier for details)" |
| Too many 🔴 to discuss at once | Batch into groups of 5-7, discuss one batch at a time |
| User overwhelmed | Offer to prioritize: "Should we discuss CRITICAL/high-risk items first, then handle the rest in silent consent?" |
| Dossier would be enormous | Section A/B items are already individual -- plan mode handles scale. Dossier length is expected for large PRs. |

In compressed mode:
- The header row MUST still be shown at least once (even if items are collapsed)
- The SELF-CHECK still applies: verify the table header exists in your output
- Collapsed items should still be countable from the summary line

---

## Step 4: Final Confirmation Table

After all discussion converges, produce an updated table reflecting every outcome. All 🔴 items must be resolved.

### Change Summary

Include a change summary so the user can quickly see what changed from Step 3:

```
## Changes from Step 3
- #2: conclusion changed from `valid` to `invalid` (discussion: doesn't apply after all)
- #3: conflict resolved -- chose @alice's `const` approach, rejecting @bob's `let`
- #5: split from merged entry #4 (discussion revealed different issues)
- #7: conclusion changed from `needs_clarification` → `valid` (user provided direction)
```

### Final Overview Table

```
### Final Overview
| # | ... (updated table with all changes applied) |
```

The same table format and SELF-CHECK rules apply to the final table.

### Confirmation Gate

The user must explicitly confirm before dossier generation. Confirmation equivalents:

- "ok"
- "yes"
- "looks good"
- "proceed"
- "confirmed"
- Any affirmative response

If the user does not explicitly confirm, ask: "Shall I proceed with dossier generation based on this final table?"

The validation protocol (`validation.md`) enforces that Step 4 confirmation was obtained before Step 4 dossier generation is allowed.

---

## Change Summary Behavior

The change summary between Step 3 and Step 4 shows the user what their decisions affected. This prevents surprises at the final table.

| Situation | Change Summary Should Show |
|-----------|---------------------------|
| Conclusion changed | Old → new value + reason |
| Conflict resolved | Which option was chosen |
| Entry split from merge | Original merged entry + new separate entries |
| `needs_clarification` → resolved | What direction was provided |
| Item removed/abandoned | Reason for removal |

If no changes resulted from discussion, state explicitly: "No changes from Step 3 -- all conclusions confirmed."

---

## Interaction Flow Summary

```
Step 3: Produce overview table (MANDATORY)
    └─ SELF-CHECK: table header present?
    └─ Zero-actionable? Table still mandatory.
        │
Step 3.5: Interactive Discussion
    ├─ Discuss 🔴 items (blocking -- resolve before proceeding)
    ├─ Silent consent for non-🔴 items
    └─ Large PR? Apply compression strategy
        │
Step 4: Final Confirmation Table
    ├─ Change summary (what changed from Step 3)
    ├─ Updated overview table
    └─ User explicit confirmation ("ok" / equivalent)
        │
Step 4: Dossier Generation (gated by Step 4 confirmation)
```

---


