# Reply Policy

This file defines the reply policy — the templates, endpoint rules, and multi-author reply strategy for responding to PR review comments. It is responsible for ensuring every reply is correctly addressed, properly formatted, and directed to the right endpoint.

## Precedence

Layer 3 (decision protocols). Consumes conclusion assignments from classification and cross-reference protocols. Reply templates are selected by conclusion type (assigned in Step 2). Reply endpoints are selected by comment kind (assigned in Step 1, documented in dossier). Template defaults can be overridden by explicit instructions from the interaction protocol (Step 3).

---

## Scope

This file covers:
- **Reply templates per conclusion**: valid (fixed), invalid, already_fixed, out_of_scope, needs_clarification, conflict (not chosen)
- **Endpoint kinds**: inline (pull request comments), review (issue comments), top_level (issue comments)
- **Endpoint commands**: `gh api` commands per endpoint kind, required parameters (commit_id, path, line, in_reply_to, etc.)
- **Duplicate author reply strategy**: same content, different `in_reply_to` IDs
- **Conflict reply strategy**: reply to rejected reviewer explaining why their approach wasn't taken
- **Commit SHA note**: inline replies require a valid commit SHA on the PR branch

## Out of Scope

- Conclusion assignment → `classification.md`
- Duplicate detection → `cross-reference.md`
- Dossier generation → `dossier.md` (references reply templates and endpoints)
- Platform-specific `gh` installation or authentication → `platform.md`

## Key Design Decisions

### One Template Per Conclusion

Each conclusion maps to exactly one reply template:

| Conclusion | Template |
|-----------|----------|
| valid (fixed) | `Fixed in <commit_sha>.` |
| invalid | `This suggestion doesn't apply because <reason>.` |
| already_fixed | `Already resolved in the current code — no changes needed.` |
| out_of_scope | `This is outside the scope of this PR. <follow-up>.` |
| needs_clarification | `Confirmed: <resolved direction>.` (direction known from Step 3) |
| conflict (not chosen) | `Thanks. We went with @other's approach for <reason>.` |

### Endpoint Selection by Comment Kind

| Comment kind | Endpoint | Key parameter |
|-------------|----------|---------------|
| inline | `repos/{owner}/{repo}/pulls/{pr}/comments` | `in_reply_to=<comment_id>` |
| review body | `repos/{owner}/{repo}/issues/{pr}/comments` | mention @author in body |
| top_level | `repos/{owner}/{repo}/issues/{pr}/comments` | — |

### Separate Replies for Duplicate Authors

When multiple reviewers flagged the same issue (merged duplicate), each reviewer gets their own reply with their own `in_reply_to` ID. The reply content is the same, but the API call is per author. This prevents GitHub from treating it as a single reply thread and ensures each reviewer gets a notification.
