## Use When

Use this reference when a system creates, changes, settles, reverses, or corrects a trading, payment, wallet, or stored-value transaction.

Model every lifecycle in two dimensions:

- An **event** is an observed fact, such as an execution report, cancellation acknowledgement, provider webhook, hold, release, or correction. An event is immutable after recording.
- A **state** is the current business interpretation derived from accepted events. State changes only through transitions allowed by the project code, specification, or authoritative event contract.

Do not infer legal transitions from enum names, client responses, transport order, or wall-clock timestamps. Require project evidence for the transition graph, terminal states, reopen or correction rules, sequence semantics, and idempotency-key scope. A missing rule blocks expected-value generation and should be reported as an evidence gap.

Assertions must check business effects. A test that only verifies a handler call, HTTP status, provider-library method, or message count is not a lifecycle oracle.

## Required Facts

Collect these facts before writing expected results:

- The event schema, event identity, aggregate identity, source, sequence or version field, and replay behavior.
- The project-defined legal and illegal transition graph, including terminal states, cancellation races, partial outcomes, correction states, and whether a terminal record can be amended only by a linked compensating event.
- The idempotency key, duplicate-detection key, deduplication retention, and whether deduplication is scoped to an order, payment, wallet, device, account, or event source.
- The commit boundary and partial-failure behavior. Identify which effects are atomic, which may be pending, and how an unknown result is resolved.
- The authoritative quantity, amount, fee, position, balance-bucket, and currency representations. Preserve source-defined scale, rounding, and sign rules.
- For trading, order quantity, cumulative execution quantity, leaves quantity, cancellation quantity, reject reason, fee asset, fee amount, and position effect.
- For payments, accepted, reserved, settled, rejected, returned, and recalled meanings, provider reference, idempotency key, timeout behavior, refund or reversal lineage, and whether a refund is separate from a returned payment.
- For wallets or stored value, available, frozen, and pending bucket meanings, account ownership, issuance or redemption rules, hold and release semantics, reversal lineage, and device or source event identity.

The project sequence or version is the ordering authority. If no sequence, version, or equivalent replay rule is documented, do not substitute `created_at`, delivery time, callback time, or local receipt time. Keep the outcome unresolved until an authoritative read or reconciliation rule decides it.

## Invariants and Oracles

Use at least one independent oracle for each lifecycle. Derive expected values from the required project facts, then compare the result to a separately computed ledger, quantity, state, or lineage view.

- **Transition oracle:** every accepted event has one project-defined predecessor state and one legal successor interpretation. Illegal edges fail without applying business effects. A correction is a new linked event, not mutation of the original event. Duplicate delivery produces no second effect, while a distinct correction may produce the documented compensating effect.
- **Replay oracle:** applying the same accepted event stream in project sequence or version order produces the same state, quantities, balances, fees, and lineage on every replay. Out-of-order events are buffered, rejected, or marked as gaps according to project evidence. Wall-clock order is never an implicit replay rule.
- **Trading quantity oracle:** assert the project-defined conservation equation across original order quantity, cumulative execution quantity, leaves quantity, canceled quantity, and rejected quantity. Do not assume whether canceled quantity is included in leaves or cumulative fields. For every accepted execution, verify one execution effect on position, cash or inventory, and fee totals. A duplicate execution report must not increase filled quantity, position, fee, or settlement obligation.
- **Trading transition oracle:** test order, replace, cancel, partial fill, fill, and reject as separate event types and states where the project distinguishes them. A cancel acknowledgement does not erase an execution that is legally sequenced before or concurrently with cancellation. The final state and remaining quantity must follow the project race rule, with no negative leaves quantity or overfill.
- **Payment amount oracle:** reconcile the authorized or accepted amount, reserved amount, settled amount, returned amount, recalled amount, refund amount, reversal amount, and fees using the project-defined signs and currencies. One idempotency key must not create multiple business charges, reservations, refunds, or reversals. A retry after an unknown provider outcome must first resolve the original operation or use the documented status query path.
- **Payment state oracle:** accepted, reserved, settled, rejected, returned, and recalled events must produce only project-defined transitions. A provider timeout is an unknown outcome, not proof of rejection and not proof of success. A later settled or rejected event resolves that uncertainty. Refunds and reversals must link to the original payment and must not silently create an unrelated charge or negative balance.
- **Wallet bucket oracle:** compute the balance relationship among available, frozen, and pending buckets using the project-defined conservation rule. Holds move only the documented amount into frozen or pending. Release restores the documented bucket. Issuance and redemption change the total only when the project says they do, and every change has an event and lineage. A duplicate freeze, release, issuance, redemption, or device event must not repeat the balance effect.
- **Wallet correction oracle:** a reversal or correction records its source event, applies the project-defined compensating movement exactly once, and preserves the original event for audit and replay. A repeated correction is a duplicate. A correction arriving before its source is handled as a gap, pending event, or documented rejection, never as an unrelated balance mutation.
- **Partial-failure oracle:** when persistence, downstream posting, or event delivery fails after one business effect but before another, the resulting state must match the documented commit boundary. Recovery must either complete the missing effect exactly once or record an unresolved state that blocks a second effect. Assert final balances, quantities, fees, positions, and obligations, not just retry counts.

