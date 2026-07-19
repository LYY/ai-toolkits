# Financial Systems Testing Evaluation Matrix

This matrix freezes behavioral evaluation inputs for the `financial-systems-testing` skill. It is maintainer documentation, not runtime guidance.

| Case ID | Input facts | Applicable reference | Expected route | Blocking rubric IDs | Explicit non-goals |
|---|---|---|---|---|---|
| `money-rounding-source-missing` | Multi-currency wallet has an unspecified rounding rule. | `money-ledger-invariants` | `financial-systems-testing` | FSE-01, FSE-02, FSE-03, FSE-04, FSE-05, FSE-06, FSE-07, FSE-08 | Do not invent a rounding mode or library. |
| `ledger-transfer-conservation` | Transfer moves funds across available and pending buckets. | `money-ledger-invariants` | `financial-systems-testing` | FSE-01, FSE-02, FSE-03, FSE-04, FSE-05, FSE-06, FSE-07, FSE-08 | Do not prescribe accounting standards or database APIs. |
| `trade-partial-fill-cancel-race` | Order fills can arrive while cancellation is requested. | `transaction-lifecycles` | `financial-systems-testing` | FSE-01, FSE-02, FSE-03, FSE-04, FSE-05, FSE-06, FSE-07, FSE-08 | Do not choose a transport framework. |
| `payment-timeout-unknown-outcome` | Provider timeout follows a payment request. | `transaction-lifecycles` | `financial-systems-testing` | FSE-01, FSE-02, FSE-03, FSE-04, FSE-05, FSE-06, FSE-07, FSE-08 | Do not promise retry behavior without evidence. |
| `wallet-freeze-reversal` | Frozen funds are later reversed after correction. | `transaction-lifecycles` | `financial-systems-testing` | FSE-01, FSE-02, FSE-03, FSE-04, FSE-05, FSE-06, FSE-07, FSE-08 | Do not assume balance-bucket meanings. |
| `risk-liquidation-price-source` | Margin liquidation consumes multiple price feeds. | `risk-credit-settlement` | `financial-systems-testing` | FSE-01, FSE-02, FSE-03, FSE-04, FSE-05, FSE-06, FSE-07, FSE-08 | Do not define a universal liquidation policy. |
| `credit-decision-replay` | Credit approval must be replayable after rule changes. | `risk-credit-settlement` | `financial-systems-testing` | FSE-01, FSE-02, FSE-03, FSE-04, FSE-05, FSE-06, FSE-07, FSE-08 | Do not infer underwriting thresholds. |
| `settlement-partial-dvp-calendar` | Linked delivery and payment legs settle partially around a business date. | `risk-credit-settlement` | `financial-systems-testing` | FSE-01, FSE-02, FSE-03, FSE-04, FSE-05, FSE-06, FSE-07, FSE-08 | Do not encode a market calendar. |
| `reconciliation-break-correction` | Two systems disagree after a correction event. | `resilience-reconciliation` | `financial-systems-testing` | FSE-01, FSE-02, FSE-03, FSE-04, FSE-05, FSE-06, FSE-07, FSE-08 | Do not prescribe observability tooling. |
| `reference-data-effective-date` | Instrument data changes by effective date and version. | `money-ledger-invariants` | `financial-systems-testing` | FSE-01, FSE-02, FSE-03, FSE-04, FSE-05, FSE-06, FSE-07, FSE-08 | Do not infer a data vendor or date convention. |
| `generic-crud-tests` | Profile CRUD has no monetary or financial state. | none | `not-applicable` | FSE-01, FSE-02, FSE-06, FSE-08 | Do not load finance guidance. |
| `generic-concurrency-test` | In-memory work queue has a concurrent dequeue race. | none | `golang-concurrency` | FSE-01, FSE-02, FSE-06, FSE-08 | Do not create a finance test plan. |
| `security-only-payment-api` | Payment-branded API only verifies signed requests and authorization. | none | `golang-security` | FSE-01, FSE-02, FSE-06, FSE-08 | Do not infer money semantics from the endpoint name. |
| `compliance-only-request` | Request asks for jurisdictional payment compliance interpretation. | none | `out-of-scope-compliance` | FSE-01, FSE-06, FSE-07, FSE-08 | Do not interpret law, regulation, or compliance controls. |

## Grouping

Positive-domain groups are `money-ledger`, `transaction-lifecycle`, `risk-settlement`, and `resilience-reference`. Negative routes are `generic`, `security`, and `compliance`. RED validation requires a branch-level miss in every positive-domain group and at least one routing or compliance miss across negative routes.
