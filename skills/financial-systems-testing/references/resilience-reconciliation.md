# Resilience and Reconciliation

## Use When

Use this reference when a financial workflow can be delivered more than once, delivered in a different order, interrupted at a boundary, corrected after an apparent success, or compared across systems. Typical signals include payment or trade requests with retries, provider timeouts, replayed messages, missing sequence ranges, journal recovery, reversal events, ledger breaks, processor files, counterpart reports, or a correction that must not be applied twice.

Keep two questions separate:

- Delivery semantics ask whether an event, command, or report may arrive zero, one, or many times and whether ordering is guaranteed.
- Business-effect semantics ask what monetary, position, obligation, or status effect may exist after those deliveries.

Duplicate delivery can be valid. Duplicate monetary effect cannot be assumed valid. A test must prove the allowed delivery behavior and the single business effect independently.

Lock, channel, transaction, and logging mechanics are implementation concerns outside this reference. Assert finance behavior and retained evidence here. Keep generic implementation routing in the owning workflow rather than turning this reference into a concurrency, database, or observability tutorial.

## Required Facts

Before creating expected values, record facts that identify the event, its intended effect, and the evidence available after failure. Missing facts block an expected-value oracle rather than permitting a guessed default.

### Delivery and effect identity

- Command or event type, schema version, producer, and source sequence or replay position.
- Idempotency key, its scope, and the business effect it names. State whether scope is account, order, payment, settlement instruction, correction, or another project-defined boundary.
- Stable business key shared by the systems under comparison. Do not substitute a transport message ID when one business action can produce several messages.
- Amount, asset, account or position, fee, FX context, and effective business time where those facts affect the effect.
- Expected state transition and whether the event is an intent, an acceptance, a reservation, a posting, a settlement result, a correction, or a reversal.

### Ordering and recovery facts

- Ordering contract, sequence domain, duplicate policy, and whether gaps block application, permit buffering, or require a snapshot.
- Retry classification for the operation: retryable before acceptance, retryable after a confirmed no-op, non-retryable business rejection, or unknown outcome requiring read-back or reconciliation.
- Snapshot identifier, snapshot cut, journal range, and version or configuration inputs used for replay.
- Crash boundary under test, such as before delivery, after durable acceptance, after the business effect, or after the response became unknown.
- Correction or reversal lineage, including the original event key, correction key, reason, effective time, and whether the correction replaces, offsets, or supplements the original effect.

### Reconciliation facts

- Source systems: internal ledger, business subsystem, and external counterpart or processor. Record which source is authoritative for each fact, not only which source has the final balance.
- Event-level economic facts from each source, including action, amount, asset, account or instrument, status, business time, settlement date, fee, and correction or reversal relation.
- Stable join keys and any documented mapping between source identifiers. A row count, file position, or generated request ID is not a stable key unless the project contract says it is.
- Tolerance source and units. Identify the project-defined amount, quantity, timing, or status tolerance, including whether it applies per event, per account, or only to an explicitly aggregated view.
- Break owner and correction owner. The source that detects a break need not own the correction, and a correction must name the system authorized to issue it.
- Project-defined aging thresholds, escalation states, rerun scope, and retention requirements. If the project defines none, test detection and classification without inventing an age or escalation deadline.

## Invariants and Oracles

Use independent business oracles. A response code, a handler return value, a client call count, or a final balance by itself does not prove a financial effect.

### Delivery versus effect

For each idempotency scope, construct a delivery sequence such as original, duplicate, retry, delayed duplicate, and correction. The oracle checks that:

1. Every accepted delivery has an observable decision, such as applied, ignored as duplicate, rejected, buffered, or held for reconciliation.
2. Repeated delivery of the same business action does not create a second monetary, quantity, fee, reserve, or position effect.
3. A distinct correction key can create its intended offset or replacement effect without being mistaken for a duplicate of the original action.
4. A duplicate response or duplicate event has the same business result and lineage as the first accepted effect, or has the project-defined duplicate disposition.

The key is scoped to the business action. Reusing one key for two valid actions must either be rejected or produce the project-defined conflict result. Reusing a key across accounts, orders, or correction lineages is not automatically safe.

### Retry and unknown outcome

Classify retries from observed state, not from elapsed time alone. A retry after a known business rejection must not become an accepted effect. A retry after a confirmed no-op may be allowed. A timeout after the request may have been accepted is an unknown outcome, not proof of failure.

The oracle for an unknown outcome is a read-back or reconciliation result that identifies the original business key, current effect, and lineage. The test must cover both branches: the original effect exists and the original effect does not exist. Only then can it assert whether retry, recovery, or manual correction is valid.

### Ordering, gaps, and replay

Out-of-order delivery must follow the project contract. The oracle distinguishes applied, buffered, rejected, and gap-blocked decisions. It does not infer business order from wall-clock arrival time.

Replay uses a named snapshot plus an ordered journal suffix. Record every intermediate decision and event that is observable, not only the final state. Compare:

- snapshot identity and cut position;
- journal sequence, event key, event type, and correction lineage;
- each apply, ignore, buffer, reject, gap, and correction decision;
- intermediate balances, reservations, positions, obligations, or statuses when the project exposes them;
- final state and retained event evidence.