## Test Scenarios

Build scenarios from the project transition graph. For every applicable case, record input event identity, project sequence or version, expected state, expected business effects, and correction or reconciliation evidence.

- **Legal transitions:** cover the documented happy path for each lifecycle. Trading should include order, replace, partial fill, fill, and cancel or reject paths as supported. Payments should include accepted, reserved, settled, rejected, returned, and recalled paths as supported. Wallets should include issuance, hold, release, redemption, and reversal paths as supported.
- **Illegal transitions:** send an event from an invalid predecessor, repeat a terminal transition when forbidden, overfill an order, settle a rejected payment, refund a payment without a settled source, release a nonexistent hold, or reverse an event twice. Assert rejection or quarantine and prove no monetary, quantity, position, fee, or bucket effect was applied.
- **Duplicate delivery:** deliver the same execution report, provider webhook, freeze event, payment request, refund request, or device event more than once using the project duplicate key. Assert one business effect, one lineage record where specified, and unchanged state after replay.
- **Out-of-order delivery:** deliver a fill before the order event, a settled webhook before accepted or reserved state, a release before a hold, or a correction before its source. Use project sequence or version semantics to assert buffering, gap marking, rejection, or later application. Do not order events by arrival timestamp.
- **Partial fill and cancel race:** send a partial execution while cancellation is in flight, then vary the project-defined sequence of execution and cancellation acknowledgement. Assert cumulative and leaves quantities, final order state, position, fees, and any settlement obligation. A duplicate execution after cancel acknowledgement must not add another fill.
- **Payment unknown outcome:** make the provider timeout after receipt of a request, then replay the same idempotency key and deliver settled, rejected, returned, recalled, refund, and reversal events in supported orders. Assert that the timeout remains unresolved until authoritative evidence arrives, and that only one charge or compensating effect is recorded.
- **Wallet hold and correction:** freeze funds, repeat the freeze, release the hold, reverse the hold, and deliver correction events before and after the source event. Assert available, frozen, and pending balances, total stored value, source linkage, and one application of every distinct event.
- **Partial failure and recovery:** fail after reservation but before settlement, after a fill but before position posting, or after a bucket movement but before durable event recording. Resume using the documented recovery or reconciliation path. Assert no lost or duplicated business effect and a deterministic final replay.
- **Correction:** apply a documented fee correction, execution correction, payment reversal, refund, wallet release correction, or balance adjustment. Assert immutable source preservation, linked compensating event, exact net business effect, and idempotent reapplication. If correction rules are absent, mark expected results blocked.

## Completion Criteria

A lifecycle test strategy is complete only when:

- Project code, specification, or authoritative data evidence supports every expected transition, status meaning, amount, quantity, bucket movement, fee, and correction result.
- Event records and current state are asserted separately, including source identity, sequence or version, duplicate status, and correction lineage.
- Legal, illegal, duplicate, out-of-order, partial-failure, and correction scenarios are covered for each applicable trading, payment, and wallet lifecycle.
- Independent business-effect oracles verify quantity, amount, fee, position, obligation, and balance-bucket outcomes. Client call counts and protocol-library syntax are not the only evidence.
- Replay uses project sequence or idempotency semantics and does not rely on wall-clock ordering.
- Unknown outcomes remain explicit until resolved by authoritative evidence, and recovery cannot create a second business effect.
- Missing transition, sequence, idempotency, representation, or correction rules are reported as blockers rather than filled with assumed behavior.
