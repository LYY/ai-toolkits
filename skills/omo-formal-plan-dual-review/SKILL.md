---
name: omo-formal-plan-dual-review
description: Use ONLY when user requests Momus + Oracle double review, dual review, or automatic repair of current formal ulw-plan. Reviews and minimally repairs only current .omo formal plan until both reviewers unconditionally approve same plan digest.
---

# Formal Plan Dual Review

Run this protocol only for explicit requests to double-review current formal
plan. Treat this skill as binding. Do not invoke it for implementation review,
product code review, or an inline plan.

## Authority And Scope

Target is current run's complete formal plan. Identify it from current request
and session context, including any plan created, approved, or explicitly named
in this session. If context cannot identify one readable formal plan, ask user
for target path; report `INCONCLUSIVE` only when interaction is unavailable.

Allowed reads: current project source, tests, scripts, rules, and current
formal plan, solely to verify plan claims. Allowed write: current formal plan
only, solely to resolve eligible blockers. Do not modify product source,
configuration, tests, tasks, branches, worktrees, commits, PRs, issues, or
remote resources. Do not run implementation, product tests, product QA,
publishing, deployment, or `/start-work`.

Formal plan is delivery intent. Receipts, blocker ledgers, reconciliation
records, and recovery diagnostics are workflow evidence: emit them in review
output, never in the formal plan. Plan-only write authority never permits
workflow evidence to be copied into the plan.

## Frozen Review Round

Every review epoch begins with one discovery round. Each later round is a
closure round for that epoch.

For every round:

1. Read raw live plan bytes. Record SHA-256 digest, exact byte count, and a
   unique round identity. No newline normalization or regenerated copy.
2. Freeze that byte sequence as only review target for this round.
3. Run exactly two independent review lanes: one `momus`, one `oracle`. Give
   both same frozen digest, byte count, round identity, and frozen content.
   They may inspect permitted repository facts, but must not edit anything.
4. Until both lanes reach terminal outcomes, never relay, summarize, or share
   findings, verdicts, or proposed repairs between lanes. Do not start a third
   reviewer.
5. Discovery lanes audit D01-D10. Closure lanes audit accepted blocker closure,
   repair regressions, and admissible novel blockers. Each lane returns evidence
   bound to frozen target plus an unconditional `APPROVED` or `BLOCKED` verdict.
   Every eligible blocker must include its ID, violated criterion, exact location
   or reproduction, impact, causal evidence, minimal correction boundary, and
   closure assertion. Treat a finding missing one of those fields as a
   non-blocking note.
6. After a valid discovery pair, reconcile candidates and freeze an accepted
   blocker ledger: ID, root cause, correction boundary, and closure assertion.
   Later rounds must not rediscover unchanged plan content. They may admit only
   a repair-caused regression, a fact unavailable to discovery and now verified,
   or a concrete D10 risk that makes continuation unsafe. A novel blocker must
   state why discovery could not have found it; otherwise record a non-blocking
   note.
7. Set a finite deadline for each lane. A matching receipt with a clear verdict
   but incomplete coverage receives one receipt-only completion request to the
   same lane and same digest; it must not reopen content review or modify plan.
   Transport failure, mismatched identity, absent or conditional verdict, or an
   unresponsive completion request invalidates the pair. Do not reconcile or
   repair from an invalid pair. Start at most one fresh recovery round with two
   new lanes over unchanged live plan bytes. If recovery also fails, stop as
   `INCONCLUSIVE`; never infer approval or require user intervention.

Momus focus: plan completeness, scope, dependencies, QA, and delivery
constraints. Oracle focus: logical consistency, failure terminal states, real
consumer paths, authority sources, permission isolation, security,
compatibility, and data risks.

## Review Criteria

Audit every frozen plan against all criteria:

- `D01`: owner outcome, success criteria, Scope IN and Scope OUT.
- `D02`: current source paths, consumers, tests, scripts, and behavior facts.
- `D03`: dependency order, generation barriers, parallel safety, read/write
  conflicts.
- `D04`: normal, failure, boundary, equivalent paths, and termination.
- `D05`: failure handling and terminal-state completeness.
- `D06`: decision-complete QA behavior, environment boundary, observable
  success/failure result, and evidence location.
- `D07`: future implementation evidence identity, persistence, digest, and
  read-back; not current review receipts.