The replay oracle passes only when the same snapshot, journal bytes or equivalent event facts, versioned rules, and reference inputs produce the same intermediate decisions and final state. A final-state match with a different decision path is a replay discrepancy when intermediate decisions are observable or affect later corrections.

### Crash boundaries and corrections

Place failures at each project-defined boundary and assert the permitted recovery state:

- before the action is accepted;
- after acceptance but before the effect is visible;
- after the effect is applied but before the response is known;
- after a correction is accepted but before its effect is visible;
- after the correction is visible but before the recovery response is known.

Every correction or reversal must point to the original business event, carry its own key, and state whether it offsets, replaces, or supplements the original. The oracle rejects an unlinked correction, a correction applied twice, or a correction that silently rewrites retained original evidence. It also checks that a replay after the crash preserves the same lineage and does not turn an unknown outcome into an invented failure.

### Reconciliation oracle

Reconcile event-level economic facts across the internal ledger, business subsystem, and external counterpart. Compare the event set, stable keys, effect values, statuses, business times, and correction lineage before comparing balances. Equal balances can hide a missing debit and credit, a duplicated event offset by another error, an omitted fee, or a correction applied to the wrong account.

For each joined business event, classify the result using project-defined categories such as matched, missing from one source, duplicate, conflicting amount or asset, conflicting status, ordering gap, late event, or correction lineage break. Keep unmatched facts from every source. A break is not resolved merely because an aggregate total later agrees.

Tolerance comes from the project specification or source configuration. Apply it at the documented scope and preserve the raw values used for comparison. Never choose a universal amount, quantity, or time tolerance for convenience.

### Break lifecycle

The lifecycle oracle checks detection, classification, project-defined aging and escalation, correction ownership, correction application, rerun scope, and retained original evidence. It should show which source facts created the break, who owns the next correction, what changed, and why the rerun is safe.

If the project defines aging or escalation states, test their boundaries and transitions. If it does not, do not invent a deadline, priority, or escalation policy. A rerun must be scoped by stable business key or explicit break set, must preserve the original comparison inputs and result, and must distinguish a new correction from a repeated correction. The corrected result must be linked to the original break and remain reproducible from retained evidence.

## Test Scenarios

Build one scenario from project facts, then vary one delivery or business condition at a time. Record intermediate decisions and event facts in the test result when the system exposes them.

### Replay matrix

Cover the applicable rows:

| Variation | Required observation |
|---|---|
| First delivery | Accepted decision, business key, effect, and lineage |
| Exact duplicate | Duplicate disposition and unchanged economic effect |
| Same key with conflicting facts | Project-defined conflict or rejection, with no silent overwrite |
| Retry after known rejection | No effect unless the contract explicitly permits a new action |
| Timeout with accepted original | Unknown outcome resolved by read-back or reconciliation, not blind retry |
| Timeout with no original effect | Project-defined retry or recovery path, with one eventual effect |
| Out-of-order event | Applied, buffered, rejected, or gap decision from the ordering contract |
| Missing sequence range | Gap handling, recovery input, and no invented event |
| Snapshot plus journal replay | Same intermediate decisions and final state from same inputs |
| Crash at each defined boundary | Recovery state, duplicate protection, and retained lineage |
| Correction or reversal | Original link, separate correction key, one intended offset or replacement |

### Reconciliation matrix

For an internal ledger, business subsystem, and counterpart report, cover:

- all three sources contain the same event facts;
- one source is missing an event;
- one source contains a duplicate;
- amount, asset, fee, account, instrument, or status conflicts;
- events arrive out of order or after the comparison cut;
- a correction exists in one source only;
- a correction exists in all sources but links to different originals;
- balances agree while event facts disagree;
- a difference is inside the project-defined tolerance;
- a difference is outside tolerance;
- a rerun repeats the same break set after correction;
- a rerun is narrowed to one stable key while unrelated breaks remain unchanged.

For every case, assert source attribution, stable key selection, tolerance source, break classification, correction ownership, original evidence retention, and the post-correction rerun result. When project-defined aging exists, include just-before, at, and just-after boundary cases. When it does not exist, record that aging and escalation are not applicable rather than inventing them.

## Completion Criteria

The test strategy is complete when every applicable touchpoint has all of the following:

- delivery semantics and business-effect semantics stated separately;
- idempotency key and scope grounded in project facts;
- retry classification and unknown-outcome resolution defined without treating timeout as failure;
- ordering, gap, snapshot, journal, correction, and crash behavior covered where the contract exposes them;
- intermediate replay decisions and events compared with the final state when observable;
- reconciliation sources, event-level economic facts, stable business keys, and source ownership identified;
- tolerance and any aging or escalation rule taken from project-defined sources;
- break detection, classification, correction, rerun, and original evidence retention independently observable;
- correction ownership and lineage tested so one correction cannot be silently replayed;
- implementation mechanics such as locks, channels, transactions, and logging kept outside this finance oracle.

If a required source fact, key mapping, tolerance, ordering contract, correction rule, or recovery boundary is absent, mark expected values as blocked and state exactly which project decision is needed. Do not replace the missing contract with a generic retry policy, aggregate-balance check, wall-clock ordering rule, or implementation assertion.
