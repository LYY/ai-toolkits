# Script Contract: `list_comments.py`

This document is the **canonical script/data boundary** between `scripts/list_comments.py` and the `address-pr-comments-review` skill. It defines the authoritative schema for the script's JSON output. Changes to this contract must be coordinated with all protocol files (classification.md, cross-reference.md, dossier.md, reply.md, interaction.md).

Field tables in this file are the single source of truth for JSON field schemas. Protocol documentation must reference this contract by field name rather than re-listing field definitions. Duplicating field schemas elsewhere creates drift risk.

## JSON Output Structure

The script emits a JSON array of normalized comment objects. Each object represents a single PR feedback item (inline, review, or top_level).

## Consumed Fields

### Common Fields (All Output Kinds)

| Field       | Type    | Required | Description |
|-------------|---------|----------|-------------|
| `kind`      | string  | yes      | One of: `inline`, `review`, `top_level` |
| `id`        | integer | yes      | GitHub comment/review ID (used for `in_reply_to` in gh API) |
| `author`    | string  | yes      | Author login. May be `null` (ghost account). |
| `is_ai`     | boolean | yes      | `true` if author is a known bot/AI reviewer |
| `body`      | string  | yes      | Full comment body text (may be empty string) |
| `excerpt`   | string  | yes      | Truncated body (~220 chars). Not authoritative for classification — protocol must read `body`. |
| `ai_prompts`| string  | yes      | Extracted AI prompt blocks from the body. Empty string if none found. |

### Timestamp and URL Fields

Timestamp and URL fields vary by output kind:

| Field         | Applies to       | Required | Description |
|---------------|------------------|----------|-------------|
| `created_at`  | inline, top_level | yes (when present) | ISO 8601 timestamp of comment creation. Absent for `review` kind. |
| `submitted_at`| review           | yes (when present) | ISO 8601 timestamp of review submission. Only present for `kind=review`. |
| `url`         | inline, top_level | yes (when present) | GitHub URL for the comment. Absent for `review` kind. |

### Thread Metadata Fields

| Field              | Type    | Required | Description |
|--------------------|---------|----------|-------------|
| `has_replies`      | boolean | yes      | `true` if the thread has at least one non-AI reply. Primary signal for `already_replied` classification. |
| `thread_resolved`  | boolean | yes (inline only) | `true` if the thread was marked resolved in GitHub UI. Weak signal — NOT evidence of fix-state. Only present for `kind=inline`. |
| `thread_outdated`  | boolean | yes (inline only) | `true` if the diff context shifted since the comment was posted. NOT evidence of fix-state — triggers mandatory code verification. Only present for `kind=inline`. |

### Inline-Specific Fields

| Field  | Type    | Required | Notes |
|--------|---------|----------|-------|
| `path`  | string  | no (inline only) | File path relative to repo root. Only present when `kind=inline`. |
| `line`  | integer | no (inline only) | Line number in the file. Only present when `kind=inline`. |

These fields are absent for `review` and `top_level` kinds. The skill must handle missing path/line gracefully.

### Review-Specific Fields

| Field   | Type    | Required | Notes |
|---------|---------|----------|-------|
| `state`  | string  | yes (review only) | Review state (e.g. `APPROVED`, `CHANGES_REQUESTED`, `COMMENT`). Only present when `kind=review`. |

## Internal Implementation Details

### issue_comment Event (Internal Only)

The script uses an internal `issue_comment` event kind exclusively within `build_reply_map()` for chronological event sorting and reply detection. This kind is **never part of the public JSON output array**. Protocol files and consumers must not treat `issue_comment` as a public comment kind.

| Field    | Type    | Description |
|----------|---------|-------------|
| `kind`   | string  | Always `"issue_comment"` |
| `id`     | integer | GitHub comment ID |
| `time`   | string  | ISO 8601 timestamp |
| `author` | string  | Author login |

This event type is consumed internally by the reply detection logic and does not appear in the normalized comment output that protocol files consume.

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
