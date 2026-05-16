---
name: address-pr-comments
description: Address GitHub pull request review comments using gh CLI. Use when asked to process PR feedback, especially mixed human + AI bot reviews (for example CodeRabbit prompts), triage validity, apply fixes, and prepare concise responses with evidence.
---

# Address PR Comments

## Overview

Collect PR feedback with `gh`, classify AI/bot vs human comments, validate each comment against current code, implement only valid changes, and summarize what was addressed vs rejected.

## Workflow

Address PR comments in this order:

1. Resolve target PR (auto-detect from current branch by default).
2. Verify `gh` availability/auth.
3. Collect comments (top-level, reviews, inline).
4. Classify source (AI/bot vs human) AND classify intent (actionable vs informational).
5. Validate each actionable comment before changing code.
6. Apply fixes and run targeted checks.
7. Commit each resolved comment locally (no push).
8. Reply to ALL non-informational comments with outcome.
9. Summarize addressed/rejected items with rationale.

## 1. Resolve PR (Auto-Detect by Default)

**Always auto-detect PR from current branch first.** No need for the user to pass a PR number.

```bash
python3 ./scripts/list_comments.py --json
```

The script automatically calls `gh pr view --json number` to resolve the PR from the current branch. No `--pr` argument is needed unless you explicitly want to target a different PR.

If auto-detection fails (no PR open for the current branch), ask the user for the PR number or URL.

## 2. Verify GH CLI

```bash
gh --version
gh auth status
```

If missing or unauthenticated, stop and report the blocker clearly.

## 3. Collect Feedback

Use the helper script for normalized output:

```bash
python3 ./scripts/list_comments.py --pr <number> --json
```

The script aggregates:
- Top-level comments
- Review submissions
- Inline review comments from unresolved threads by default (including outdated unresolved threads)
- AI-prompt snippets when present in bot comments

To include resolved inline threads too:

```bash
python3 ./scripts/list_comments.py --pr <number> --json --include-resolved
```

## 4. Classify Source + Intent

**IMPORTANT**: Use the **full `body`** field from JSON output for classification, not just `excerpt`. The excerpt is truncated to 220 characters and may cut off the actual content of long review comments.

**Step A: Classify Source**

Prioritize:
1. Human reviewer blocking concerns
2. High-confidence AI comments with concrete evidence
3. Lint/style/nit comments

Treat bots as advisory. Do not apply suggestions blindly.

**Step B: Classify Intent — Actionable vs Informational**

For each comment, determine whether it requires action or reply:

| Intent | Examples | Must Reply? |
|--------|----------|-------------|
| **Actionable** | Change requests, bug reports, nitpicks, suggestions with code changes, questions asked by the reviewer | YES |
| **Informational** | LGTM, praise ("Nice work!", "👍", "+1"), FYI notes, link sharing, reviewer's own note-to-self | NO — skip |

Identifying informational comments:
- Comment body is only emoji / short praise (< 10 words without code suggestions)
- Comment is a simple approval sticker (e.g. "LGTM", "looks good", "ship it")
- Comment points to external references without requesting changes
- Comment is the reviewer documenting their own reasoning (not asking you to do anything)

When in doubt, treat as actionable.

## 5. Validate Before Fixing (Actionable Comments Only)

Skip informational comments. Validate only actionable comments.

Use the checklist in `references/validation-checklist.md`.

Mark each actionable comment as one of:
- `valid`
- `invalid`
- `already_fixed`
- `out_of_scope`
- `needs_clarification`

For AI bot comments containing a "Prompt for AI Agents" block, parse and verify each requested change against current files and repo conventions before editing.

## 6. Implement + Verify

Apply fixes one validated comment at a time.

Run checks relevant to changed files only, scoped to the modified paths (e.g., type checks, linting, tests).

## 7. Commit Each Resolved Comment (No Push)

For every `valid` comment you resolve:

1. Stage only the files needed for that single comment.
2. Examine recent commits (`git log --oneline -10`) to understand the repository's commit message style. If a commit message generation skill is installed, use it. Otherwise, write a concise commit message from the staged diff that follows the same conventions.
3. Create exactly one local commit for that resolved comment.
4. Do **not** push.

Rules:
- Do not combine multiple resolved comments into one commit unless technically inseparable.
- If inseparable, note all linked comment URLs in your final report for that commit.
- Do not commit comments marked `invalid`, `already_fixed`, `out_of_scope`, or `needs_clarification`.

