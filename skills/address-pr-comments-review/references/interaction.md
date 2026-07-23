# Interaction Protocol

This file defines the interaction protocol for the interactive review confirmation phase. It governs the conversation flow between the AI analyst and the user during Steps 3 and 4: overview table presentation, silent consent, discussion of flagged items, and final confirmation. Cleanup commands are maintenance routes and skip this flow.

## Cleanup Routing

If the user invokes `/address-pr-comments-review cleanup` or `/address-pr-comments-review cleanup-all`, load `execution.md` §Artifact Cleanup and stop this interaction flow. Do not produce an overview table, classify comments, generate artifacts, or post replies.

Cleanup confirmation rules:

- `cleanup`: list exact target paths first, then ask for confirmation before deleting.
- `cleanup-all`: show grouped preview and totals first. Treat `--dry-run` as preview-only with no confirmation prompt needed.
- `cleanup-all --older-than <age>`: preview only the directories matching the age filter, then ask for confirmation before deleting.
- Repo-local override paths are never part of default cleanup. Ask for explicit `--artifact-dir <path>` before deleting those.

---

## Step 3: Overview Table (MANDATORY)

Every invocation MUST produce the overview table. **Even when there are zero actionable comments, the table is mandatory.**

### Table Format

```
## PR #N Comment Analysis -- X total (Y raw), Z actionable (after dedup)

### Overview
| # | 来源 | 类型 | 文件 | 摘要 | 结论 | 证据 | 去重/冲突 | 讨论 |
|---|------|------|------|------|------|------|-----------|------|
| 1 | @alice, @copilot | inline | foo.ts:42 | var -> const | valid | HEAD foo.ts:42 + local pattern accepts | ≡ merged (2 reviews) | |
| 2 | @bot   | inline | bar.ts:15 | rename suggestion | invalid | HEAD bar.ts:15 shows existing name is API contract | | |
| 3 | @alice vs @bob | inline | baz.ts:8 | const vs let choice | ⚠️ conflict | HEAD baz.ts:8; fit differs by approach | ↯ conflicting advice | 🔴 resolve |
| 4 | @human | inline | qux.ts:3 | logic question | needs_clarification | missing evidence | | 🔴 insufficient_code_evidence |
| 5 | @reviewer | review | -- | LGTM but note on perf | already_replied | reply verified | ↩ already replied | |
```

### Legend

- `≡ merged` -- duplicate comments combined into one entry
- `↯ conflict` -- opposing recommendations, user must choose
- `↩ already replied` -- comment already has a human reply; skipped by default
- `🔴 resolve` -- needs user decision before proceeding
- `missing evidence` -- Evidence Ledger Gate incomplete; cannot become Section A until resolved

### Zero-Actionable MUST Still Produce the Table

When every comment is `informational`, `already_replied`, or otherwise non-actionable, the table must still appear with all items listed. A statement like "0 actionable" is NOT a substitute for the table. The table header, rows, and legend are mandatory regardless of the number of actionable items.

### Self-Check (Do Not Skip)

**SELF-CHECK**: Before proceeding, verify your output contains a table with the header `| # | 来源 | 类型 | 文件 | 摘要 | 结论 | 证据 | 去重/冲突 | 讨论 |`. If the table is missing, you have NOT completed this step. Stop and regenerate the table.

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
| `🔴 insufficient_code_evidence` | Agent must complete the Evidence Ledger Gate or ask the one unresolved question that code cannot answer |
| `🔴 high-risk` | User must acknowledge or override before proceeding |
| No 🔴 | No blocking discussion needed; proceed directly |

All 🔴 items must be resolved (conclusion changed or confirmed) before the final confirmation table is produced. The validation gates in `dossier-output.md` enforce this.

### 3. Silent Consent for Non-🔴 Items

Items without 🔴 are accepted as-is per AI conclusion only when the evidence column shows a complete Evidence Ledger Gate, no unresolved conflict, and a clear fix direction. The following all count as consent:

- User says "continue", "ok", "go ahead"
- User does not object to an item
- User explicitly agrees ("yes", "that's right", "correct")
- User only discusses 🔴 items without mentioning non-🔴 ones

The AI may prompt: "The remaining M items are accepted by silent consent unless you object. Shall we proceed?"

Any item can be objected to by number at any point. If the user objects, move that item into discussion and update the conclusion as needed.

