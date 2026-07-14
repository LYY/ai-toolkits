# Platform Integration

Runtime commands, paths, cleanup, and the `list_comments.py` script contract. Artifacts are generic Markdown files. Handoff targets any capable executor.

## Prerequisites

Before running any collection commands:

1. **`gh` CLI installed**: Verify with `gh --version`.
2. **Authenticated**: Run `gh auth status`. Must show "Logged in to github.com".
3. **PR context**: Current git branch must have an open PR, or you must provide `--pr <N>` and optionally `--repo owner/name`.

## Step 0: Current Checkout and PR Verification

Run this protocol before Comment Collection. Its completion criterion is strict: `TARGET_WORKTREE_ROOT` is an absolute canonical repo root for the current checkout, branch/PR identity has no unresolved mismatch, and `gh pr view` succeeds from that root. If any check fails, Stop before collection.

### 0a. Resolve Current Git Root

Start from the current directory and resolve the repo root:

```bash
git rev-parse --show-toplevel
git rev-parse --git-dir
git rev-parse --git-common-dir
git rev-parse --show-superproject-working-tree
```

Use the `--show-toplevel` output as the target checkout root. Canonicalize it to an absolute physical path and assign it:

```bash
TARGET_WORKTREE_ROOT="$(cd "$(git rev-parse --show-toplevel)" && pwd -P)"
```

Submodule guard: if `git rev-parse --show-superproject-working-tree` prints a path, the current directory is inside a submodule. Stop and ask which repository root should be reviewed. Don't collect comments from a submodule by accident.

### 0b. Detect Linked Worktrees

List linked worktrees from the current checkout's repository:

```bash
git -C "$TARGET_WORKTREE_ROOT" worktree list --porcelain
```

This is the target-root form of `git worktree list --porcelain`; run it against `TARGET_WORKTREE_ROOT` so linked worktrees are interpreted in the same repository.

Interpretation:

| Result | Action |
|--------|--------|
| One `worktree` entry | Continue with `TARGET_WORKTREE_ROOT`. |
| Multiple `worktree` entries and current root is one of them | Continue with the current root. Mention the other linked worktrees as context, but do not ask for confirmation yet. |
| Multiple `worktree` entries and current root is not listed | Stop and ask the user to select one listed path. |
| Current entry has `detached` | Treat detached HEAD as abnormal for this skill. Stop unless the user explicitly confirms that detached checkout and provides `--repo owner/name --pr <N>`. |

When multiple linked worktrees exist, state the checkout being used as: absolute path, branch or detached state, and HEAD. If asking for selection, show only each linked worktree's absolute path, branch or detached state, and HEAD. Don't instruct the user to create, switch, prune, or delete worktrees.

### 0c. Record Current Checkout Identity

From the bound checkout, record these facts:

```bash
git -C "$TARGET_WORKTREE_ROOT" status --short --branch
git -C "$TARGET_WORKTREE_ROOT" rev-parse HEAD
git -C "$TARGET_WORKTREE_ROOT" remote -v
```

If multiple linked worktrees exist, state the bound checkout's absolute path, branch or detached state, and HEAD before running any PR query. This is informational unless a hard stop condition below applies.

### 0d. Verify PR From Bound Checkout

Run PR detection from `TARGET_WORKTREE_ROOT`, not from the agent's original current directory:

```bash
gh pr view --json number,url,headRefName,baseRefName
```

For explicit PR input, run the same validation from the bound checkout:

```bash
gh pr view <N> --repo owner/name --json number,url,headRefName,baseRefName
```

Explicit `--pr <N>` and `--repo owner/name` do not bypass validation against the bound checkout. The bound checkout still defines the local files used for classification and verification.

After `gh pr view` succeeds, compare the PR head branch with the bound checkout branch:

```bash
git -C "$TARGET_WORKTREE_ROOT" branch --show-current
```

If the current branch is non-empty and does not match `headRefName`, stop before collection. Explain the mismatch and ask the user whether to rerun from the matching worktree or explicitly continue with the current checkout. Do not collect comments while the branch/PR identity is unresolved.

Hard stop rules before collection. These are hard stop conditions, not warnings:

