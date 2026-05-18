# Classification Protocol

This file defines the classification protocol for analyzing individual PR review comments. It is responsible for determining the source, intent, and conclusion of each comment, and for mapping those conclusions to dossier sections.

## Precedence

Layer 2 (workflow/protocol). Called by SKILL.md Step 2. Classification conclusions feed into the cross-reference protocol (Step 2.5), interaction protocol (Step 3), and dossier generation (Step 5). Classification rules take precedence over reply templates — the conclusion assigned here determines which reply template applies, not the reverse.

---

## Scope

This file covers:
- **Source detection**: `@human` vs `@bot` identification
- **Intent assessment**: `actionable` vs `informational` determination
- **Conclusion assignment**: `valid` / `invalid` / `already_fixed` / `already_replied` / `out_of_scope` / `needs_clarification`
- **Edge case handling**: minimized comments, deleted authors, empty bodies, self-review, pre-existing replies
- **Dossier section mapping**: conclusion → Section A/B/C mapping table

## Out of Scope

- Duplicate or conflict detection across comments → `cross-reference.md`
- Reply template selection → `reply.md` (the conclusion assigned here selects the template there)
- Interaction flow or silent consent rules → `interaction.md`
- Platform-specific comment collection → `platform.md`, `SKILL.md` Step 1

## Key Design Decisions

### Reading Full Body

The `excerpt` field from `list_comments.py` is truncated to 220 characters. Classification must read the `body` field for accurate analysis, especially for long review comments where the excerpt may cut off critical detail.

### Discussion Flag

Comments classified as `needs_clarification` or high-risk `valid` items get a 🔴 discussion flag. This flag is consumed by the interaction protocol (Step 3) to determine which items require interactive resolution before proceeding.

### Conclusion → Section Mapping

The mapping table (actionable conclusions → A or B, informational → C) is defined in the source SKILL.md. This file exists to own that table and any future modifications to it.

### Duplicate Author Reply Policy

When duplicates are detected (by `cross-reference.md`), each author receives an individual reply. The classification protocol assigns the conclusion; `reply.md` defines how to address multiple authors.