## 8. Reply to All Non-Informational Comments (MANDATORY)

After all fixes are committed, **reply to EVERY actionable comment** to close the loop. Skip informational comments only.

### Reply by Comment Kind

Each comment from `list_comments.py --json` has a `kind` and an `id`. Use these to construct the correct reply.

**JSON field → API parameter mapping:**

| JSON field | Used as | Applies to kind |
|------------|---------|-----------------|
| `id` | `in_reply_to` (for inline) or reference in body | all |
| `path` | `-F path=` | `inline` |
| `line` | `-F line=` | `inline` |
| `author` | `@<author>` in reply body | `review`, `top_level` |

**For inline review comments** (`kind: "inline"`) — reply with `in_reply_to` to thread under the original review comment:

```bash
gh api repos/{owner}/{repo}/pulls/{pr}/comments --method POST \
  -F body="Your reply text here" \
  -F commit_id=$(git rev-parse HEAD) \
  -F path="path/to/file.go" \
  -F line=<line_number> \
  -F side=RIGHT \
  -F in_reply_to=<comment_id>
```

- `<comment_id>` comes from the JSON output's `id` field for this inline comment.
- `side=RIGHT` for comments on the PR's diff side (the new code).
- `commit_id` must be a valid commit SHA on the PR branch.
- Including both positioning fields AND `in_reply_to` ensures the reply appears threaded under the original comment, NOT as a standalone comment on the same line.

**For review body comments** (`kind: "review"`) — post a PR conversation comment:

```bash
gh api repos/{owner}/{repo}/issues/{pr}/comments --method POST \
  -F body="@<reviewer_login> Thanks for the review. <outcome>."
```

Review bodies appear as timeline events and don't support direct threading. Posting an issue comment that mentions the reviewer keeps the conversation connected.

**For top-level PR comments** (`kind: "top_level"`) — post a PR conversation comment:

```bash
gh api repos/{owner}/{repo}/issues/{pr}/comments --method POST \
  -F body="@<author_login> <outcome>."
```

### Reply Templates by Outcome

Use these templates for concise, professional replies:

| Outcome | Reply Template |
|---------|---------------|
| `valid` (fixed) | `Fixed in <commit_sha>.` |
| `invalid` | `This suggestion doesn't apply because <brief reason>.` |
| `already_fixed` | `Already resolved in the current code — no changes needed.` |
| `out_of_scope` | `This is outside the scope of this PR. <Optional: suggest follow-up>.` |
| `needs_clarification` | `Could you clarify <specific question>?` |

**Rules for replies:**
- Keep replies short (1-2 sentences max).
- Always mention the commit SHA for fixed items.
- Do NOT reply to informational comments (LGTM, praise, FYI, emoji-only).
- If a comment already has a reply thread from you, append — don't create a duplicate.
- **CRITICAL for inline comments**: Always include `in_reply_to=<comment_id>`. Without it, your reply becomes a standalone comment on the same diff line instead of being threaded under the original review comment.
- Only use `in_reply_to` for `kind: "inline"` comments. For `kind: "review"` and `kind: "top_level"`, post a PR issue comment instead.

## 9. Report Back

Provide:
- Addressed comments (with file references and commit hashes)
- Rejected comments (with reason)
- Any unclear comments that need reviewer clarification
- What checks were run and results
- Reply status: which comments were replied to and which were skipped (informational)

## Quick Commands

```bash
# Auto-detect PR from current branch (default — no --pr needed)
python3 ./scripts/list_comments.py --json

# Manual PR override
python3 ./scripts/list_comments.py --pr <number> --json

# Include resolved inline threads
python3 ./scripts/list_comments.py --json --include-resolved

# Reply to an inline review comment (threaded reply via in_reply_to)
gh api repos/{owner}/{repo}/pulls/{pr}/comments --method POST \
  -F body="Fixed in <sha>." \
  -F commit_id=$(git rev-parse HEAD) \
  -F path="path/to/file.go" \
  -F line=<line> \
  -F side=RIGHT \
  -F in_reply_to=<comment_id>

# Reply to a review body or top-level PR comment (conversation comment)
gh api repos/{owner}/{repo}/issues/{pr}/comments --method POST \
  -F body="@<reviewer> Fixed in <sha>."

# Per-comment local commit workflow (no push)
git add <files-for-one-comment>
git diff --staged --stat
git commit -m "<conventional-commit-message>"
# DO NOT: git push
```