- Stop if `TARGET_WORKTREE_ROOT` is unset, relative, or not a repo root.
- Stop if a submodule root might be mistaken for the target repo.
- Stop if the bound checkout is detached and the user hasn't explicitly confirmed detached HEAD plus `--repo owner/name --pr <N>`.
- Stop if `gh pr view` fails from `TARGET_WORKTREE_ROOT`, even when explicit PR arguments were provided.
- Stop if PR `headRefName` and the current branch disagree and the user hasn't explicitly resolved the mismatch.

## Comment Collection

All comment collection uses `scripts/list_comments.py` (vendored within the skill, no Python package dependencies). The script lives at `<skill-dir>/scripts/list_comments.py`, where `<skill-dir>` is the directory containing `SKILL.md` — the same base path from which you loaded this file, minus the `references/` prefix.

### Command

```bash
# Resolve SCRIPT to the full path relative to SKILL.md's directory:
# SCRIPT="<skill-dir>/scripts/list_comments.py"

# Auto-detect PR from bound checkout branch
(cd "$TARGET_WORKTREE_ROOT" && python3 "$SCRIPT" --json)

# Explicit PR number
(cd "$TARGET_WORKTREE_ROOT" && python3 "$SCRIPT" --pr <N> --json)

# Cross-repo after bound checkout validation
(cd "$TARGET_WORKTREE_ROOT" && python3 "$SCRIPT" --repo owner/name --pr <N> --json)

# Include resolved threads
(cd "$TARGET_WORKTREE_ROOT" && python3 "$SCRIPT" --include-resolved --json)
```

### Flags

| Flag | Required | Description |
|------|----------|-------------|
| `--json` | Yes | Output as JSON (machine-readable). Always required. |
| `--pr <N>` | No | PR number. Auto-detected from current branch if omitted. |
| `--repo owner/name` | No | Repository. Auto-detected if omitted. Required for cross-repo access. |
| `--include-resolved` | No | Include resolved/outdated threads. Excluded by default. |

### Auto-Detection

When `--pr` is omitted, the script runs `gh pr view` to detect the PR from the current branch. This requires an open PR for the current branch. If auto-detection fails, provide `--pr` explicitly.

Always run the script from `TARGET_WORKTREE_ROOT`. `--repo owner/name --pr <N>` selects the remote PR, but it doesn't change the local checkout used for reading files and checking comment locations.

## Script JSON Contract

The script emits a JSON array of normalized comment objects. Each object represents a single PR feedback item (inline, review, or top_level).

### Common Fields (All Output Kinds)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `kind` | string | yes | One of: `inline`, `review`, `top_level` |
| `id` | integer | yes | GitHub comment/review ID (used for `in_reply_to` in gh API) |
| `author` | string | yes | Author login. May be `null` (ghost account). |
| `is_ai` | boolean | yes | `true` if author is a known bot/AI reviewer |
| `body` | string | yes | Full comment body text (may be empty string). **Authoritative for classification — `excerpt` is truncated and must not be used.** |
| `excerpt` | string | yes | Truncated body (~220 chars). Not authoritative for classification. |
| `ai_prompts` | string | yes | Extracted AI prompt blocks from the body. Empty string if none found. |

### Timestamp and URL Fields

Timestamp and URL fields vary by output kind:

| Field | Applies to | Required | Description |
|-------|-----------|----------|-------------|
| `created_at` | inline, top_level | yes (when present) | ISO 8601 timestamp of comment creation. Absent for `review` kind. |
| `submitted_at` | review | yes (when present) | ISO 8601 timestamp of review submission. Only present for `kind=review`. |
| `url` | inline, top_level | yes (when present) | GitHub URL for the comment. Absent for `review` kind. |

### Thread Metadata Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `has_replies` | boolean | yes | `true` if the thread has at least one non-AI reply. Primary signal for `already_replied` classification. |
| `thread_resolved` | boolean | yes (inline only) | `true` if the thread was marked resolved in GitHub UI. Weak signal — NOT evidence of fix-state. Only present for `kind=inline`. |
| `thread_outdated` | boolean | yes (inline only) | `true` if the diff context shifted since the comment was posted. NOT evidence of fix-state — triggers mandatory code verification. Only present for `kind=inline`. |

