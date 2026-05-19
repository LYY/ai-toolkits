# Platform Integration

Runtime commands, paths, and the `list_comments.py` script contract. Platform lock: OpenCode + OhMyOpenCode (Sisyphus) only.

## Prerequisites

Before running any collection commands:

1. **`gh` CLI installed**: Verify with `gh --version`.
2. **Authenticated**: Run `gh auth status`. Must show "Logged in to github.com".
3. **PR context**: Current git branch must have an open PR, or you must provide `--pr <N>` and optionally `--repo owner/name`.

## Comment Collection

All comment collection uses `scripts/list_comments.py` (vendored within the skill, no Python package dependencies). The script lives at `<skill-dir>/scripts/list_comments.py`, where `<skill-dir>` is the directory containing `SKILL.md` — the same base path from which you loaded this file, minus the `references/` prefix.

### Command

```bash
# Resolve SCRIPT to the full path relative to SKILL.md's directory:
# SCRIPT="<skill-dir>/scripts/list_comments.py"

# Auto-detect PR from current branch
python3 "$SCRIPT" --json

# Explicit PR number
python3 "$SCRIPT" --pr <N> --json

# Cross-repo (run from any directory)
python3 "$SCRIPT" --repo owner/name --pr <N> --json

# Include resolved threads
python3 "$SCRIPT" --include-resolved --json
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

After comments are collected and processed, the dossier is written to:

```
.sisyphus/notepads/pr-<N>-dossier/dossier-<TIMESTAMP>.md
```

- `<N>`: PR number
- `<TIMESTAMP>`: formatted as `YYYYMMDD-HHMMSS` using `date +%Y%m%d-%H%M%S`
- Directory is created automatically if it does not exist

### Timestamp Format

```bash
date +%Y%m%d-%H%M%S
```

Example: `20260115-143022` for January 15, 2026 at 14:30:22.

### Directory Creation

```bash
mkdir -p .sisyphus/notepads/pr-<N>-dossier/
```

## Handoff

After the dossier is saved, output the following message to the user:

```
Dossier saved to .sisyphus/notepads/pr-<N>-dossier/dossier-<TIMESTAMP>.md

To generate the execution plan, switch to Prometheus mode and paste:

  Read .sisyphus/notepads/pr-<N>-dossier/dossier-<TIMESTAMP>.md
  and generate an execution plan. Ask me if any task is ambiguous.
```

Replace `<N>` and `<TIMESTAMP>` with actual values.


