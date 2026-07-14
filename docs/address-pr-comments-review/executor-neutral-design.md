# Executor-Neutral Design: address-pr-comments-review

## Status

Approved design. Implementation has not started.

## Objective

Make the PR comment review workflow independent of any agent runtime or orchestration command. Preserve evidence-led review, checkout binding, user confirmation, artifact generation, scoped execution, verification, replies, read-back, and artifact cleanup.

The finished workflow must be usable by any agent or human operator that can read Markdown, access the bound checkout, run Git commands, and use the GitHub CLI.

## Non-Goals

- Replacing GitHub or the `gh` CLI.
- Introducing a serialized JSON or YAML protocol.
- Retaining runtime-specific adapters, aliases, examples, or compatibility paths.
- Changing comment collection or classification behavior unrelated to executor coupling.
- Expanding cleanup beyond artifacts created by this workflow.

## Chosen Architecture

Split the workflow into two modules joined by one approved Markdown artifact interface.

```text
PR + bound checkout + comments
            |
            v
[Review Analysis Module]
 evidence -> classify -> cross-reference -> user confirmation
            |
            v
[Approved Artifact Interface]
 Review Dossier | Direct Fix Brief | Reply Only (POST/read-back) | No Action (terminal)
            |
            v
[Execution Handoff Module]
 scope check -> change -> verify -> commit -> reply -> read-back -> cleanup
```

### Review Analysis Module

Inputs:

- Bound checkout identity.
- PR identity.
- Normalized comments and thread metadata.
- Current repository evidence.

Responsibilities:

- Bind and verify the current checkout before PR detection.
- Collect comments through `scripts/list_comments.py`.
- Build the Evidence Ledger.
- Classify comments from current-code evidence.
- Detect duplicates, conflicts, dependencies, and existing replies.
- Route to one of four outcomes (see Artifact Types below).
- Obtain required user decisions and confirmation.
- Generate exactly one approved artifact when code work is required.

The module does not select an executor, prescribe a runtime command, generate an executor-specific plan, or apply code changes.

Completion criterion: the route is determined, classification is complete, and (when applicable) one approved artifact exists, contains no placeholders, matches the bound checkout, and passes its completeness gate.

### Approved Artifact Interface

Every executable artifact carries:

- PR URL, repository, branch, HEAD, and absolute checkout root.
- Reviewer concern and current-code evidence for each actionable item.
- Classification, fix direction, scope guardrails, and dependencies.
- Exact authorized changes or reply-only actions.
- Targeted verification commands and expected outcomes.
- Reply kind, target, endpoint requirements, and commit SHA requirements.
- Read-back verification and cleanup conditions.

Artifact types (two persisted, two terminal):

| Artifact | Condition | Consumer action |
|----------|-----------|-----------------|
| Review Dossier | Code work is complex, cross-file, dependent, or otherwise unsuitable for direct execution | Execute ordered tasks under the full execution contract; persisted artifact |
| Direct Fix Brief | Confirmed low-risk, mechanically specified code work meets every fast-path gate | Execute the exact bounded change; persisted artifact |
| Reply Only | No code changes are needed, but confirmed replies remain | Direct POST to each reply endpoint, then GET/LIST read-back verification; no artifact written |
| No Action | Nothing remains actionable | Terminal no-write; record completion only |

Markdown remains the interface for persisted artifacts. Mandatory sections and completeness gates provide sufficient structure without adding schema versioning or parser maintenance.

### Artifact Lifecycle

Every persisted artifact (Review Dossier, Direct Fix Brief) transitions through four states:

| State | Trigger | Meaning |
|-------|---------|---------|
| `pending` | Artifact generated and passed completeness gate | Ready for execution; no work has begun |
| `in-progress` | First authorized change applied to the bound checkout | Work is underway; artifact may be partially complete |
| `blocked` | Execution cannot proceed (stale evidence, checkout mismatch, dependency unresolved, verification failure) | Execution stops; artifact preserved for handoff or evidence regeneration |
| `verified-complete` | All required changes applied, verified, committed (if requested), replies posted, and read-back passes | Artifact is done; eligible for cleanup |

Transitions are one-way (pending → in-progress → verified-complete). An artifact in `blocked` returns to Review Analysis for regeneration with fresh evidence.