Silent consent is not allowed for actionable items with `missing evidence`, unclear fix direction, or reviewer suggestion fit `modify`/`reject` unless the difference is mechanical and fully explained in the evidence column. Those items must be discussed or re-grounded before Step 4.

### 4. Zero-Actionable Fast Path

When ALL comments are `informational`, `already_replied`, or otherwise non-actionable:

1. Produce overview table (mandatory — all items listed)
2. Immediately state: "All N comments require no action. No code changes or replies needed."
3. Skip Step 3.5 discussion (no 🔴 items to discuss)
4. End — no dossier needed. Nothing actionable, nothing to implement.

### 5. Scaling for Large PRs (20+ Actionable Comments)

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

When Section A is non-empty, append this route disclosure to the final-table surface before asking for confirmation. Fill every value from the final table and Direct Fix preflight; do not use placeholders in user-visible output:

```text
Recommended route: Direct Fix | Review Dossier
Batch shape: <independent singletons and optional ordered chain>
Section A tasks: N/5
Ordered chains: N/1
Maximum chain length: N/3
Eligible complexity classes: `mechanical`, `local-behavior`
Implementation paths: <paths grouped by task>
Verification companion paths: <paths grouped by task>
Execution: serial
Plan approval: no second plan approval after valid informed Direct Fix confirmation
Fallback reason inventory: <none, or every failed Direct Fix eligibility condition>
```

This disclosure is route-specific. For a Direct Fix recommendation, it states the exact candidate batch and direct-execution consequences. For a Review Dossier recommendation, it names every failed Direct Fix condition in the Fallback reason inventory. Do not offer Direct Fix when the disclosed batch and current preflight differ.

<!-- route-confirmation-contract:start -->
## Route Confirmation Contract

### Stage 3: Classification-Only Confirmation

At Step 3, a generic affirmative such as `proceed` confirms classifications and silent consent only. It authorizes the agent to run the Direct Fix eligibility preflight, then present the Step 4 final table and completed route disclosure. It does not select a route, create an artifact, or authorize an edit, commit, push, reply POST, or reply read-back.

Do not promise either route before preflight completes and the final-table disclosure is shown. Direct Fix eligibility remains owned by `dossier-output.md` §Direct Fix Brief; this contract only controls when route selection becomes valid.

### Stage 4: Disclosure and Route Selection

After preflight, expose the final table and route disclosure. Apply these transitions without changing the Consent State Matrix:

| Preference state | Final disclosure and response | Route-selection result |
|------------------|-------------------------------|------------------------|
| `none` | `disclosed` + `generic-affirmative` | `classification-only`; ask the user to explicitly select `Direct Fix` or `Review Dossier`. |
| `pending-direct-fix` | `disclosed-and-restated` + `generic-affirmative` | `direct-fix-once` for the disclosed batch. |
| `any` | `disclosed` + `explicit-direct-fix` | Select Direct Fix; the Consent State Matrix supplies `direct-fix-once` for the disclosed batch. |
| `any` | `disclosed` + `explicit-review-dossier` | Select Review Dossier; this grants no Direct Fix authority. |

If preflight finds failed Direct Fix eligibility conditions, enumerate every failed condition in the Fallback reason inventory before offering the Review Dossier route. If preflight finds the batch eligible but Direct Fix is still unconfirmed, do not fabricate an eligibility failure or silently choose either route: keep `Fallback reason inventory: none` and ask for the explicit route selection.
<!-- route-confirmation-contract:end -->

### Confirmation Gate

The user must explicitly confirm the final classification table before dossier generation or reply posting. An affirmative response confirms the classification; Direct Fix authorization is evaluated separately by the Consent State Matrix below.

Confirmation equivalents:

- "ok"
- "yes"
- "looks good"
- "proceed"
- "confirmed"
- Any affirmative response

A prior Direct Fix preference remains pending and is not authorization. Carry it forward and restate the pending Direct Fix preference on the final-table surface with the completed route disclosure. When that restatement is present, an affirmative final-table confirmation reconfirms the pending preference and authorizes Direct Fix once. This does not require the user to repeat a magic route keyword or provide a second `Direct Fix` keyword.

Without a pending prior Direct Fix preference, generic consent such as `proceed` confirms classification only, even when the final table discloses Direct Fix. Ask for an explicit Direct Fix selection after disclosure. Silent consent never authorizes Direct Fix.

