---
name: GitHub CLI
description: >-
  Use when a task needs GitHub operations from the terminal, especially pull
  request review, issue triage, workflow inspection, or release creation with
  gh.
---

# GitHub CLI

## Overview

Use `gh` when the task is about GitHub state, not just local git state. Prefer concise read operations first, then perform writes only after you have confirmed the target repository, branch, PR, issue, or release you are about to modify.

## Use When

- you need to inspect or manage pull requests from the terminal
- you need to inspect or update issues without opening the browser
- you need to inspect GitHub Actions runs or logs
- you need to create or publish a release
- you need GitHub API access via `gh api`

## Quick Reference

```bash
# Verify auth and current repo context
gh auth status
gh repo view

# Pull requests
gh pr status
gh pr view 123 --web
gh pr diff 123
gh pr checks 123 --watch

# Issues
gh issue list
gh issue view 456

# Actions
gh run list
gh run view 789 --log

# Releases
gh release list
gh release view v1.2.3
gh release create v1.2.3 --generate-notes
```

## Common Workflows

1. Confirm auth and repo with `gh auth status` and `gh repo view`.
2. Read the current object first: `gh pr view`, `gh issue view`, `gh run view`, `gh release view`, or `gh api GET ...`.
3. Only then perform the write: review, edit, merge, close, trigger, or release.
4. Verify the write with a read command instead of repeating the write operation.

### Pull Requests

- Inspect status: `gh pr status`
- Read details: `gh pr view 123`
- Read diff: `gh pr diff 123`
- Review: `gh pr review 123 --approve|--comment|--request-changes`
- Merge carefully: `gh pr merge 123 --squash|--rebase|--merge`

### Issues

- Read before editing: `gh issue view 456`
- Edit metadata: `gh issue edit 456 --add-label bug --add-assignee @me`
- Comment: `gh issue comment 456 --body "Update"`

### Actions

- Inspect runs: `gh run list`
- Read logs: `gh run view 789 --log`
- Retry or cancel only after inspection: `gh run rerun 789`, `gh run cancel 789`

### Releases

- Check existing releases first: `gh release list`
- Confirm the tag exists and points to the intended commit before publishing.
- Prefer `gh release create <tag> --generate-notes` unless custom notes are required.

## Safety Checks

- Do not create a release until version numbers, tags, and branch state are verified.
- If the project uses multiple version files, read and compare them before tagging.
- Read the release back with `gh release view <tag>` after creation instead of re-running `gh release create`.
- Treat `gh api` write calls exactly like any other external side effect.
- Use `GET` to inspect state first.
- After `POST`, `PATCH`, or `DELETE`, verify with a follow-up read.
- If you are unsure whether a write succeeded, do not repeat it blindly.

## Gotchas

- `gh` operates against GitHub state, which may differ from your local branch or remotes.
- `--web` is useful for fast inspection, but terminal reads are better when you need deterministic verification.
- `gh api` is powerful enough to create duplicate side effects if you retry writes without reading state first.
- Release and merge commands are high-impact; always confirm the target object immediately before running them.
