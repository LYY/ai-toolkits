# Review Dossier: PR #{{PR_NUMBER}} — {{PR_TITLE}}

> **For Prometheus plan mode**: Read this dossier to generate the execution plan.
> No further interview needed — all decisions are confirmed below.

## Executive Summary

| Category | Count | Action |
|----------|-------|--------|
| Needs code change + reply | {{VALID_COUNT}} | Modify code, run tests, reply inline, commit |
| Needs reply only | {{REPLY_ONLY_COUNT}} | Reply inline with explanation, no code changes |
| Informational (skip) | {{INFO_COUNT}} | No action |
| **Total tasks for plan** | **{{TOTAL_TASKS}}** | **{{VALID_COUNT}} code tasks + {{REPLY_ONLY_COUNT}} reply tasks** |

## Context

- PR: {{PR_URL}}
- Branch: {{BRANCH}}
- Repository: {{REPO}}
- Analyzed: {{TIMESTAMP}}

---

## A. Comments Requiring Code Change + Reply ({{VALID_COUNT}} items)

Each item requires: code modification → run targeted tests → inline reply with commit SHA → local commit.

### Comment #{{COMMENT_ID}}: {{SUMMARY}}

- **Source**: @{{AUTHOR}} | {{KIND}} | {{FILE_PATH}}:{{LINE}}
- **Conclusion**: `valid`
- **What to change**: {{DEV_CHANGES}} (exact file path, line numbers, specific code modification)
- **How to test**: {{TEST_STRATEGY}} (specific test commands, expected output)
- **Reply after fix**: {{REPLY_KIND}} → @{{AUTHOR}}

  ```bash
  # Choose the correct endpoint based on reply kind:
  # inline:
  gh api repos/{{REPO}}/pulls/{{PR_NUMBER}}/comments --method POST \
    -F body="{{REPLY_TEXT}}" -F commit_id=$(git rev-parse HEAD) \
    -F path="{{FILE_PATH}}" -F line={{LINE}} -F side=RIGHT \
    -F in_reply_to={{COMMENT_ID}}
  # review:
  gh api repos/{{REPO}}/pulls/{{PR_NUMBER}}/reviews --method POST \
    -F body="{{REPLY_TEXT}}" -F event=COMMENT
  # top_level:
  gh api repos/{{REPO}}/issues/{{PR_NUMBER}}/comments --method POST \
    -F body="{{REPLY_TEXT}}"
  ```

- **Commit message**: `{{SUGGESTED_COMMIT_MESSAGE}}`

---

## B. Comments Requiring Reply Only ({{REPLY_ONLY_COUNT}} items)

**No code changes needed.** Each item only requires an inline reply explaining why the suggestion was not applied. No tests, no commits.

### Comment #{{COMMENT_ID}}: {{SUMMARY}}

- **Source**: @{{AUTHOR}} | {{KIND}} | {{FILE_PATH}}:{{LINE}}
- **Conclusion**: `{{CONCLUSION}}` — {{RATIONALE}}
- **Reply**: {{REPLY_KIND}} → @{{AUTHOR}}

  ```bash
  # Choose the correct endpoint (same as section A):
  gh api repos/{{REPO}}/pulls/{{PR_NUMBER}}/comments --method POST \
    -F body="{{REPLY_TEXT}}" -F commit_id=$(git rev-parse HEAD) \
    -F path="{{FILE_PATH}}" -F line={{LINE}} -F side=RIGHT \
    -F in_reply_to={{COMMENT_ID}}
  ```

---

## C. Informational Comments — No Action ({{INFO_COUNT}} items)

No code changes. No replies. These are LGTM, praise, emoji-only, or FYI comments.

| # | Source | Kind | Summary |
|---|--------|------|---------|
| {{COMMENT_ID}} | @{{AUTHOR}} | {{KIND}} | {{SUMMARY}} |

---

## Reply Templates (Reference)

| Outcome | Reply Text |
|---------|------------|
| valid (fixed) | `Fixed in <commit_sha>.` |
| invalid | `This suggestion doesn't apply because <brief reason>.` |
| already_fixed | `Already resolved in the current code — no changes needed.` |
| out_of_scope | `This is outside the scope of this PR. <Optional: suggest follow-up>.` |
| needs_clarification | `Confirmed: <resolved direction>.` |

## Reply Endpoints

| Type | gh api Endpoint | Key Flag |
|------|----------------|----------|
| inline | `repos/{owner}/{repo}/pulls/{pr}/comments` | `in_reply_to=<comment_id>` |
| review | `repos/{owner}/{repo}/pulls/{pr}/reviews` | `event=COMMENT` |
| top_level | `repos/{owner}/{repo}/issues/{pr}/comments` | — |

## Dependencies

{{DEPENDENCIES_NOTE}}
