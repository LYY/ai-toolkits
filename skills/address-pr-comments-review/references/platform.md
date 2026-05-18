# Platform Integration

This file defines platform-specific commands, paths, and conventions for the address-pr-comments-review skill. It is responsible for documenting all CLI commands, file operations, and environment requirements that are specific to the OpenCode + OhMyOpenCode (Sisyphus) platform.

## Precedence

Layer 4 (templates/checklists). Provides convenience defaults and command references for all upper layers. Platform commands are referenced by name from SKILL.md (Step 1, Step 5) and the dossier contract. Upper layers can override or extend these commands with additional parameters, but must not change the base command signatures documented here.

---

## Scope

This file covers:
- **Comment collection**: `list_comments.py` script usage, flags (`--json`, `--pr`, `--repo`, `--include-resolved`), auto-detection from current branch
- **Prerequisites**: `gh` CLI installation and authentication (`gh auth status`)
- **Platform lock**: compatibility boundaries (OpenCode only, not Claude Code / Cursor / Gemini CLI)
- **Dossier file operations**: path generation (`.sisyphus/notepads/pr-<N>-dossier/dossier-<TIMESTAMP>.md`), directory creation, timestamp format (`date +%Y%m%d-%H%M%S`)
- **Verification commands**: `test -f` for dossier existence, `git log --oneline` for commit style discovery
- **Handoff message format**: the exact text to output after dossier is saved

## Out of Scope

- Reply API commands (inline/review/top_level endpoints) → owned by `dossier.md` (Reply Endpoints section). This file documents comment collection only.
- Reply templates or content → `reply.md`
- Dossier structure or section rules → `dossier.md`
- Verification gate logic → `validation.md`
- Classification or cross-reference rules → `classification.md`, `cross-reference.md`

## Prerequisites

Before running any collection commands:

1. **`gh` CLI installed**: Verify with `gh --version`.
2. **Authenticated**: Run `gh auth status`. Must show "Logged in to github.com".
3. **PR context**: Current git branch must have an open PR, or you must provide `--pr <N>` and optionally `--repo owner/name`.

## Comment Collection

All comment collection uses `scripts/list_comments.py` (vendored within the skill, no Python package dependencies).

### Command

```bash
# Auto-detect PR from current branch
python3 ./scripts/list_comments.py --json

# Explicit PR number
python3 ./scripts/list_comments.py --pr <N> --json

# Cross-repo (run from any directory)
python3 ./scripts/list_comments.py --repo owner/name --pr <N> --json

# Include resolved threads
python3 ./scripts/list_comments.py --include-resolved --json
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

Replace `<N>` and `<TIMESTAMP>` with actual values. This handoff is the bridge from Phase 1 (this skill) to Phase 2 (Prometheus plan generation).

## Ownership Boundary

**Collection commands** (`list_comments.py`) and **runtime commands** (directory operations, timestamps, `gh` auth) are owned by this file. **Reply endpoint commands** (inline/review/top_level API calls) are owned by `references/dossier.md` (Reply Endpoints section). Do not add reply endpoint commands to this file.

## Key Design Decisions

### Platform Lock Is Explicit

This skill requires OpenCode + OhMyOpenCode (Sisyphus). The dossier placement path and the Prometheus → `/start-work` flow are Sisyphus-specific. These constraints are not configurable.

### Self-Contained Script

`list_comments.py` is vendored within the skill directory with no Python package dependencies. Only `gh` CLI is required externally. This avoids dependency management issues when using the skill across different environments.

### Cross-Repo Access

The `--repo owner/name` flag allows collecting comments from a remote PR without being in the repo directory. This is important for reviewers who don't have the codebase locally.

### Command Ownership Boundary

This file owns comment collection commands (`list_comments.py`) and prerequisite verification. Reply API commands (inline/review/top_level endpoints) are owned by `dossier.md` (Reply Endpoints section). For reply endpoint commands, see `references/dossier.md`.

### Commit SHA for Inline Replies

Inline replies require a valid commit SHA on the PR branch. The command `git rev-parse HEAD` provides this. Review and top-level replies do not need `commit_id`.
