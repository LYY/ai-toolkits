# Risk, Credit, and Settlement

## Use When

Use this reference when code calculates positions, cost basis, PnL, mark or index prices, margin, liquidation, credit decisions, limits, utilization, clearing, netting, collateral, linked delivery and payment, partial settlement, settlement dates, cutoffs, calendars, or settlement instructions.

Expected values come from project code, specifications, contracts, or versioned project reference data. Missing price roles, model versions, or settlement calendars are expected-value blockers. Do not replace a missing fact with a market convention, a default threshold, or an inferred ordering.

This reference covers financial effects and business state. Keep transport, database, concurrency, security, observability, and statistical validation mechanics outside the oracle itself.

## Required Facts

Record the exact facts that determine each expected result.

### Risk and positions

- Instrument identity, account, side, signed quantity, unit, multiplier, transfers, and corporate-action treatment from the project model.
- Opening position, fills, fees, transfers, and corrections needed to derive quantity, cost basis, realized PnL, and unrealized PnL.
- Price role for each calculation, such as mark, index, last, or venue price, including precedence, effective time, freshness rule, and missing or conflicting input behavior.
- Margin formula, collateral scope, netting scope, maintenance threshold, liquidation trigger, liquidation ordering, and residual-balance treatment from project specifications.

### Credit

- Account or applicant identity, decision timestamp, input snapshot, external score snapshot, source identifiers, and effective dates.
- Rule-set version, model version, parameter or configuration version, feature values, reason codes, and decision output needed to replay the original result.
- Limit identity, currency or unit, exposure buckets, reserved amount, utilized amount, available amount, and the project-defined conservation relationship.
- Project-defined lifecycle states and transitions for delinquency, restructure, write-off, recovery, correction, and closure. Do not invent transitions that sources do not define.

### Clearing and settlement

- Obligation identity, source events, parties, asset leg, payment leg, quantities, units, currencies, and link or netting group.
- Netting scope, collateral or margin effect, residual obligation, partial-settlement unit, and treatment of failed, cancelled, corrected, or reversed legs.
- Scheduled date, cutoff instant, timezone, business-calendar identifier and version, and settlement-instruction identifier and version.
- Delivery-versus-payment, payment-versus-payment, and finality behavior only from target-system contracts. Do not infer whether one leg, both legs, or a linked group becomes final from terminology alone.

## Invariants and Oracles

Use project-sourced expected values and at least one independent observable oracle for each domain. An assertion that only repeats the system under test is not independent.

### Risk and positions

- Recompute position quantity from the recorded opening position, fills, transfers, and corrections using the project-defined sign and multiplier rules. Compare with the position service and with an independent position or event snapshot.
- Recompute cost basis and PnL from the recorded position facts and the source-defined price role. A missing or ambiguous mark, index, last, or venue role blocks expected-value generation.
- Assert margin monotonicity only when the project formula proves it for the tested position, netting, collateral, and price domain. Otherwise assert the formula result, not a presumed direction.
- Verify liquidation ordering against a source-defined priority fixture. Reconcile every released, consumed, or residual balance with an independent collateral or account snapshot.
- For duplicate, reordered, or concurrent inputs, compare economic effects and final position facts with the independently recomputed event set. Do not rely only on call counts or internal flags.

### Credit

- Replay a decision with the original input snapshot, rule-set version, model version, parameter version, external-score snapshot, and effective dates. The replay oracle is the persisted decision and reason-code record, compared with an independent recomputation from those frozen artifacts.
- Verify the project-defined limit identity, such as available plus utilized plus reserved equaling the limit. Derive each term from independent exposure and reservation facts, then compare with the credit state.
- Test threshold boundaries using source-defined values. A missing rule, model version, feature value, score snapshot, or threshold blocks expected-value generation.
- For version drift, replay the historical decision with historical artifacts, then evaluate the new version as a separate decision with explicit lineage. Do not silently overwrite the historical result.
- Verify lifecycle transitions against project-defined state records and effective events. Independent evidence can be the decision journal, exposure snapshot, account state, or recovery record, provided it is not the same calculated field being asserted.

