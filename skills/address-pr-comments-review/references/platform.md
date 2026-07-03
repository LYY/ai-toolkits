# Platform Integration

Runtime commands, paths, and the `list_comments.py` script contract. Platform lock: OpenCode + OhMyOpenCode (Sisyphus) only.

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

## Dossier Path & Timestamp

After comments are collected and processed, the dossier is written under the bound checkout:

```
<TARGET_WORKTREE_ROOT>/.omo/notepads/pr-<N>-dossier/dossier-<TIMESTAMP>.md
```

- `<N>`: PR number
- `<TIMESTAMP>`: formatted as `YYYYMMDD-HHMMSS` using `date +%Y%m%d-%H%M%S`
- Directory is created automatically from `TARGET_WORKTREE_ROOT` if it does not exist

### Timestamp Format

```bash
date +%Y%m%d-%H%M%S
```

Example: `20260115-143022` for January 15, 2026 at 14:30:22.

### Directory Creation

```bash
mkdir -p "$TARGET_WORKTREE_ROOT/.omo/notepads/pr-<N>-dossier/"
```

## Handoff

After the dossier is saved, output the following message to the user. Replace `<N>`, `<TIMESTAMP>`, `<PLAN_PATH>`, and `<TARGET_WORKTREE_ROOT>` with actual values. Keep the dossier path anchored to the bound checkout.

```
Dossier saved to <TARGET_WORKTREE_ROOT>/.omo/notepads/pr-<N>-dossier/dossier-<TIMESTAMP>.md

To generate the execution plan, switch to Prometheus mode and paste:

  Read <TARGET_WORKTREE_ROOT>/.omo/notepads/pr-<N>-dossier/dossier-<TIMESTAMP>.md
  and generate an execution plan. Ask me if any task is ambiguous.

After Prometheus writes the plan, run:

  /start-work <PLAN_PATH> worktree_path=<TARGET_WORKTREE_ROOT>
```