### Execution Handoff Module

Input: an approved artifact and access to the matching checkout. For Reply Only and No Action routes, no artifact is needed — the route itself defines the execution contract.

Responsibilities:

1. Verify repository, branch, checkout root, and relevant HEAD state.
2. Stop on unresolved checkout mismatch or stale evidence.
3. Execute only actions authorized by the artifact.
4. Respect dependency ordering and scope guardrails.
5. Run targeted verification before any success claim or review reply.
6. Commit only when requested by the operator.
7. Include the resulting commit SHA in replies that require one (Section A mandatory order).
8. Post each required reply through the correct endpoint.
9. Verify every posted reply through GET or LIST read-back.
10. Clean artifacts only after verified completion.

Output: an execution summary containing applied, skipped, and blocked items; verification results; commit SHA or no-commit reason; reply identifiers; read-back evidence; unresolved work; and cleanup disposition.

The module contains no agent names, runtime commands, plan file conventions, or runtime-specific recovery semantics.

### Section A Mandatory Commit Order

When a Review Dossier or Direct Fix Brief contains Section A items (code changes that require replies with commit SHAs), the execution order is fixed:

```
edit → verify → commit → remote-reachability → reply → read-back
```

1. **edit**: Apply authorized code changes to the bound checkout.
2. **verify**: Run the artifact's targeted verification commands. Do not proceed if verification fails.
3. **commit**: Commit only if requested by the operator. If no commit is requested, Section A replies must use a no-commit annotation instead of a commit SHA.
4. **remote-reachability**: Confirm the commit is reachable from the remote (pushed). If not pushed, Section A replies must not include a SHA.
5. **reply**: Post each reply through the correct endpoint with the commit SHA (or no-commit annotation).
6. **read-back**: Verify every posted reply via GET or LIST. Skip only items already proven posted.

This order is mandatory for every Section A artifact. Reordering or skipping steps invalidates the reply contract.

### Dirty-Target Blocking

Before applying any change, the Execution Handoff must verify that the target files are clean (no uncommitted modifications unrelated to the current artifact).

- If any target file is dirty, execution stops immediately.
- The artifact transitions to `blocked`.
- The blocked reason references the dirty file paths.
- Execution may resume only after the operator resolves the dirty state or regenerates the artifact against fresh checkout state.

### Cleanup Semantics

Artifact cleanup is governed by the following rules:

- Cleanup is only permitted when the artifact is in `verified-complete` state.
- Attempting cleanup on a `pending`, `in-progress`, or `blocked` artifact must be refused with the current state and blocked reason.
- The `--force` flag overrides the state guard but requires two explicit confirmations from the operator:
  1. First confirmation: operator acknowledges the artifact state and cleanup risk.
  2. Second confirmation: operator confirms the exact artifact path(s) to delete.
- After cleanup, the artifact directory is removed. If the parent per-repo directory becomes empty, it is also removed.

## Workflow

1. Bind checkout and record repository, branch, and HEAD.
2. Detect PR and collect review comments.
3. Build evidence, classify, and cross-reference the full comment set.
4. Present the overview and resolve blocking decisions.
5. Obtain explicit confirmation where required.
6. Route to one of four outcomes: Review Dossier, Direct Fix Brief, Reply Only, or No Action.
7. For persisted artifacts: generate the artifact, run completeness checks, present executor-neutral handoff prompt.
8. Executor validates checkout identity before acting.
9. Executor applies authorized work, verifies it, and commits only if requested.
10. Executor posts required replies and verifies them by read-back.
11. Executor cleans artifacts only after every required action is verified.

## Failure Handling

| Failure | Required behavior |
|---------|-------------------|
| Checkout identity mismatch | Stop before changes; bind the intended checkout or regenerate the artifact |
| Evidence no longer matches current code | Return affected items to Review Analysis |
| Target files are dirty | Stop immediately; transition artifact to `blocked` with dirty path details |
| Verification fails | Do not commit, claim success, post a fixed reply, or clean artifacts |
| Commit unreachable from remote | Section A replies must not include a commit SHA |
| Reply POST result is unclear | Read back first; retry only after proving the reply is absent |
| Execution is interrupted | Re-read artifact, current HEAD, and existing replies; skip only items already proven complete |
| Some tasks remain blocked | Preserve artifact and report exact blocked items and required decisions |
| Cleanup requested before verified-complete | Refuse cleanup unless `--force` with two confirmations |

