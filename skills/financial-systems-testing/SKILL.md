---
name: financial-systems-testing
description: Use when testing code involving money, balances, ledger postings, trading orders or positions, payments or wallets, credit or risk, clearing or settlement, reconciliation, or finance reference data.
---

# Financial Systems Testing

Test financial behavior from target-project facts. Keep expected values blocked when source facts are absent; do not supply familiar financial conventions.

## Modes

- **Test-first**: route generic test-first practice to `tdd`; this skill owns financial facts and oracles.
- **Tests-after**: this skill owns finance oracle design, then fit it to target-project test conventions.
- **Audit**: route generic test-quality review to `codeprobe-testing`; retain only financial invariants and scenarios here.
- **Debug**: route the mechanical failure to the relevant `debugging` or test owner after classifying financial semantics.

## Workflow

1. **Classify**: identify money, ledger, lifecycle, risk, settlement, reconciliation, or reference-data touchpoints. Route non-financial mechanics to their owner.
2. **Ground**: name the target code, specification or contract, fixture, and authoritative data source for each expected value. If any source is unavailable, name that missing source as a blocker rather than inferring a value.
3. **Route**: load only reference guidance matching the detected touchpoint.
4. **Model**: state the invariant and an independent observable oracle. Record missing source facts as blockers.
5. **Execute**: select applicable happy, failure, duplicate or replay, ordering or concurrency, and correction cases. State evidence-backed `not applicable` for any category the target facts do not support. Route generic test mechanics to `tdd` without duplicating its tutorial.
6. **Prove**: assert business state and retained evidence, not only implementation calls or response status.

For non-financial requests, do not load finance references: generic CRUD stays with target-project testing conventions, concurrency routes to `golang-concurrency`, security-only behavior routes to `golang-security`, and jurisdictional compliance interpretation is out of scope.

## On-Demand Loading

Load one or more entries below only after classification. `SKILL.md` points into these references; references do not route back or sideways.

| Runtime reference | Load only when |
|---|---|
| `money-ledger-invariants.md` | Money representation, balances, ledger postings, fees, FX, buckets, or finance reference-data versions affect behavior. |
| `transaction-lifecycles.md` | Trading orders or positions, payments, wallets, holds, idempotency, unknown outcomes, or corrections define a lifecycle. |
| `risk-credit-settlement.md` | Risk, credit, margin, liquidation, limits, clearing, linked settlement legs, calendars, or settlement instructions affect results. |
| `resilience-reconciliation.md` | Delivery multiplicity, replay, recovery, unknown outcomes, reconciliation breaks, or correction lineage affect financial effects. |

## Public-Skill Routing

For generic mechanics, preserve the named owner above. When a public skill is unavailable, follow target project conventions, implement only the finance oracle, and omit generic tutorial content.

## Completion Criterion

Complete only when every detected financial touchpoint maps to source plus invariant or oracle plus applicable cases, or evidence-backed `not applicable`.
