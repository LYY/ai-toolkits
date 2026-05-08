---
name: address-pr-comments
description: Address GitHub pull request review comments using gh CLI. Use when asked to process PR feedback, especially mixed human + AI bot reviews (for example CodeRabbit prompts), triage validity, apply fixes, and prepare concise responses with evidence.
---

# Address PR Comments

## Overview

Collect PR feedback with `gh`, classify AI/bot vs human comments, validate each comment against current code, implement only valid changes, and summarize what was addressed vs rejected.

## Workflow

Address PR comments in this order:

1. Resolve target PR.
2. Verify `gh` availability/auth.
3. Collect comments (top-level, reviews, inline).
4. Classify source (AI/bot vs human).
5. Validate each comment before changing code.
6. Reply to inline comments with proper positioning fields.
7. Apply fixes and run targeted checks.
8. Commit each resolved comment locally (no push).
9. Summarize addressed/rejected items with rationale.

## 1. Resolve PR

If user did not provide a PR number, infer from current branch:

```bash
gh pr view --json number,title,url
```

If that fails, ask the user for PR number or URL.

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

## 4. Classify + Prioritize

Prioritize:
1. Human reviewer blocking concerns
2. High-confidence AI comments with concrete evidence
3. Lint/style/nit comments

Treat bots as advisory. Do not apply suggestions blindly.

## 5. Validate Before Fixing

Use the checklist in `references/validation-checklist.md`.

Mark each comment as one of:
- `valid`
- `invalid`
- `already_fixed`
- `out_of_scope`
- `needs_clarification`

For AI bot comments containing a "Prompt for AI Agents" block, parse and verify each requested change against current files and repo conventions before editing.

## 6. Reply to Inline Comments

To reply to an inline review comment in a way that GitHub displays as a threaded reply (not an orphaned comment), you MUST provide positioning fields. Do NOT use `in_reply_to`.

```bash
gh api repos/{owner}/{repo}/pulls/{pr}/comments --method POST \
  -F body="Your reply text here" \
  -F commit_id=$(git rev-parse HEAD) \
  -F path="path/to/file.go" \
  -F line=<line_number> \
  -F side=RIGHT
```

Use `side=RIGHT` for comments on the PR's diff side (the new code). The `commit_id` must be a valid commit SHA on the PR branch.

To resolve a thread after replying, use:

```bash
gh api repos/{owner}/{repo}/pulls/{pr}/comments/{comment_id}/replies --method PATCH \
  -F body="Resolved."
```

Or resolve via the review thread:

```bash
gh api repos/{owner}/{repo}/pulls/{pr}/reviews/{review_id}/threads/{thread_id} \
  --method PATCH -F resolved=true
```

## 7. Implement + Verify

Apply fixes one validated comment at a time.

Run checks relevant to changed files only, scoped to the modified paths (e.g., type checks, linting, tests).

## 8. Commit Each Resolved Comment (No Push)

For every `valid` comment you resolve:

1. Stage only the files needed for that single comment.
2. Examine recent commits (`git log --oneline -10`) to understand the repository's commit message style. If a commit message generation skill is installed, use it. Otherwise, write a concise commit message from the staged diff that follows the same conventions.
3. Create exactly one local commit for that resolved comment.
4. Do **not** push.

Rules:
- Do not combine multiple resolved comments into one commit unless technically inseparable.
- If inseparable, note all linked comment URLs in your final report for that commit.
- Do not commit comments marked `invalid`, `already_fixed`, `out_of_scope`, or `needs_clarification`.

## 9. Report Back

Provide:
- Addressed comments (with file references and commit hashes)
- Rejected comments (with reason)
- Any unclear comments that need reviewer clarification
- What checks were run and results

## Quick Commands

```bash
# Current branch PR
gh pr view --json number,title,url

# Structured comment dump
python3 ./scripts/list_comments.py --json

# Structured comment dump for a specific PR
python3 ./scripts/list_comments.py --pr <number> --json

# Include resolved inline threads
python3 ./scripts/list_comments.py --pr <number> --json --include-resolved

# Reply to an inline comment (MUST use positioning fields, NOT in_reply_to)
gh api repos/{owner}/{repo}/pulls/{pr}/comments --method POST \
  -F body="..." \
  -F commit_id=$(git rev-parse HEAD) \
  -F path="path/to/file.go" \
  -F line=<line> \
  -F side=RIGHT

# Per-comment local commit workflow (no push)
git add <files-for-one-comment>
git diff --staged --stat
git commit -m "<conventional-commit-message>"
# DO NOT: git push
```
