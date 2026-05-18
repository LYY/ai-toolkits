# Interaction Protocol

This file defines the interaction protocol for the interactive review confirmation phase. It is responsible for governing the conversation flow between the AI analyst and the user during Steps 3 and 4: overview table presentation, silent consent, discussion of flagged items, and final confirmation.

## Precedence

Layer 2 (workflow/protocol). Consumes output from classification (Step 2) and cross-reference (Step 2.5) protocols. Governs Steps 3 and 4 of SKILL.md. Interaction rules apply only during the live conversation — once confirmed, the dossier protocol (Step 5) takes over. Silent consent and 🔴 discussion rules established here have the final say on what counts as "confirmed" for dossier generation.

---

## Scope

This file covers:
- **Overview table construction**: format, deduplication display, legend
- **Silent consent**: what counts as agreement, how to handle non-response
- **🔴 item discussion protocol**: how to present conflicts, needs_clarification, high-risk items
- **Scaling rules**: large PR handling, batch discussion, prioritization
- **Final confirmation table**: change summary format, explicit user approval gate

## Out of Scope

- Comment classification → `classification.md`
- Duplicate/conflict detection → `cross-reference.md`
- Dossier generation → `dossier.md` (occurs after interaction confirms)
- Reply content or templates → `reply.md`

## Key Design Decisions

### Silence = Consent

If the user says "continue", "ok", "go ahead", or doesn't object to a specific item, that item is considered accepted on the AI's classification. This is a deliberate design choice to reduce friction for routine reviews. Any item can be objected to by number.

### Confirmation Escalation

There are two distinct gates:
1. **Step 3 gate**: User accepts or discusses 🔴 items. Remaining items proceed on silent consent.
2. **Step 4 gate**: User explicitly confirms the final table with "ok" or equivalent.

Both gates must be passed before dossier generation (Step 5). The validation protocol (`validation.md`) enforces this.

### Large PR Scaling

When the number of actionable comments exceeds 20, the interaction protocol switches to a compressed mode:
- Show 🔴 items inline
- Collapse 📝 items to a summary line
- Batch 🔴 discussions into groups of 5-7
- Offer prioritization (CRITICAL first, then lower)

### Change Summary

Between Step 3 and Step 4, a change summary is shown so the user can see what their decisions affected. This prevents surprises at the final table.
