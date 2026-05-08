# Validation Checklist

Use this checklist before applying any PR comment.

## Decide Validity

Mark each comment as one of:

- `valid`: technically correct, in-scope, and still applies to current HEAD.
- `invalid`: incorrect claim, unsafe recommendation, or contradicts repo conventions.
- `already_fixed`: issue is no longer present.
- `out_of_scope`: unrelated to the PR scope.
- `needs_clarification`: ambiguous ask or missing acceptance criteria.

## Validate AI/Bot Comments

For bot comments (for example CodeRabbit), process in this order:

1. Read any embedded “Prompt for AI Agents” block.
2. Verify each suggested file/line exists on current HEAD.
3. Reproduce or reason about the claimed issue.
4. Apply only changes that improve correctness/safety/maintainability.
5. Ignore purely mechanical changes that conflict with local conventions.

## Validate Human Comments

1. Identify intent (bug risk, style, scope, product behavior).
2. Confirm current behavior in code.
3. Validate side effects and regressions.
4. Prefer the reviewer’s intent over literal wording when they differ.

## Evidence Requirements

Before marking a comment `valid`, collect at least one:

- file+line proof from current code
- failing check / warning / linter output
- reproducible behavior path

## Implementation Rules

- Batch related fixes together.
- Keep unrelated cleanups out of the patch.
- Run checks relevant to changed files only, scoped to the modified paths.
- Create one local commit per resolved `valid` comment.
- Examine recent commits (`git log --oneline -10`) to understand the repository's commit message style. If a commit message generation skill is installed, use it. Otherwise, write a concise commit message that follows the same conventions.
- Do not push as part of this workflow.

## Suggested Status Summary Format

```text
Addressed:
- <comment link or reviewer>: <what changed> (<file path>) | commit <sha>

Not Addressed:
- <comment link or reviewer>: <reason: invalid/already_fixed/out_of_scope>

Needs Clarification:
- <comment link or reviewer>: <specific question>
```
