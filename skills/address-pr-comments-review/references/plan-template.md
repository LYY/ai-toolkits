# Plan: PR #{{PR_NUMBER}} — {{PR_TITLE}}

## Goal

Address {{ACTIONABLE_COUNT}} actionable review comments. Apply valid fixes, respond per outcome, skip non-actionable items.

## Architecture

{{ARCHITECTURE_NOTE}}

## Tech Stack

{{TECH_STACK}}

## Tasks

### Task {{TASK_NUM}}: Comment #{{COMMENT_ID}} — {{SUMMARY}}

- **Source**: @{{AUTHOR}} | {{COMMENT_TYPE}} — {{FILE_PATH}}:{{LINE_NUMBER}}
- **Dev**: {{CHANGE_DESCRIPTION}}
- **Test**: {{TEST_STRATEGY}}
- **Reply**: {{REPLY_TYPE}} → @{{AUTHOR}}

  ```bash
  {{REPLY_COMMAND}}
  ```
- **Commit**: `git commit -m "{{COMMIT_MESSAGE}}"`
- **Deps**: {{TASK_DEPENDENCIES}}

### Reply Type Reference

| Type | Endpoint | Key Flag |
|------|----------|----------|
| inline | `/repos/{{REPO_OWNER}}/{{REPO_NAME}}/pulls/{{PR_NUMBER}}/comments` | `in_reply_to={{COMMENT_ID}}` |
| review | `/repos/{{REPO_OWNER}}/{{REPO_NAME}}/pulls/{{PR_NUMBER}}/reviews` | `event=COMMENT` |
| top_level | `/repos/{{REPO_OWNER}}/{{REPO_NAME}}/issues/{{PR_NUMBER}}/comments` | — |

## Skipped Comments

| # | Source | File | Conclusion | Reason |
|---|--------|------|------------|--------|
| {{COMMENT_ID}} | @{{AUTHOR}} | {{FILE_PATH}} | {{CONCLUSION}} | {{REASON}} |

## Reply Templates

| Outcome | Reply Text |
|---------|------------|
| valid (fixed) | `Fixed in {{COMMIT_SHA}}.` |
| invalid | `This suggestion doesn't apply because {{REASON}}.` |
| already_fixed | `Already resolved in the current code — no changes needed.` |
| out_of_scope | `This is outside the scope of this PR. {{OPTIONAL_FOLLOW_UP}}` |
| needs_clarification | `Confirmed: {{RESOLVED_DIRECTION}}.` |

## Dependencies

{{DEPENDENCIES_NOTE}}
