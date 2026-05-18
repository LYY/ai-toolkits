# Script Contract: `list_comments.py`

This document defines the implicit interface contract between `scripts/list_comments.py` and the `address-pr-comments-review` skill. The skill consumes the script's JSON output; changes to this contract must be coordinated with all protocol files (classification.md, cross-reference.md, dossier.md, reply.md, interaction.md).

## JSON Output Structure

The script emits a JSON array of normalized comment objects. Each object represents a single PR feedback item (inline, review, top_level, or issue_comment).

## Consumed Fields

### Common Fields (All Kinds)

| Field       | Type    | Required | Description |
|-------------|---------|----------|-------------|
| `kind`      | string  | yes      | One of: `inline`, `review`, `top_level`, `issue_comment` |
| `id`        | integer | yes      | GitHub comment/review ID (used for `in_reply_to` in gh API) |
| `author`    | string  | yes      | Author login. May be `null` (ghost account). |
| `is_ai`     | boolean | yes      | `true` if author is a known bot/AI reviewer |
| `created_at`| string  | yes      | ISO 8601 timestamp |
| `url`       | string  | yes      | GitHub URL for the comment or review |
| `body`      | string  | yes      | Full comment body text (may be empty string) |
| `excerpt`   | string  | yes      | Truncated body (~220 chars). Not authoritative for classification — protocol must read `body`. |
| `ai_prompts`| string  | yes      | Extracted AI prompt blocks from the body. Empty string if none found. |

### Thread Metadata Fields

| Field              | Type    | Required | Description |
|--------------------|---------|----------|-------------|
| `has_replies`      | boolean | yes      | `true` if the thread has at least one non-AI reply. Primary signal for `already_replied` classification. |
| `thread_resolved`  | boolean | yes      | `true` if the thread was marked resolved in GitHub UI. Weak signal — NOT evidence of fix-state. |
| `thread_outdated`  | boolean | yes      | `true` if the diff context shifted since the comment was posted. NOT evidence of fix-state — triggers mandatory code verification. |

### Inline-Specific Fields

| Field  | Type    | Required | Notes |
|--------|---------|----------|-------|
| `path`  | string  | no (inline only) | File path relative to repo root. Only present when `kind=inline`. |
| `line`  | integer | no (inline only) | Line number in the file. Only present when `kind=inline`. |

These fields are absent for `review`, `top_level`, and `issue_comment` kinds. The skill must handle missing path/line gracefully.

## Field Usage by Protocol

| Protocol File       | Key Fields Consumed |
|---------------------|---------------------|
| classification.md   | `author`, `is_ai`, `body`, `excerpt`, `has_replies`, `thread_outdated`, `thread_resolved`, `path`, `line`, `kind` |
| cross-reference.md  | `has_replies`, `kind`, `path`, `line`, `id`, `author` |
| dossier.md          | `id`, `author`, `kind`, `path`, `line`, `url` |
| reply.md            | `id`, `author`, `kind`, `path`, `line` |
| interaction.md      | `id`, `author`, `kind`, `path`, `line`, `url` |

## Stability Guarantee

The `address-pr-comments-review` skill depends on these fields being present and correctly populated. Any change that renames, removes, or changes the semantics of a required field breaks the contract and must be coordinated with all protocol files listed above.
