---
name: github-cli
description: >-
  Use when a task touches GitHub issues, pull requests, comments, Actions,
  releases, repository metadata, or GitHub API state. Route remote state
  through gh with deterministic reads and explicit write verification.
---

# GitHub CLI

## Route GitHub State Through `gh`

Use `gh` first for GitHub issues, pull requests, discussions, reviews, Actions,
releases, repository metadata, and API state. Use a browser or web fetch only
when `gh` cannot access the required state. Do not use web tools when `gh` can
read the object.

Resolve targets explicitly:

- A GitHub URL identifies its host, repository, and object. Pass the URL to the
  matching high-level command.
- Without a URL, use `-R OWNER/REPO` or `--repo [HOST/]OWNER/REPO` on high-level
  commands. Do not assume the current repository when another target is known.
- For `gh api`, use an explicit `repos/OWNER/REPO/...` endpoint when no URL or
  current repository should be assumed. Do not rely on `{owner}` or `{repo}`
  substitution in that case.
- Prefer explicit object numbers, URLs, and commit SHAs. Avoid implicit current
  branch or current PR selection when more than one target is plausible.

High-level formatting semantics:

- On high-level subcommands that expose `--jq`, `--jq '<expression>'` requires
  `--json <fields>`; check `gh <command> --help` when unsure. Use `--json` alone
  when field selection is enough.
- `gh api` has no `--json` flag. Apply `--jq '<expression>'` directly to its
  JSON response, or use `--template`.

## Structured Reads

Use the smallest read that answers the question. Add `--json <fields>` when
the result will be parsed or compared.

| Need | Read command |
| --- | --- |
| Issue | `gh issue view <number-or-url> --comments --json number,title,state,author,body,comments,labels,url` |
| Pull request | `gh pr view <number-or-url> --comments --json number,title,state,author,body,headRefName,headRefOid,baseRefName,reviews,comments,url` |
| PR diff / checks | `gh pr diff <number-or-url>`; `gh pr checks <number-or-url> --json name,state,bucket,link` |
| Action run / logs | `gh run view <run-id> --json status,conclusion,headSha,url`; add `--log-failed` or `--log` for logs |
| Release | `gh release view <tag> --json tagName,targetCommitish,isDraft,isPrerelease,publishedAt,url` |
| API | `gh api repos/OWNER/REPO/<endpoint> --method GET`, add `--paginate` for collections |

`gh pr checks` is one-shot by default. Pending checks return exit code `8`.
Use `--watch` only when the user explicitly asks to wait for completion.

## PR Discussions And Reviews

Keep three GitHub comment surfaces separate:

- PR discussion comments are issue-style comments. Read them with
  `gh pr view <pr> --comments` or the `comments` JSON field.
- Review submissions are approve, request-changes, or review-level comments.
  Read them through `gh pr view <pr> --json reviews,latestReviews`.
- Inline review comments attach to a diff location. Read them with:
  `gh api repos/OWNER/REPO/pulls/PR/comments --method GET --paginate`

Use `gh pr review` only for a review submission. Use `gh pr comment PR` for a
PR discussion comment. Use the API endpoint for inline review comments.

## Write Protocol

Any command that changes remote state requires explicit user authorization for
the exact operation and target.

1. Read the target immediately before writing. Confirm repository, object number
   or tag, current state, and any relevant head SHA or existing content.
2. Choose the route matching the object surface. Write once with explicit target
   and parameters.
3. Read back through the route that proves the write. Never repeat a write to
   discover whether an earlier write succeeded. If success is uncertain, read
   first and retry only after confirming that no write occurred.

For `gh api`, the default method is `GET` without parameters and `POST` when
`-f/--raw-field` or `-F/--field` is present. Use explicit `--method GET` when
fields are query parameters, for example:

```bash
gh api search/issues --method GET -f q='repo:OWNER/REPO is:open bug'
```

After writes, use route-specific read-back:

- Issue edit or comment: `gh issue view ISSUE --comments --json state,comments,labels`
- PR discussion comment: `gh pr view PR --comments --json comments`
- Review submission: `gh pr view PR --json reviews,latestReviews`
- API mutation: `gh api repos/OWNER/REPO/<same-resource> --method GET`

## High-Impact Writes

Merge and release operations need an extra target check immediately before the
write.

- Merge: read `headRefOid` with `gh pr view PR --json state,headRefOid`. Pass
  that exact SHA as `--match-head-commit <sha>` to `gh pr merge`, then read back
  `state,mergedAt,mergeCommit,headRefOid` with `gh pr view`.
- Release: read `gh api repos/OWNER/REPO/git/ref/tags/TAG --method GET` and verify
  the remote tag ref exists and represents the intended target. If object type is
  `tag`, read `gh api repos/OWNER/REPO/git/tags/<object-sha> --method GET` before
  determining the underlying commit. Create with `gh release create TAG --verify-tag`,
  then read back with `gh release view TAG`. Do not create when tag or target is unclear.

Treat reruns, retries, merge, release creation, issue edits, comments, review
submissions, and API mutations as writes. The read, authorization, single write,
and route-specific read-back rules apply to each.