### Inline-Specific Fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `path` | string | no (inline only) | File path relative to repo root. Only present when `kind=inline`. |
| `line` | integer | no (inline only) | Line number in the file. Only present when `kind=inline`. |

These fields are absent for `review` and `top_level` kinds.

### Review-Specific Fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `state` | string | yes (review only) | Review state (e.g. `APPROVED`, `CHANGES_REQUESTED`, `COMMENT`). Only present when `kind=review`. |

### Field Usage by Protocol

| Protocol File | Key Fields Consumed |
|---------------|---------------------|
| `classify.md` | `author`, `is_ai`, `body`, `has_replies`, `thread_outdated`, `thread_resolved`, `path`, `line`, `kind` |
| `cross-reference.md` | `has_replies`, `kind`, `path`, `line`, `id`, `author` |
| `dossier-output.md` | `id`, `author`, `kind`, `path`, `line`, `url` |
| `interaction.md` | `id`, `author`, `kind`, `path`, `line`, `url` |

## Artifact Path & Timestamp

After comments are collected and processed, generated artifacts are written to user-local state by default:

```
~/.local/state/ai-toolkits/pr-comments/<owner>__<repo>/pr-<N>/review-dossier-<TIMESTAMP>.md
~/.local/state/ai-toolkits/pr-comments/<owner>__<repo>/pr-<N>/direct-fix-<TIMESTAMP>.md
```

- `<owner>__<repo>`: GitHub repository with `/` replaced by `__`
- `<N>`: PR number
- `<TIMESTAMP>`: formatted as `YYYYMMDD-HHMMSS` using `date +%Y%m%d-%H%M%S`
- Directory is created automatically if it does not exist

`TARGET_WORKTREE_ROOT` still binds local code reads, git commands, and PR identity checks. It does not define the default artifact directory.

### artifact_dir Override

If the user provides `artifact_dir=<path>`, write artifacts there instead of the default state directory and use that path consistently in handoff messages.

Rules:

- Do not edit root `.gitignore`, `.git/info/exclude`, or global gitignore.
- Do not default to `.agent` or any repo-local directory.
- If `artifact_dir` is inside the repository and is not ignored, warn that artifacts may appear in `git status`; continue only if the user accepts.
- If the user explicitly chooses an artifact path like `notepads/pr-<N>-dossier/`, treat it as an optional artifact location, not as the default.

### Timestamp Format

```bash
date +%Y%m%d-%H%M%S
```

Example: `20260115-143022` for January 15, 2026 at 14:30:22.

### Directory Creation

```bash
mkdir -p "$HOME/.local/state/ai-toolkits/pr-comments/<owner>__<repo>/pr-<N>/"
```

## Handoff

After an artifact is saved, place the complete applicable handoff block in the current user-visible final response with the actual artifact path and actual values. Use the chosen artifact path, whether default or `artifact_dir` override.

### Dossier Handoff

````text
Review Dossier saved to:
<ARTIFACT_PATH>

Generic executor prompt:

```markdown
Read this PR comment review artifact:

<ARTIFACT_PATH>

Execute it as a PR review work package. Follow the Execution Contract exactly: apply Section A code changes, run listed verification, commit if requested by the operator, reply to every required PR comment, and verify posted replies by read-back. Do not repeat POST requests for verification.
```

Executor handoff prompt:

```markdown
Read this PR comment review artifact:

<ARTIFACT_PATH>

Generate an execution plan. Preserve every reply task from the artifact:
- code changes before replies
- targeted verification before commit
- commit SHA included in Section A replies
- PR comment replies posted through the listed endpoints
- read-back verification after posting replies
Ask me before planning if any task is ambiguous.
```

After execution plan is generated, pass it to your executor along with `worktree_path=<TARGET_WORKTREE_ROOT>` as the target checkout.

Cleanup target after verified execution:
`~/.local/state/ai-toolkits/pr-comments/<owner>__<repo>/pr-<N>/`
````

