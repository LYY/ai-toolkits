# Money and Ledger Invariants

Test monetary transformations and ledger postings against the target system's data model and source-backed business contract. Treat every amount, unit, asset, and reference-data choice as an observable part of the behavior under test.

## Use When

Use this guidance when a scenario creates, moves, reserves, settles, reverses, corrects, converts, applies fees, or reconciles monetary value. It applies to ledger entries, account buckets, balances, holdings, payment amounts, wallet value, instrument quantities with monetary valuation, and related reference data.

Start by identifying the project-defined representation and the boundary at which values are normalized, persisted, serialized, or converted. The representation may be decimal, a fixed-point integer, BigInt, or an equivalent type. Flag binary floating point only when it is used for monetary quantities; do not infer a defect from its use for unrelated measurements.

## Required Facts

Collect evidence from the target code, executable specification, fixtures, or authoritative project data before writing expected values. Record the source and version or effective date for each fact. Do not substitute a familiar finance convention for missing project evidence.

At minimum, establish:

- Monetary representation: type, signedness, unit, scale, precision, serialization form, and conversion boundaries.
- Rounding: operation that rounds, rounding mode, scale at which it occurs, whether intermediate values remain exact, and whether residuals are posted, carried, or rejected.
- Currency and asset identity: currency or asset for every amount, allowed pairs, minor-unit scale, and whether fee amounts may use a different asset.
- Fees: fee calculation base, timing, payer, beneficiary, asset, rounding, and treatment when the fee cannot be collected.
- FX: rate source, rate version or timestamp, quote direction, conversion scale, residual policy, and the project-defined behavior for an unallocated residual.
- Overflow and range: maximum and minimum representable values, multiplication and aggregation behavior, and the required outcome when a value exceeds that range.
- Reference data: currency, instrument, calendar, rate, and fee-rule identity together with effective date, version, and provenance requirements.

If any fact is absent, make the test expose that ambiguity rather than inventing a rounding mode, currency scale, fee asset, FX residual policy, or overflow policy. Keep expected values in the same representation and unit as the system boundary being asserted.

## Invariants and Oracles

Use an oracle that does not call the implementation's amount calculator, posting builder, conversion helper, or balance reducer. Build expected values from independent fixture data and explicit arithmetic in the test harness, then compare both final state and materialized trace.

Check these invariants independently:

- Balanced debits and credits: for each posting group and transaction boundary defined by the project, total debits equal total credits in the required asset and scale. If cross-asset balancing is supported, assert the project-defined conversion and residual representation rather than comparing unlike assets.
- Account bucket and asset conservation: opening value plus permitted inflows minus permitted outflows equals closing value for each account, bucket, and asset. Check available, held, pending, frozen, or equivalent buckets separately when the model distinguishes them; do not collapse buckets merely because their totals match.
- Reversal and correction trace: a reversal or correction references the original event or posting, preserves the original economic facts, applies the exact opposite or project-defined correcting effect, and leaves an auditable ordered trace. A correction must not silently rewrite the original amount or erase its provenance.
- Effective-date, version, and provenance validity: every currency, instrument, calendar, rate, and fee fact used by a calculation is the version effective for the event under the project contract, and its source identity is retained wherever the contract requires it. Test that a later reference-data version cannot silently change a historical result.
- Arithmetic boundaries: independently verify scale normalization, rounding residual, fee asset, FX residual, signed zero or sign handling where relevant, and overflow behavior at every operation that can change value.

For each invariant, assert the smallest relevant state and the resulting ledger trace. A passing balance total is insufficient if bucket conservation, asset identity, reversal linkage, or reference-data provenance is wrong. For rejected operations, assert no prohibited mutation and preserve the project-defined failure evidence.

## Test Scenarios

Use project fixtures and source-backed expected results for each applicable class. Vary amount sign, scale, asset, bucket, fee, rate, reference-data version, and event identity without assuming that all combinations are valid.

### Positive

- Post a valid single-asset transfer and verify balanced entries, per-account bucket conservation, asset identity, and persisted trace.
- Apply a valid fee in the configured fee asset and verify principal, fee, recipient, and residual outcomes independently.
- Execute a valid FX conversion with the project-defined rate and residual policy; verify both asset balances, scale, rate provenance, and any residual posting.
- Replay a valid correction or reversal according to the project contract and verify the original remains unchanged while the new trace balances.

### Boundary

- Use zero, smallest supported unit, largest supported value, maximum scale, and values exactly at rounding boundaries.
- Exercise sign changes, near-zero residuals, fee equal to or greater than the principal where the contract defines behavior, and bucket limits.
- Exercise multiplication, aggregation, and conversion values at the representable range boundary; verify the specified overflow result rather than relying on host-language wraparound or implicit widening.
- Use an effective-date boundary for currency, instrument, calendar, rate, or fee data and verify which version the event is entitled to use.

### Failure

- Supply malformed, unsupported, mismatched, or missing currency or asset identity; assert the project-defined rejection or quarantine and no prohibited postings.
- Trigger a non-balancing debit/credit set, insufficient bucket, invalid scale, unavailable fee asset, invalid FX pair, missing residual destination, or overflow condition; assert the specified failure state and trace.
- Supply reference data with missing version, provenance, effective date, or incompatible units; assert that calculation does not silently proceed with an unqualified value.
- Verify that a failed operation does not partially move value across accounts, buckets, or assets unless partial mutation is explicitly part of the contract and independently traceable.

### Duplicate and Correction

- Submit the same event or idempotency key twice and assert the project-defined result: one economic effect, a stable replay result, or an explicit duplicate failure. Check balances and trace count, not merely response text.
- Submit the same correction or reversal twice and verify it cannot double-apply. If repeated correction is allowed, assert the distinct correction identity and its exact effect.
- Correct an amount, fee, asset, or reference-data selection using the project-defined mechanism. Verify original and correcting entries, linked identifiers, conservation, and the resulting balance without deleting history.
- Reuse an event identity with changed monetary facts and assert the specified conflict or stale-write behavior.

### Stale Reference Data

- Run an event against currency, instrument, calendar, rate, or fee data whose version is older or newer than the event's effective date. Assert the project-defined accept, reject, quarantine, or recompute behavior.
- Change current reference data after a historical posting and verify that reading or replaying the historical event uses the recorded effective version and provenance.
- Omit or mismatch reference-data provenance while keeping numeric values equal; assert failure when provenance is required, because equal numbers do not prove equal source semantics.
- Repeat the stale-data case after a correction or reversal and verify that the correction follows the original event's applicable reference-data contract rather than silently using today's data.

## Completion Criteria

Consider the money or ledger test complete only when:

- The expected representation, currency, scale, rounding, fee asset, FX residual, overflow, and reference-data rules are evidenced by the target project or explicitly exposed as unresolved assumptions.
- Positive, boundary, failure, duplicate/correction, and stale-reference-data cases cover every applicable monetary path.
- Independent oracles verify balanced debits and credits, account bucket conservation, asset conservation, reversal/correction trace, and effective-date/version/provenance validity.
- Assertions inspect economic state and trace data, including no-prohibited-mutation behavior on failure, rather than only return codes or client call counts.
- Replays and corrections are checked for idempotency, linkage, conservation, and preservation of original history.
- The test does not encode unproven universal monetary policies or behavior outside the target project's contract.
