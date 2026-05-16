# Review Dossier: PR #{{PR_NUMBER}} — {{PR_TITLE}}

> **For Prometheus**: Read this dossier and generate an execution plan for `/start-work`.
> All classification decisions are confirmed below, but ask clarifying questions if any task is ambiguous.
>
> **Minimum requirements for the plan** (how you achieve them is up to you):
> - No two tasks modifying the same file run concurrently
> - Each task runs with the right agent profile for its domain (backend tests → golang-testing, code changes → appropriate profile)
> - Each task knows its scope boundary: what NOT to change beyond the fix
> - Tests target specific test names, not broad `-run` patterns
> - Reply-only tasks are locked down: no code changes, no test runs, no commits
> - After all tasks complete, a final verification wave validates the whole PR
>
> *These are minimum requirements, not a rigid template. If Prometheus has evolved native mechanisms that achieve these outcomes, prefer native.*

## Executive Summary

| Category | Count | Action |
|----------|-------|--------|
| Needs code change + reply | {{VALID_COUNT}} | Modify code, run tests, reply inline, commit |
| Needs reply only | {{REPLY_ONLY_COUNT}} | Reply inline with explanation, no code changes |
| Already replied (skip) | {{ALREADY_REPLIED_COUNT}} | Already has a human reply — no action needed |
| Informational (skip) | {{INFO_COUNT}} | No action |
| **Total plan tasks** | **{{TOTAL_TASKS}}** | **code tasks + reply tasks** |
| **Raw comments (before dedup)** | {{RAW_COUNT}} | Original count from list_comments.py |
| **Merged duplicates** | {{DUP_COUNT}} | Comments merged into entries above |
| **Conflicts resolved** | {{CONFLICT_COUNT}} | User chose one direction among conflicting advice |

## Dedup & Conflict Notes

| Type | Count | Details |
|------|-------|---------|
| Duplicates merged | {{DUP_COUNT}} | {{DUP_DETAILS}} |
| Conflicts resolved | {{CONFLICT_COUNT}} | {{CONFLICT_DETAILS}} |

## Context

- PR: {{PR_URL}}
- Branch: {{BRANCH}}
- Repository: {{REPO}}
- Commit style: {{COMMIT_STYLE}} (run `git log --oneline -10` in the PR branch to discover conventions)
- Analyzed: {{TIMESTAMP}}

---

## A. Comments Requiring Code Change + Reply ({{VALID_COUNT}} items)

Each item requires: code modification → run targeted tests → reply with commit SHA → local commit.
If duplicates exist, reply to ALL authors individually.

**Reply endpoint selection** (same as Section B):

| Reply Kind | Endpoint | Key Flag |
|------------|----------|----------|
| `inline` | `repos/{owner}/{repo}/pulls/{pr}/comments` | `in_reply_to=<id>` |
| `review` | `repos/{owner}/{repo}/issues/{pr}/comments` | mention @author in body |
| `top_level` | `repos/{owner}/{repo}/issues/{pr}/comments` | — |

### Task {{TASK_NUM}}: Comment #{{COMMENT_ID}} — {{SUMMARY}}

- **Source**: @{{AUTHOR}} | {{KIND}} | {{FILE_PATH}}:{{LINE}}
- **Also noted by**: @{{DUP_AUTHOR1}}, @{{DUP_AUTHOR2}} (omit if no duplicates)
- **Conclusion**: `valid`
- **What to change**: {{DEV_CHANGES}} (exact file path, line numbers, specific code modification)
- **How to test**: {{TEST_STRATEGY}} (specific test commands, expected output)
- **Reply after fix**: {{REPLY_KIND}} → @{{AUTHOR}}

  ```bash
  # inline:
  gh api repos/{{REPO}}/pulls/{{PR_NUMBER}}/comments --method POST \
    -F body="{{REPLY_TEXT}}" -F commit_id=$(git rev-parse HEAD) \
    -F path="{{FILE_PATH}}" -F line={{LINE}} -F side=RIGHT \
    -F in_reply_to={{COMMENT_ID}}

  # review:
  gh api repos/{{REPO}}/issues/{{PR_NUMBER}}/comments --method POST \
    -F body="@{{AUTHOR}} {{REPLY_TEXT}}"

  # top_level:
  gh api repos/{{REPO}}/issues/{{PR_NUMBER}}/comments --method POST \
    -F body="{{REPLY_TEXT}}"
  ```

- **Reply to duplicate authors**: Repeat for @{{DUP_AUTHOR}} with `in_reply_to={{DUP_COMMENT_ID}}`
- **Commit message**: `{{SUGGESTED_COMMIT_MESSAGE}}`

---

## B. Comments Requiring Reply Only ({{REPLY_ONLY_COUNT}} items)

**No code changes needed.** Each item only requires a reply explaining the decision. No tests, no commits.

**IMPORTANT**: Choose the correct `gh api` endpoint based on `{{REPLY_KIND}}`. Each kind uses a different endpoint:

