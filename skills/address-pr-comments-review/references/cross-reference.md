# Cross-Reference Protocol

This file defines the cross-reference protocol for detecting patterns across classified PR review comments. It is responsible for identifying duplicates, conflicts, relations, and already-replied status across the full comment set.

## Precedence

Layer 2 (workflow/protocol). Called by SKILL.md Step 2.5, after individual classification (Step 2) and before the overview table (Step 3). Cross-reference results transform the raw classified comments into a deduplicated, relation-aware dataset. The interaction protocol (Step 3) consumes this transformed dataset. Cross-reference has final say on dedup and conflict strategy within its domain — interaction defers on these matters.

---

## Scope

This file covers:
- **Duplicate detection**: same file + same line + same issue, different line + same function, same semantic issue
- **Conflict detection**: opposing or incompatible recommendations on the same code
- **Relation detection**: causally or logically connected comments across different files/lines
- **Already-replied detection**: `has_replies` field from `list_comments.py`, detection methods per comment kind
- **Merge strategy**: how duplicates become single entries with multi-author attribution
- **Conflict presentation**: formatted table entries with 🔴 flags for interactive resolution

## Out of Scope

- Individual comment classification (source, intent, conclusion) → `classification.md`
- Interactive discussion of conflicts → `interaction.md`
- Dossier section assignment for merged entries → `dossier.md` (consumes cross-reference output)
- Comment collection or `gh` operations → `platform.md`

## Key Design Decisions

### Detection Signals

| Pattern | Signal | Action |
|---------|--------|--------|
| Duplicate | Same `path:line`, same function, same semantic issue | Merge into one entry, list all authors |
| Conflict | Opposing recommendations on same code | Merge into one entry, mark 🔴, present both options |
| Related | Causal/logical connection across files | Note relationship, add dependency metadata |
| Already-replied | `has_replies: true` from `list_comments.py` | Classify as `already_replied`, place in Section C |

### Conflict Resolution Order

When a conflict involves both a human and a bot reviewer:
1. Present both sides neutrally (not weighted by source)
2. User chooses direction during Step 3 interaction
3. Chosen direction goes to Section A or B in dossier
4. Rejected direction goes to Section B as reply-only
5. Reply template for rejected direction is defined in `reply.md`

### Duplicate Author Reply

Merged duplicates list all authors. Each author receives an individual reply using their own `in_reply_to` ID. The reply strategy is defined in `reply.md`; the cross-reference protocol only identifies which authors need to be replied to.
