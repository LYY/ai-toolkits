# Platform Integration

This file defines platform-specific commands, paths, and conventions for the address-pr-comments-review skill. It is responsible for documenting all CLI commands, file operations, and environment requirements that are specific to the OpenCode + OhMyOpenCode (Sisyphus) platform.

## Precedence

Layer 4 (templates/checklists). Provides convenience defaults and command references for all upper layers. Platform commands are referenced by name from SKILL.md (Step 1, Step 5, Step 6) and the dossier contract. Upper layers can override or extend these commands with additional parameters, but must not change the base command signatures documented here.

---

## Scope

This file covers:
- **Comment collection**: `list_comments.py` script usage, flags (`--json`, `--pr`, `--repo`, `--include-resolved`), auto-detection from current branch
- **Dossier file operations**: path generation (`.sisyphus/notepads/pr-<N>-dossier/dossier-<TIMESTAMP>.md`), directory creation, timestamp format (`date +%Y%m%d-%H%M%S`)
- **Reply API commands**: `gh api` commands for inline, review, and top_level reply endpoints with full parameter sets
- **Verification commands**: `test -f` for dossier existence, `git log --oneline` for commit style discovery
- **Platform lock**: compatibility boundaries (OpenCode only, not Claude Code / Cursor / Gemini CLI)
- **Prerequisites**: `gh` CLI installation and authentication (`gh auth status`)
- **Handoff message format**: the exact text to output after dossier is saved

## Out of Scope

- Reply templates or content → `reply.md`
- Dossier structure or section rules → `dossier.md`
- Verification gate logic → `validation.md`
- Classification or cross-reference rules → `classification.md`, `cross-reference.md`

## Key Design Decisions

### Platform Lock Is Explicit

This skill requires OpenCode + OhMyOpenCode (Sisyphus). The dossier placement path and the Prometheus → `/start-work` flow are Sisyphus-specific. These constraints are not configurable.

### Self-Contained Script

`list_comments.py` is vendored within the skill directory with no Python package dependencies. Only `gh` CLI is required externally. This avoids dependency management issues when using the skill across different environments.

### Cross-Repo Access

The `--repo owner/name` flag allows collecting comments from a remote PR without being in the repo directory. This is important for reviewers who don't have the codebase locally.

### Commit SHA for Inline Replies

Inline replies require a valid commit SHA on the PR branch. The command `git rev-parse HEAD` provides this. Review and top-level replies do not need `commit_id`.