If the user does not explicitly confirm, ask, based on the final table's A/B counts:
- **Code changes needed (A > 0)**: "Which route should I use for this final table: `Direct Fix` or `Review Dossier`?"
- **Replies only (A = 0, B > 0)**: "Shall I post replies based on this final table and verify them by read-back?"
- **Nothing actionable (A = 0, B = 0)**: no confirmation needed — Post-Confirmation Routing will end.

The validation gates in `dossier-output.md` enforce that Step 4 confirmation was obtained before dossier generation is allowed.

### Consent State Matrix

Use these states exactly. `classification-only`, `invalidated`, and `missing-contract` authorize no Direct Fix execution or handoff. They produce zero edit, commit, push, reply POST, and read-back side effects. Treat any malformed or unrecognized consent input as `missing-contract`.

| Prior preference | Final disclosure | User response | Result |
|------------------|------------------|---------------|--------|
| `none` | `disclosed` | `generic-affirmative` | `classification-only` |
| `pending-direct-fix` | `disclosed-and-restated` | `generic-affirmative` | `direct-fix-once` |
| `any` | `undisclosed` | `generic-affirmative` | `classification-only` |
| `any` | `undisclosed` | `silent` | `classification-only` |
| `any` | `disclosed` | `explicit-direct-fix` | `direct-fix-once` |
| `confirmed-direct-fix` | `materially-changed` | `any` | `invalidated` |
| `confirmed-direct-fix` | `topology-mismatch` | `any` | `invalidated` |

`direct-fix-once` authorizes only the disclosed final-table batch. Any final-table content, topology, or scope change invalidates prior confirmation and requires a fresh disclosure and reconfirmation before any Direct Fix side effect. A mismatch between disclosed topology and artifact topology is a material change: block preflight, list the mismatch in the fallback reason inventory, and route to Review Dossier only after valid confirmation for that updated surface.

### Post-Confirmation Routing (Decision Gate)

After the user confirms the final table, evaluate the Consent State Matrix and check what kind of work is needed **before** generating the dossier. Direct Fix is available only for `direct-fix-once` and an eligible Section A batch matching the disclosed route. No second plan-approval step follows valid informed Direct Fix confirmation.

| Scenario | Section A | Section B | Action |
|----------|-----------|-----------|--------|
| Eligible Direct Fix batch with `direct-fix-once` consent | > 0 | any | Proceed to Step 4a (pre-write scan) → Dossier Accuracy Grill Gate → Direct Fix Brief → `execution.md` §Direct Fix Brief Handoff after brief verification. No second plan-approval step is required. Do not generate the full dossier. |
| Code changes needed by default, or direct-fix criteria fail | > 0 | any | Proceed to Step 4a (pre-write scan) → Step 4b (Dossier Accuracy Grill Gate) → Step 4c (dossier) → Step 4e (reply task contract) → Step 5 (handoff) |
| Replies only, no code changes | = 0 | > 0 | **Skip dossier.** State: "No code changes are needed. N comments need replies. I will post replies now and verify them by read-back." Then send replies per Direct Reply-Only Posting and Reply Policy (`dossier-output.md`). |
| Nothing actionable | = 0 | = 0 | **Skip dossier.** State: "All comments require no action. Nothing to do." End. |

**Direct-fix criteria**: use `dossier-output.md` §Direct Fix Brief for the exact complexity certificate, topology, caps, deterministic order, and fallback rules. Small PR fast-path consent does not count as Direct Fix consent.

If the Direct Fix preflight finds any failed eligibility condition, list every failed condition before routing to Review Dossier. Do not silently downgrade the route or omit failed conditions from the fallback record.

**Dossier Accuracy Grill Gate**: before either Direct Fix Brief or full dossier, ask only questions whose answers cannot be obtained from code, comment text, or prior user decisions. Use grill-me style: one question at a time, with a recommended answer. If the gate reveals ambiguity, conflict, cross-file scope, architecture choice, or unclear test/reply behavior, route to the normal dossier path. Do not invoke `grill-with-docs` by default; it is only appropriate when the PR comment requires domain glossary or ADR-style decision capture.

**Rationale**: The dossier feeds into an executor for plan-driven implementation. It's valuable for complex code changes, but a one-file low-risk task can be executed from a Direct Fix Brief as long as the reply policy and read-back verification are preserved. For reply-only or no-action scenarios, dossier generation is unnecessary overhead with no downstream benefit. The reply-only route is operational: post replies through the documented endpoints, then use read/list/get read-back verification. Do not verify by repeating a POST.

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
