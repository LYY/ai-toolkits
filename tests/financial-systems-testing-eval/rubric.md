# Financial Systems Testing Evaluation Rubric

Each applicable criterion is binary. A receipt records `true` only when the response contains the observable evidence named below. A `false` criterion requires a concise evidence string identifying the missing or contradictory behavior.

| ID | Binary observable rule |
|---|---|
| FSE-01 | Response invokes financial guidance only for financial semantics; negative cases route to the named owner or state that the request is out of scope. |
| FSE-02 | Response identifies every applicable financial domain from the case facts and does not add an unrelated finance domain. |
| FSE-03 | Response names a project code, specification, or authoritative data source for each expected value; absent rules remain blockers. |
| FSE-04 | Response states at least one independent observable oracle, not merely an implementation assertion. |
| FSE-05 | Response selects applicable happy, failure, duplicate or replay, ordering or concurrency, and correction paths without adding irrelevant paths. |
| FSE-06 | Response names the applicable public skill owner when generic mechanics are requested and does not duplicate that skill's tutorial. |
| FSE-07 | Response refuses jurisdictional or compliance interpretation and does not state compliance requirements as facts. |
| FSE-08 | Response accounts for every detected financial touchpoint or supplies evidence-backed `not applicable`. |

## Receipt Contract

`rubric` is an object whose keys exactly equal the manifest case's `blocking_criteria`; every value is a boolean. `evidence` is an object keyed by each false rubric ID with a non-empty string. A GREEN receipt has every blocking criterion true. A RED receipt records observed misses; the phase validator aggregates the branch-level miss requirements from the frozen manifest.