- `D08`: real consumer, authoritative source, and behavior validation path.
- `D09`: agent and tool capability, permission, and isolation.
- `D10`: security, compatibility, data-loss, and external-contract risk only
  where specific impact and causal evidence exist.

An eligible blocker must violate an explicit owner decision, Scope IN/OUT, or
success criterion; expose a missing or contradictory invariant, dependency,
acceptance criterion, executable QA, or delivery constraint; reproduce an
existing regression or broken flow; or demonstrate a security, data-loss,
compatibility, or external-contract risk with concrete causal evidence.

Blockers based on source paths, consumers, tests, scripts, or symbols require
current verification against permitted repository facts. An unverified path,
stale reference, or inferred consumer is a non-blocking note. D06 and D07 may
require observable properties and evidence destinations, never commands,
receipt fields, log layouts, fixture or harness construction, temporary-file
protocols, or other implementation recipes unless the mechanism itself is an
explicit product behavior or security invariant.

Preferences, wording, extra examples, implementation recipes, optional
hardening, alternative architecture, unproven risks, scope expansion, and
demands to inline future implementation or QA artifacts are never blockers.

## Reconciliation And Repair

After both valid receipts for same frozen digest arrive:

1. Present required review evidence before reconciling.
2. Deduplicate only eligible blockers sharing a demonstrated root cause. For
   each candidate, state accepted or rejected and cite eligibility evidence. In
   discovery, freeze accepted candidates as the blocker ledger.
3. If no eligible blockers remain and both lanes returned unconditional
   `APPROVED`, read live plan bytes again. Approval is valid only when live
   digest and byte count equal frozen target. If different, discard approval
   and begin a new round.
4. Otherwise change only current formal plan. Apply every accepted blocker in
   one smallest aggregate repair. Use replacement-first: replace, simplify, or
   delete smallest relevant plan text before appending. Never add material
   unrelated to a closure assertion.
5. Re-read modified plan bytes and begin a closure round with its new digest.
   Verify ledger closure and repair regressions only. Do not reopen a closed
   root cause or accept an unchanged-baseline concern without new causal
   evidence. Add an admissible novel blocker to the ledger before one further
   aggregate repair; otherwise leave it as a note.

Keep formal plan decision-complete but non-bloated. It may retain only:

- implementation surface;
- dependency order;
- behavior invariants;
- acceptance criteria;
- executable happy-path and failure QA;
- evidence locations;
- delivery constraints;
- Scope IN/OUT; and
- residual risks.

Do not paste workflow receipts or ledgers, full state/event tables, guard
schemas, review controllers, fixture generators, QA harnesses, implementation
code, test implementation details, or exact QA command/log protocols. A plan
may demand properties of future implementation or QA artifacts, not their
complete contents. Missing post-implementation evidence blocks implementation
review or delivery, never forces that evidence into plan. Do not expand an
already decision-complete plan to preempt possible implementation issues.

## Workflow Evidence (Never Plan Content)

Emit workflow evidence in review output, not the formal plan. For discovery,
record D01-D10 coverage, lane identity binding, findings, and verdicts. For
closure, record ledger closure, admissible novel findings, lane identity
binding, and verdicts. A compact coverage matrix is sufficient; only eligible
blockers require the full field set.

For every completed or failed round, record:

- frozen target digest, byte count, and round identity;
- Momus and Oracle lane status, identity binding, applicable coverage,
  findings, and verdict;
- deadline, attempt, observed failure, and termination or detachment result
  when a lane fails or expires;
- reconciliation decisions, including root-cause merges and accepted or
  rejected blocker eligibility reasons;
- repair summary when applicable;
- final live read-back digest, byte count, and comparison result when approval
  is considered; and
- workflow state: `REVIEWING`, `REPAIRING_PLAN`, `APPROVED`, or
  `INCONCLUSIVE`.

Use any clear structure that preserves this evidence. Do not treat headings,
ordering, or serialization format as a review-validity requirement.

`APPROVED` may appear only after Momus and Oracle each unconditionally approve
same live digest and final live read-back matches that digest. Otherwise use
`REVIEWING`, `REPAIRING_PLAN`, or `INCONCLUSIVE` truthfully. Stop immediately
after reporting valid dual approval; do not run implementation work or extra
review.