| Reply Kind | Endpoint | Key Flag |
|------------|----------|----------|
| `inline` | `repos/{owner}/{repo}/pulls/{pr}/comments` | `in_reply_to=<id>` |
| `review` | `repos/{owner}/{repo}/issues/{pr}/comments` | mention @author in body |
| `top_level` | `repos/{owner}/{repo}/issues/{pr}/comments` | — |

**Commit SHA note**: Inline replies require a valid commit SHA on the PR branch. Use `git rev-parse HEAD` from the PR branch (NOT a newly created commit — no code changes exist). `review` and `top_level` replies do NOT need `commit_id`.

### Reply Task {{TASK_NUM}}: Comment #{{COMMENT_ID}} — {{SUMMARY}}

- **Source**: @{{AUTHOR}} | {{KIND}} | {{FILE_PATH}}:{{LINE}}
- **Conclusion**: `{{CONCLUSION}}` — {{RATIONALE}}
- **Reply**: {{REPLY_KIND}} → @{{AUTHOR}}

  ```bash
  # inline:
  gh api repos/{{REPO}}/pulls/{{PR_NUMBER}}/comments --method POST \
    -F body="{{REPLY_TEXT}}" -F commit_id=$(git rev-parse HEAD) \
    -F path="{{FILE_PATH}}" -F line={{LINE}} -F side=RIGHT \
    -F in_reply_to={{COMMENT_ID}}

  # review:
  gh api repos/{{REPO}}/issues/{{PR_NUMBER}}/comments --method POST \
    -F body="@{{AUTHOR}} {{REPLY_TEXT}}"

  # top_level:
  gh api repos/{{REPO}}/issues/{{PR_NUMBER}}/comments --method POST \
    -F body="{{REPLY_TEXT}}"
  ```

### Reply Task {{TASK_NUM}}: Comment #{{COMMENT_ID}} — Conflict resolution: {{SUMMARY}}

- **Source**: @{{REJECTED_AUTHOR}} (vs @{{CHOSEN_AUTHOR}}) | {{KIND}} | {{FILE_PATH}}:{{LINE}}
- **Context**: User chose @{{CHOSEN_AUTHOR}}'s approach over @{{REJECTED_AUTHOR}}'s conflicting suggestion.
- **Conclusion**: `invalid` (conflicting approach not taken)
- **Reply**: {{REPLY_KIND}} → @{{REJECTED_AUTHOR}}

  *(Use the endpoint matching `{{REPLY_KIND}}` as shown above)*

---

## C. Informational & Already-Replied Comments — No Action ({{INFO_COUNT}} + {{ALREADY_REPLIED_COUNT}} items)

No code changes. No replies. LGTM, praise, emoji-only, FYI, minimized/hidden, already-replied.

| # | Source | Kind | Summary | Reason |
|---|--------|------|---------|--------|
| {{COMMENT_ID}} | @{{AUTHOR}} | {{KIND}} | {{SUMMARY}} | {{informational / already_replied}} |

---

## Reply Templates (Reference)

| Outcome | Reply Text |
|---------|------------|
| valid (fixed) | `Fixed in <commit_sha>.` |
| invalid | `This suggestion doesn't apply because <brief reason>.` |
| already_fixed | `Already resolved in the current code — no changes needed.` |
| already_replied | (Skip — already has a human reply) |
| out_of_scope | `This is outside the scope of this PR. <Optional: suggest follow-up>.` |
| needs_clarification | `Confirmed: <resolved direction>.` |
| conflict (not chosen) | `Thanks for the suggestion. We went with @other's approach for <reason>.` |

## Cross-Reference Checks

| Check | Status |
|-------|--------|
| New duplicates | {{NEW_DUP_CHECK}} |
| Stale duplicates | {{STALE_DUP_CHECK}} |
| Unresolved conflicts | {{UNRESOLVED_CONFLICT_CHECK}} |
| Orphaned replies | {{ORPHANED_REPLY_CHECK}} |
| New relations | {{NEW_RELATION_CHECK}} |
| Cross-section leakage | {{CROSS_SECTION_CHECK}} |
| Reply target mismatch | {{REPLY_TARGET_CHECK}} |
| Stale already_replied | {{STALE_ALREADY_REPLIED_CHECK}} |

## Dependencies

{{DEPENDENCIES}}

If related comments exist (call chain, shared type), note here:
- Task X and Task Y both modify `shared_type.go` — coordinate changes.
- Task A is a callee of Task B's caller — order: fix callee first, then caller.
- Fixing Task X may make Task Y unnecessary — verify after X is complete.

## Scope Guardrails

These constraints prevent scope creep during execution. Prometheus should bake them into every task.

| Rule | Rationale |
|------|-----------|
| {{GUARDRAIL_1}} | {{RATIONALE_1}} |
| {{GUARDRAIL_2}} | {{RATIONALE_2}} |

Common guardrails for PR review remediation:
- Do not refresh `vendor/` or update dependencies.
- Do not refactor code outside the changed lines unless the fix requires it.
- Do not expand a fix into a general-purpose helper/utility.
- Reply-only tasks must NOT modify any code, run tests, or create commits.
- Do not rewrite tests beyond what's needed to validate the fix (no test suite reorganization).
