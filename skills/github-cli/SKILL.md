---
name: GitHub CLI
description: >-
  Use when a task touches GitHub issues, pull requests, review comments,
  Actions runs/logs, releases, repository metadata, GitHub URLs, or GitHub API
  state from the terminal.
---

# GitHub CLI

## Overview

Use `gh` for GitHub state. GitHub issues, PRs, review comments, Actions runs, releases, repository metadata, and GitHub API reads are terminal operations, not generic web pages.

## Tool Routing Rule

When the user provides a GitHub URL or asks to read/manage GitHub state, use `gh` first:

| User target | Default command |
|-------------|-----------------|
| Issue URL or number | `gh issue view <url-or-number> --comments --json number,title,state,author,body,comments,labels,url` |
| PR URL, number, or branch | `gh pr view <url-or-number-or-branch> --comments --json number,title,state,author,body,comments,headRefName,baseRefName,url` |
| PR diff | `gh pr diff <pr>` |
| Actions run | `gh run view <run-id> --json status,conclusion,headSha,url` |
| Failed Actions logs | `gh run view <run-id> --log-failed` |
| Release | `gh release view <tag>` |

Do not use `webfetch` for GitHub issues, PRs, reviews, comments, checks, runs, releases, or API state when `gh` can read it. Use `webfetch` only for ordinary web content outside GitHub's CLI/API surface, or after `gh` proves the state is inaccessible.

## Use When

- the user gives a `github.com/.../issues/<N>` or `github.com/.../pull/<N>` URL
- you need to inspect or manage pull requests from the terminal
- you need to inspect or update issues without opening the browser
- you need to read or reply to GitHub comments or review comments
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
gh pr view 123 --comments --json number,title,state,author,body,comments,headRefName,baseRefName,url
gh pr diff 123
gh pr checks 123
gh pr checks 123 --watch

# Issues
gh issue list --state open --json number,title,state,labels,url
gh issue view 456 --comments --json number,title,state,author,body,comments,labels,url

# Actions
gh run list --limit 20
gh run view 789 --json status,conclusion,headSha,url
gh run view 789 --log-failed

# Releases
gh release list
gh release view v1.2.3
gh release create v1.2.3 --verify-tag --generate-notes

# API reads
gh api repos/{owner}/{repo}/issues/123 --method GET
gh api repos/{owner}/{repo}/issues/123/comments --method GET --paginate
```

## Common Workflows

1. Confirm auth and repo with `gh auth status` and `gh repo view`.
2. Read the current object first: `gh pr view`, `gh issue view`, `gh run view`, `gh release view`, or `gh api <endpoint> --method GET`.
3. Only then perform the write: review, edit, merge, close, trigger, or release.
4. Verify the write with a read command instead of repeating the write operation.

### GitHub URLs

- Issue URL: `gh issue view https://github.com/OWNER/REPO/issues/456 --comments`
- PR URL: `gh pr view https://github.com/OWNER/REPO/pull/123 --comments`
- Cross-repo without URL: add `-R OWNER/REPO` to `gh issue`, `gh pr`, `gh run`, or `gh release` commands.
- Prefer `--json` plus `--jq` when you need deterministic fields for reasoning.

### Pull Requests

- Inspect status: `gh pr status`
- Read details: `gh pr view 123 --comments --json number,title,state,author,body,comments,headRefName,baseRefName,url`
- Read diff: `gh pr diff 123`
- Read checks: `gh pr checks 123`
- Review: `gh pr review 123 --approve|--comment|--request-changes --body "..."`
- Merge carefully: `gh pr merge 123 --squash|--rebase|--merge --match-head-commit <sha>`

### Issues

- Read before editing: `gh issue view 456 --comments --json number,title,state,author,body,comments,labels,url`
- Edit metadata: `gh issue edit 456 --add-label bug --add-assignee @me`
- Comment: `gh issue comment 456 --body "Update"`

### Actions

- Inspect runs: `gh run list`
- Read run state: `gh run view 789 --json status,conclusion,headSha,url`
- Read failed logs first: `gh run view 789 --log-failed`
- Read full logs only when needed: `gh run view 789 --log`
- Retry or cancel only after inspection: `gh run rerun 789`, `gh run cancel 789`

### Releases

- Check existing releases first: `gh release list`
- Confirm the tag exists and points to the intended commit before publishing.
- Prefer `gh release create <tag> --verify-tag --generate-notes` unless custom notes are required.
- Add `--fail-on-no-commits` when duplicate/no-op releases should fail.

### GitHub API

- GET with no params: `gh api repos/{owner}/{repo}/issues/123 --method GET`
- GET with params: `gh api search/issues --method GET -f q='repo:OWNER/REPO is:open bug'`
- Paginate reads: `gh api repos/{owner}/{repo}/issues --method GET --paginate`
- POST/PATCH/DELETE only after a read proves the target and intended change.
- Remember: adding `-f` or `-F` fields makes `gh api` default to POST unless `--method GET` is explicit.

## Safety Checks

- Do not create a release until version numbers, tags, and branch state are verified.
- If the project uses multiple version files, read and compare them before tagging.
- Read the release back with `gh release view <tag>` after creation instead of re-running `gh release create`.
- Treat `gh api` write calls exactly like any other external side effect.
- Use `--method GET` to inspect state first.
- After `POST`, `PATCH`, or `DELETE`, verify with a follow-up read.
- If you are unsure whether a write succeeded, do not repeat it blindly.

## Gotchas

- `gh` operates against GitHub state, which may differ from your local branch or remotes.
- `--web` is useful for fast inspection, but terminal reads are better when you need deterministic verification.
- `gh api` is powerful enough to create duplicate side effects if you retry writes without reading state first.
- `gh api` switches to POST when field flags are present unless `--method GET` is explicit.
- Release and merge commands are high-impact; always confirm the target object immediately before running them.