### Clearing and settlement

- Recompute obligations from source trade or payment facts within the project-defined netting scope. Compare gross legs, net obligations, collateral effects, and residuals with independent obligation and balance records.
- Treat linked delivery and payment legs as one contract-defined business outcome. DvP, PvP, and finality semantics come from target contracts only. The oracle must observe both legs, their link identifier, and the resulting linked-group state.
- For partial settlement, verify settled quantity, remaining quantity, collateral or margin release, and payment amount independently for each leg. A settled leg must not imply completion of its linked group unless the contract says so.
- Derive settlement date and cutoff behavior from the versioned project calendar, timezone, and settlement instructions. Independently recompute the date around a holiday, cutoff boundary, and timezone boundary, then compare with the scheduled obligation.
- Preserve obligation lineage through correction or cancellation. Compare original, corrected, cancelled, settled, and residual records with an independent event or obligation view. Do not create a second economic obligation for a correction.

## Test Scenarios

Build scenarios from project facts, and select only branches supported by those facts.

### Risk and positions

- Happy path: long and short positions apply the project-defined price roles, cost basis, PnL, margin, and residual balance rules.
- Boundary path: zero quantity, partial fill, sign change, threshold equality, stale price boundary, and collateral exhaustion where the project defines each boundary.
- Failure path: missing, stale, conflicting, or role-ambiguous price input blocks expected liquidation or PnL values and records the missing source fact.
- Duplicate and ordering path: duplicate fill, reordered fill, price update during liquidation, and close or liquidation racing with a correction. Verify one business effect per accepted event according to the project contract.
- Correction path: corrected fill, repricing, or liquidation reversal updates quantity, cost basis, PnL, margin, and residual balances without losing original lineage.

### Credit

- Happy path: a frozen input and artifact bundle reproduces the recorded decision, reason codes, utilization, and lifecycle state.
- Boundary path: exact limit, exact threshold, zero utilization, full reservation, expired input, and score or feature effective-time boundaries when specified.
- Failure path: missing input snapshot, rule version, model version, parameter version, or external-score snapshot blocks the expected decision instead of using current values.
- Replay and ordering path: duplicate decision request, reordered score or document events, and replay after rule or model drift preserve historical lineage and distinguish old from new decisions.
- Lifecycle path: delinquency, restructure, write-off, recovery, correction, and closure follow only the transitions and balance effects present in project sources.

### Clearing and settlement

- Happy path: linked delivery and payment legs use the project calendar, cutoff, settlement instructions, netting scope, and contract-defined finality behavior.
- Boundary path: partial quantity, zero residual, holiday crossing, cutoff equality, timezone boundary, collateral release threshold, and settlement-instruction version boundary.
- Failure path: missing calendar, missing settlement instructions, broken leg link, conflicting netting scope, or unavailable collateral blocks expected scheduling or completion.
- Duplicate and ordering path: duplicate leg event, delivery before payment, payment before delivery, late correction, and settlement request racing with cancellation preserve linked-group semantics.
- Correction path: cancel or correct a partially settled obligation and verify original facts, settled portions, residual portions, collateral, payment, and lineage remain consistent.

## Completion Criteria

- Every expected quantity, price, PnL, margin, decision, limit, utilization, obligation, date, cutoff, calendar result, and settlement-instruction choice names its project code, specification, contract, or versioned reference-data source.
- Missing price role, model version, or settlement calendar is recorded as an expected-value blocker. No guessed default is used to make the scenario appear complete.
- Risk, credit, and settlement each have an independent observable oracle with frozen inputs and a separately derived expected result.
- Assertions cover business effects, including position and residual conservation, reproducible decisions and limit utilization, obligation and netting effects, collateral, linked legs, partial settlement, correction, cancellation, calendar use, and settlement instructions.
- Happy, boundary, failure, duplicate or replay, ordering or concurrency, and correction paths are present only where project facts make them applicable.
- Margin direction, liquidation order, credit thresholds, lifecycle transitions, netting, calendar rules, DvP, PvP, and finality are never treated as universal behavior. Target-system contracts and project reference data decide them.