## Direct Fix Brief Handoff

After a Direct Fix Brief is saved, place the complete applicable handoff block in the current user-visible final response: the actual brief path, direct execution prompt, and cleanup target.

````text
Direct Fix Brief saved to:
<ARTIFACT_PATH>

Direct execution prompt:

```markdown
Read and execute this Direct Fix Brief:

<ARTIFACT_PATH>

Complete the exact code change, run the listed verification, commit if requested by the operator, post the required PR comment reply, and verify the reply by read-back. Do not expand scope beyond the brief.
```

Cleanup target after verified execution:
`~/.local/state/ai-toolkits/pr-comments/<owner>__<repo>/pr-<N>/`
````

## Artifact Cleanup

Cleanup commands manage disposable files created under the default state root. They route before the normal review workflow.

### Current PR Cleanup

Trigger:

```text
/address-pr-comments-review cleanup
/address-pr-comments-review cleanup --repo owner/repo --pr <N>
/address-pr-comments-review cleanup --artifact-dir <path>
/address-pr-comments-review cleanup --force
```

#### `--force` flag

Without `--force`, only artifacts in `verified-complete` state are eligible for cleanup. Cleanup of `pending`, `in-progress`, or `blocked` artifacts is refused.

The `--force` flag overrides the state gate: it includes force-required artifacts in the candidate list, allowing cleanup of artifacts in any state (`pending`, `in-progress`, `blocked`, or `verified-complete`). Force mode requires two explicit confirmations:

1. **First confirmation**: operator acknowledges the artifact state (`pending`, `in-progress`, or `blocked`) and the risk of cleaning up incomplete work.
2. **Second confirmation**: operator confirms the exact artifact path(s) to delete.

If no artifact exists in a force-required state, `--force` has no effect and cleanup proceeds as normal.

Behavior:

1. If `--artifact-dir <path>` is provided, target that explicit path and skip PR inference.
2. If `--repo` and `--pr` are omitted, run the minimal checkout binding and PR verification from Step 0a and 0d before inference. Use `TARGET_WORKTREE_ROOT` and `gh pr view` from that root. If inference fails, ask for `--repo owner/repo --pr <N>`.
3. Default target: `~/.local/state/ai-toolkits/pr-comments/<owner>__<repo>/pr-<N>/`.
4. Check artifact state. Without `--force`, refuse cleanup if state is not `verified-complete`. With `--force`, include non-verified-complete artifacts in the candidate list.
5. List exact files/directories that will be deleted, including artifact state for each.
6. Ask for confirmation before deleting. With `--force`, require two confirmations as described above.
7. Delete the PR artifact directory after confirmation.
8. If the parent `<owner>__<repo>/` directory is empty, remove it too.

Safety rules:

- Do not delete repo-local `artifact_dir` outputs unless the user explicitly passes `--artifact-dir <path>`.
- Do not delete `.agent` or any repo path during default cleanup.
- Do not post replies, collect comments, classify, or generate artifacts during cleanup.
- If no artifacts exist, report `no artifacts found`.
- Without `--force`, refuse cleanup of non-verified-complete artifacts.
- With `--force`, require two confirmations before deleting non-verified-complete artifacts.

### Cleanup All

Trigger:

```text
/address-pr-comments-review cleanup-all
/address-pr-comments-review cleanup-all --dry-run
/address-pr-comments-review cleanup-all --older-than 7d
```

Behavior:

1. Scan `~/.local/state/ai-toolkits/pr-comments/` for `<owner>__<repo>/pr-<N>/` directories.
2. Group preview by repository and PR.
3. Show total repo count, PR count, file count, and size.
4. If `--older-than <age>` is present, include only PR artifact directories older than that age. Supported units: `d`, `h`, `m`.
5. If `--dry-run` is present, stop after preview and do not delete.
6. Otherwise ask for confirmation before deleting.
7. Delete only default-state artifact directories after confirmation, then remove empty repo directories.

Safety rules:

- `cleanup-all` never touches repo-local override paths, even if they were produced by this skill.
- `cleanup-all` never edits ignore files.
- If the state root is empty or absent, report `no artifacts found`.