## File Migration

### `skills/address-pr-comments-review/SKILL.md`

- Replace three runtime-oriented phases with Review Analysis and Execution Handoff.
- Remove runtime lock, runtime-specific handoff, command-specific recovery, and branded fallback language.
- Route complex work to Review Dossier, not to a named planner.
- Keep Direct Fix, Reply Only, No Action, and cleanup routes.

### [`execution.md`](../../skills/address-pr-comments-review/references/execution.md)

- Rename the file and update every direct reference.
- Keep checkout binding, GitHub CLI prerequisites, collection contract, artifact paths, handoff, and cleanup.
- Replace multiple handoff variants with one executor-neutral handoff.
- Remove runtime-specific artifact locations, commands, and plan-generation text.
- Add artifact lifecycle states and transitions.
- Add dirty-target blocking rule.
- Add Section A mandatory commit order.
- Add cleanup `--force` and two-confirmation semantics.

### [`dossier-output.md`](../../skills/address-pr-comments-review/references/dossier-output.md)

- Replace generated-plan terminology with Artifact Execution Contract.
- Express ordering and reply obligations directly as executor requirements.
- Make handoff completeness require only the generic prompt, artifact path, and cleanup target.
- Route Direct Fix ineligibility to Review Dossier.
- Add Section A mandatory commit order reference.

### [`interaction.md`](../../skills/address-pr-comments-review/references/interaction.md)

- Route by work shape only: Direct Fix, Review Dossier, Reply Only, or No Action.
- Replace planner-specific scaling language with artifact dependency ordering.
- Remove runtime-specific choices from the accuracy gate.

### [`classify.md`](../../skills/address-pr-comments-review/references/classify.md) and [`cross-reference.md`](../../skills/address-pr-comments-review/references/cross-reference.md)

- Preserve classification and cross-reference behavior.
- Replace generic plan-mode wording with execution ordering where needed.
- Update references affected by the file rename.

### `scripts/list_comments.py`

No behavior change planned.

### Repository documentation and evaluations

- Describe the workflow as executor-neutral.
- Update direct references to renamed files and changed handoff contracts.
- Remove runtime-specific cases from the evaluation matrix and replace them with equivalent behavioral cases.
- Reference execution.md (not the old platform.md name) in all documentation.

## Skill TDD Strategy

Implementation starts with failing behavioral scenarios. Source edits begin only after each changed behavior class has an observed baseline failure.

The TDD protocol uses 40 samples across 4 behavior classes × 5 sessions each:

### RED scenarios (20 samples)

Class 1 — Artifact type routing (5 samples):
- Complex code work emits runtime-specific handoff material instead of one neutral artifact contract.
- Direct Fix ineligibility routes to a named planner instead of Review Dossier.
- Reply Only produces an unnecessary persisted artifact instead of direct POST/read-back.
- No Action produces a write operation.
- Unknown route falls through without classification.

Class 2 — Execution contract completeness (5 samples):
- Interrupted execution depends on a runtime command instead of observable repository and reply state.
- Generic executors receive unequal or incomplete obligations.
- Section A commit order is reordered or skipped.
- Dirty target files do not block execution.
- Cleanup proceeds without verified-complete state.

Class 3 — Reply and read-back (5 samples):
- Section A reply lacks commit SHA verification.
- Reply POST is not verified by read-back.
- Duplicate authors receive only one reply.
- Reply Only route skips read-back.
- Read-back is claimed but not executed.

Class 4 — Lifecycle and cleanup (5 samples):
- Artifact state transitions are non-deterministic or bidirectional.
- `blocked` state is treated as terminal without recovery path.
- Cleanup `--force` proceeds with single confirmation.
- Empty parent directory is not cleaned up after artifact removal.
- Checkout mismatch does not transition to `blocked`.

### GREEN scenarios (20 samples)

