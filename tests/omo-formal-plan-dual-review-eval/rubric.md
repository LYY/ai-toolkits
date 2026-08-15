# Formal Plan Dual Review Evaluation Rubric

Each applicable criterion is binary. A receipt records `true` only when an independent grader binds the producer response to the case's structured outcome and observations. Grader evidence explains every applicable criterion; a false receipt criterion additionally carries causal evidence describing missing or contradictory behavior. Criteria judge outcomes, not response wording.

| ID | Binary observable rule |
|---|---|
| `OMO-01` | A valid `BLOCKED` receipt identifies an eligible plan-level violation with criterion, location or reproduction, impact, causal evidence, smallest correction boundary, and closure assertion. |
| `OMO-02` | A zero-eligible `BLOCKED` receipt triggers exactly one same-lane, same-identity completion request rather than reconciliation or repair. |
| `OMO-03` | Completion produces either an eligible `BLOCKED` result or unconditional `APPROVED` with benign notes; unresolved completion invalidates the pair and follows bounded recovery. |
| `OMO-04` | Approval requires an unconditional verdict and notes that are neither conditional nor blocker-substantive. |
| `OMO-05` | A concrete D10 security, data-loss, compatibility, or external-contract risk remains eligible and is not erased by inflation controls. |
| `OMO-06` | Blocker admission independently establishes material contract impact and plan-level necessity; reproduction or a reviewer mechanism alone is insufficient. |
| `OMO-07` | Wording, extra examples, optional hardening, and executor recipes become non-blocking notes when no material violation is evidenced. |
| `OMO-08` | Closure rejects unchanged-root rediscovery unless repair causation, a newly verified unavailable fact, or concrete D10 risk makes it novel. |
| `OMO-09` | An admitted D10 repair keeps only the smallest invariant, fail-closed outcome, acceptance result, or QA property and excludes proposed executor machinery. |
| `OMO-10` | Budget or inflation escalation preserves unresolved eligible blockers, stops automatic edits, reports `INCONCLUSIVE`, and offers compact repair, separate scope expansion, or stop-and-simplify routes. |

## Receipt Contract

Schema v2 binds each receipt to one case, phase, prompt hash, source hash and byte count, raw response hash, distinct producer and grader context IDs, case-specific `observed_outcome`, and exact `observations` keys from the manifest. RED outcomes and false observations match the frozen baseline; GREEN uses the expected outcome and all observations are true.

Raw response is a compact JSON envelope stored at `{case_id}.response.md`: schema version, case ID, observed outcome, observations, and free-form non-empty narrative. Validator checks structured fields against receipt and manifest; narrative prose remains unconstrained.

Each receipt also binds `{case_id}.grader.json` by SHA-256. Grader output independently binds the same prompt, response, context, outcome, observations, and rubric. Its evidence keys exactly equal all applicable rubric IDs. Each evidence item has a free-form non-empty `summary` and non-empty `observation_ids`; IDs must belong to and collectively cover the case's required observations. Receipt `rubric` keys exactly equal `blocking_criteria`; values are booleans. Receipt `evidence` keys exactly equal false rubric IDs. This contract permits flexible producer and grader prose while preventing a rehashed generic response from inheriting an unrelated positive grade.
