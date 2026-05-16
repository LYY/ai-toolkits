# Review Dossier: PR #{{PR_NUMBER}} — {{PR_TITLE}}

> **For Prometheus plan mode**: Read this dossier to generate the execution plan.
> No further interview needed — all decisions are confirmed below.

## Context

- PR: {{PR_URL}}
- Branch: {{BRANCH}}
- Repository: {{REPO}}
- Analyzed: {{TIMESTAMP}}
- Actionable comments: {{ACTIONABLE_COUNT}} | To fix: {{TO_FIX_COUNT}}

## Confirmed Actionable Comments

### Comment #{{COMMENT_ID}}: {{SUMMARY}}

- **Source**: @{{AUTHOR}} | {{KIND}} | {{FILE_PATH}}:{{LINE}}
- **Conclusion**: {{CONCLUSION}} — {{RATIONALE}}
- **What to do**: {{DEV_CHANGES}}
- **How to test**: {{TEST_STRATEGY}}
- **Reply**: {{REPLY_KIND}} → @{{AUTHOR}}

  ```bash
  # inline: gh api repos/{{REPO}}/pulls/{{PR_NUMBER}}/comments --method POST \
  #   -F body="{{REPLY_TEXT}}" -F commit_id=$(git rev-parse HEAD) \
  #   -F path="{{FILE_PATH}}" -F line={{LINE}} -F side=RIGHT \
  #   -F in_reply_to={{COMMENT_ID}}
  #
  # review: gh api repos/{{REPO}}/pulls/{{PR_NUMBER}}/reviews --method POST \
  #   -F body="{{REPLY_TEXT}}" -F event=COMMENT
  #
  # top_level: gh api repos/{{REPO}}/issues/{{PR_NUMBER}}/comments --method POST \
  #   -F body="{{REPLY_TEXT}}"
  ```

- **Commit message**: `{{SUGGESTED_COMMIT_MESSAGE}}`

## Skipped Comments

| # | Source | File | Conclusion | Reason |
|---|--------|------|------------|--------|
| {{COMMENT_ID}} | @{{AUTHOR}} | {{FILE_PATH}} | {{CONCLUSION}} | {{REASON}} |

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
