# Architecture Overview & Precedence Model

This file defines the layered reference structure and the rule precedence model for the address-pr-comments-review skill.

## Responsibility

This file is responsible for defining the architecture, the separation of concerns across reference files, and the precedence model that governs how rules resolve when multiple protocol layers apply to the same decision.

## Precedence

**Top of the hierarchy.** This file establishes the structure that all other reference files follow. It has no peers — it is the meta-layer that defines how the other layers relate.

---

## Precedence Model

The address-pr-comments-review system follows a four-layer precedence model:

```
entry skill → workflow/protocol → decision protocols → templates/checklists
```

| Layer | Files | Precedence | Role |
|-------|-------|------------|------|
| **Entry skill** | `SKILL.md` | Highest | Entry point. Loads references. Defines phases (collect → classify → interact → dossier → handoff). Platform lock. Prerequisites. Error recovery. |
| **Workflow / protocol** | `classification.md`, `cross-reference.md`, `interaction.md` | 2nd | Define the HOW for each major workflow step. Classification protocol, cross-reference protocol, interaction protocol. These are referenced by name from SKILL.md steps. |
| **Decision protocols** | `dossier.md`, `reply.md` | 3rd | Define WHAT to produce. Dossier contract specifies the document structure. Reply policy specifies the communication rules. |
| **Templates / checklists** | `platform.md`, `validation.md` | 4th | Provide concrete templates, checklists, platform-specific commands, and verification gates. Lowest precedence because they are referenced by upper layers, not the reverse. |

### How Precedence Resolves

When a decision could be made by rules in multiple layers:

1. **Explicit rule beats inferred rule.** If `SKILL.md` says "always scan before write", that overrides any implicit assumption in a protocol file.
2. **Upper layer overrides lower layer.** A rule in `classification.md` (layer 2) overrides a suggestion in `reply.md` (layer 3).
3. **Within the same layer, specificity wins.** The cross-reference protocol (`cross-reference.md`) has final say on dedup strategy within its domain; the interaction protocol defers to it on cross-reference matters.
4. **Template defaults are overridable.** Values in `platform.md` are convenience defaults, not rules. Upper layers can override them explicitly.
5. **No rule is silently duplicated.** If a rule exists in one layer, it is not restated in another. Precedence resolution follows the chain above.

### Layer Boundaries

| Don't | Do |
|-------|-----|
| Put classification rules in `dossier.md` | Classification rules stay in `classification.md`. Dossier references them. |
| Repeat cross-reference logic in `interaction.md` | Interaction protocol defers to cross-reference protocol for dedup/conflict concerns. |
| Define reply templates in `classification.md` | Reply templates belong in `reply.md`. Classification only assigns the conclusion that determines which template to use. |
| Embed `gh` commands outside `platform.md` | All platform-specific CLI commands live in `platform.md`. Other files reference them by name. |

---

## File Map

| File | Layer | Referenced by | Content summary |
|------|-------|---------------|-----------------|
| `overview.md` | Meta | All files | Architecture, precedence model, file map |
| `classification.md` | Workflow/protocol | SKILL.md Step 2 | Source detection, intent assessment, conclusion assignment, edge cases, dossier section mapping |
| `cross-reference.md` | Workflow/protocol | SKILL.md Step 2.5 | Duplicate detection, conflict detection, relation detection, already-replied detection |
| `interaction.md` | Workflow/protocol | SKILL.md Step 3-4 | Overview table format, silent consent, discussion flow, scaling rules, confirmation transitions |
| `dossier.md` | Decision protocols | SKILL.md Step 5 | Dossier structure, section A/B/C format, reply endpoints, cross-reference checks, dependency notation, scope guardrails, verification post-write |
| `reply.md` | Decision protocols | dossier.md, interaction.md | Reply templates per conclusion, endpoint kinds (inline/review/top_level), duplicate author reply strategy, conflict reply strategy |
| `platform.md` | Templates/checklists | SKILL.md Step 1, 5, 6 | `gh` CLI commands, `list_comments.py` usage, OpenCode/Sisyphus paths, dossier file operations, handoff message format |
| `validation.md` | Templates/checklists | SKILL.md Step 5 | Final cross-reference scan checklist, dossier verification checks, gate rules, regression scenarios |

---

## Eval Matrix

The evaluation matrix at `eval-matrix.md` defines the behavioral acceptance criteria that all reference files collectively must satisfy. It is not a protocol layer but a test suite that validates precedence correctness and rule coverage.
