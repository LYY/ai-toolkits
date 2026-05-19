---
name: address-pr-comments
description: (Archived) FROZEN — This skill is no longer maintained. Use address-pr-comments-review instead. Address GitHub pull request review comments using gh CLI. Use when asked to process PR feedback, especially mixed human + AI bot reviews (for example CodeRabbit prompts), triage validity, apply fixes, and prepare concise responses with evidence.
---

⚠️ ARCHIVED — This skill is frozen. Use address-pr-comments-review instead.

# Address PR Comments

## Overview

Collect PR feedback with `gh`, classify AI/bot vs human comments, validate each comment against current code, implement only valid changes, and summarize what was addressed vs rejected.

## Workflow

Address PR comments in this order:

1. Identify the PR (auto-detect from current branch via `gh pr view`).
2. Verify `gh` CLI is installed and authenticated.
3. Collect all comments (top-level, reviews, inline) via `list_comments.py`.
4. Classify each comment: source (AI/bot vs human) and intent (actionable vs informational).
5. Validate each actionable comment against current code before making changes.
6. Apply fixes one comment at a time, run targeted checks per change.
7. Commit each resolved `valid` comment locally (no push).
8. Reply to every actionable comment with outcome using `gh api`.
9. Summarize all addressed, rejected, and skipped items with rationale.

## Prerequisites

- `gh` CLI installed and authenticated (`gh auth status` must pass)
- Current git branch has an open PR, or you know the PR number

## Error Recovery

| Failure | Response |
|---------|----------|
| `gh` not installed / not authenticated | Stop. Tell user to run `gh auth login`. |
| `list_comments.py` fails (network, API rate limit) | Retry once after 5 seconds. If still fails, report the error and ask user if they want to continue with manual PR number override. |
| PR not found (wrong number, closed, merged) | Report the specific gh error. Ask user to verify PR number and state. |
| **Zero comments on PR** | Report: "PR has no comments — nothing to review." |
| Script returns empty JSON | Verify `gh pr view` works manually. Check that the branch has an open PR. |

## 1. Resolve PR (Auto-Detect by Default)

**Always auto-detect PR from current branch first.** No need for the user to pass a PR number.

```bash
python3 ./scripts/list_comments.py --json
```

The script automatically calls `gh pr view --json number` to resolve the PR from the current branch. No `--pr` argument is needed unless you explicitly want to target a different PR.

If auto-detection fails (no PR open for the current branch), ask the user for the PR number or URL. For cross-repo access (when not in the repo directory), use `--repo owner/name`.

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
- Inline review comments from unresolved threads by default (unresolved threads that are outdated against the current diff are still included)
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

**Already-replied detection**: Comments with `has_replies: true` in the JSON output already have a human reply (detected via thread analysis for inline comments, or time-based heuristic for review body / top-level comments). Classify these as `already_replied` — skip, no action needed. User can override by reclassifying as another conclusion.

## 5. Validate Before Fixing (Actionable Comments Only)

Skip informational comments. Validate only actionable comments.

Use the checklist in `references/validation-checklist.md` (in this skill's directory).

Mark each actionable comment as one of:
- `valid`
- `invalid`
- `already_fixed`
- `already_replied` (has human reply — skip, no action needed)
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
- Do not commit comments marked `invalid`, `already_fixed`, `already_replied`, `out_of_scope`, or `needs_clarification`.

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
| `already_replied` | (Skip — already has a human reply) |
| `out_of_scope` | `This is outside the scope of this PR. <Optional: suggest follow-up>.` |
| `needs_clarification` | `Could you clarify <specific question>?` (async — when reviewer replies, invoke this skill again; `has_replies` detection surfaces their response and skips already-handled items) |

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

**Note on `needs_clarification`**: These comments are inherently asynchronous. The agent replies with a clarification question, then the reviewer responds later. To process reviewer replies, re-run this skill — the `has_replies` detection will skip already-replied comments and surface only new reviewer responses. Mark the original `needs_clarification` item as resolved once the reviewer provides direction.

## Quick Commands

```bash
# Auto-detect PR from current branch
python3 ./scripts/list_comments.py --json

# Cross-repo PR
python3 ./scripts/list_comments.py --repo owner/name --pr <number> --json
```

Other variants (`--include-resolved`) and reply commands are shown inline in their respective sections above.
