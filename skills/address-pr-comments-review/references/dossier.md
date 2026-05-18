# Dossier Contract

This file defines the dossier contract — the structure, content rules, and quality requirements for the review dossier generated after successful interaction. It is responsible for specifying what a valid dossier looks like, what each section must contain, and how the dossier prepares for plan execution.

## Precedence

Layer 3 (decision protocols). Consumes output from classification (Step 2), cross-reference (Step 2.5), and interaction (Steps 3-4). The dossier is the final deliverable of Phase 1. It feeds Prometheus (Phase 2) for plan generation. Dossier rules take precedence over template defaults — if the dossier contract requires a specific format, platform templates must adapt.

---

## Scope

This file covers:
- **Dossier structure**: executive summary, sections A/B/C, reply endpoints, templates, dependency notation, scope guardrails
- **Section A rules**: exact file paths, line numbers, code change description, test strategy, reply target, suggested commit message
- **Section B rules**: conclusion rationale, reply target, no-code-change constraint
- **Section C rules**: informational and already-replied — no action
- **Duplicate handling in dossier**: single task entry, multi-author listing, individual reply IDs
- **Conflict handling in dossier**: chosen direction in A/B, rejected direction in B
- **Scope guardrails**: anti-scope-creep constraints embedded in the dossier
- **Post-write verification**: file existence, valid markdown, count matching, placeholder completeness, reply endpoint correctness

## Out of Scope

- Classification rules → `classification.md`
- Cross-reference logic → `cross-reference.md`
- Interaction protocol → `interaction.md`
- Platform-specific file paths and commands → `platform.md`
- Reply template content → `reply.md` (dossier references reply templates by name)

## Key Design Decisions

### Dossier Is Not a Plan

The dossier is a requirements document, not an execution plan. Plan generation happens in Phase 2 via interactive Prometheus conversation. The dossier provides enough detail for Prometheus to ask informed follow-up questions.

### Duplicate Task Structure

When comments are merged (same file:line, same issue):
- ONE task entry in the dossier
- ALL authors listed in the task
- EACH author gets an individual reply via their own `in_reply_to` ID
- Dedup & Conflict Notes section documents the merge

### Cross-Section Leakage Prevention

The dossier contract explicitly forbids:
- Code-change tasks that only need a reply (move from A to B)
- Reply-only tasks that imply code changes (keep in B, add note)
- Informational items being promoted to actionable (stay in C)

### Final Cross-Reference Scan

Before writing, run the 8-check scan defined in `validation.md`. Any unresolved 🔴 item blocks dossier writing.