Class 1 — Artifact type routing (5 samples):
- Review Dossier preserves ordered code, verification, optional commit, reply, and read-back obligations.
- Direct Fix Brief preserves exact scope, validation, commit SHA reply, and read-back gates.
- Reply Only performs no code or commit work and verifies every reply.
- No Action produces no write operations.
- Route classification is deterministic given the same evidence.

Class 2 — Execution contract completeness (5 samples):
- Checkout mismatch and stale evidence stop execution.
- Section A mandatory commit order (edit → verify → commit → remote-reachability → reply → read-back) is preserved.
- Dirty target files block execution and transition to `blocked`.
- Duplicate and conflict handling preserve every required reply target.
- Interrupted execution resumes from current code and read-back evidence without duplicate writes.

Class 3 — Reply and read-back (5 samples):
- Every Section A reply includes commit SHA (or explicit no-commit annotation).
- Every posted reply is verified by GET/LIST read-back.
- Reply Only posts directly and verifies via read-back.
- Duplicate authors each receive individual replies.
- Read-back evidence is recorded in the execution summary.

Class 4 — Lifecycle and cleanup (5 samples):
- Artifact transitions follow one-way path: pending → in-progress → blocked → regenerated, or pending → in-progress → verified-complete.
- Cleanup occurs only after verified-complete, or with `--force` and two confirmations.
- Cleanup removes the artifact directory and empty parent.
- `blocked` state preserves artifact for handoff or regeneration.
- Execution summary records final artifact state and cleanup disposition.

Run each behavior-shaping scenario in multiple fresh contexts. Judge obligations and outcomes, not exact wording.

## Acceptance Criteria

1. Repository scan finds zero forbidden runtime-specific names, commands, or artifact paths in skill source, references, README, documentation, and evaluations.
2. Review Analysis and Execution Handoff expose separate responsibilities joined only by the approved artifact interface.
3. All four outcome routes have explicit entry conditions and completion criteria.
4. Two persisted artifact types (Review Dossier, Direct Fix Brief) have defined lifecycle states and transitions.
5. Reply Only and No Action are terminal routes with no artifact persistence.
6. Section A mandatory commit order is documented and enforced.
7. Dirty-target blocking is documented and enforced.
8. Cleanup semantics (`--force`, two-confirmation) are documented and enforced.
9. Existing evidence, duplicate, conflict, reply endpoint, commit SHA, read-back, and cleanup requirements remain mandatory.
10. Every affected Markdown cross-reference resolves.
11. `bash scripts/check-cross-refs.sh` passes.
12. No artifact template contains an unfilled placeholder after generation.
13. At least five fresh executor contexts and one human-operator scenario produce equivalent execution obligations.
14. `scripts/list_comments.py` behavior remains unchanged and its existing checks pass.
15. 40-sample TDD (20 RED + 20 GREEN) passes across 4 behavior classes × 5 sessions each.

## Risks and Controls

| Risk | Control |
|------|---------|
| Text replacement weakens mandatory behavior | Rewrite requirements around observable outcomes; verify with behavioral scenarios |
| Analysis starts prescribing execution mechanics | Enforce module completion criteria and artifact-only seam |
| Neutral wording becomes vague | Define ordered executor obligations and explicit output evidence |
| File rename breaks navigation | Update all references and run cross-reference checks |
| Reply behavior regresses | Preserve endpoint, SHA, duplicate, and read-back scenarios as blocking tests |
| Token scan passes while behavior fails | Require both forbidden-term scan and fresh-context GREEN scenarios |
| Artifact lifecycle is ambiguous | Define fixed one-way state transitions with explicit trigger conditions |
| Dirty-target check is skipped | Make dirty-target blocking a mandatory pre-execution gate |

## Implementation Sequence

1. Establish RED scenarios (20 samples) for every changed behavior class (4 classes × 5 sessions).
2. Define final artifact and execution contracts in evaluation fixtures.
3. Rewrite Review Analysis and Execution Handoff independently against those scenarios.
4. Rename the execution reference — platform.md becomes execution.md — and update direct links.
5. Align README, architecture documentation, and evaluation matrix.
6. Run GREEN scenarios (20 samples), forbidden-term scan, cross-reference checks, and script regression checks.

No compatibility layer or transitional alias is planned.
