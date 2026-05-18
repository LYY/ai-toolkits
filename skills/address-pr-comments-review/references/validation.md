# Validation & Regression

This file defines the validation and regression protocol — the checklists and gate rules that ensure dossier integrity before handoff. It is responsible for defining the final cross-reference scan, the post-write dossier verification, and the regression scenarios that future changes must not break.

## Precedence

Layer 4 (templates/checklists). Called by SKILL.md Step 5 (before and after dossier write). Validation gates are enforced by the entry skill — if a check fails, the skill must not proceed. Validation rules reference classification, cross-reference, and dossier protocols but do not override them. They are the last line of defense before handoff.

---

## Scope

This file covers:
- **Final cross-reference scan**: 8 checks to run before writing the dossier (new duplicates, stale duplicates, unresolved conflicts, orphaned replies, new relations, cross-section leakage, reply target mismatch, stale already_replied)
- **Dossier post-write verification**: file existence, valid markdown, count matching, no placeholder variables, reply endpoint correctness
- **Gate rules**: conditions under which the skill must STOP and return to an earlier step
- **Regression scenarios**: behaviors that future modifications must preserve (derived from `eval-matrix.md`)

## Out of Scope

- The eval matrix itself → `eval-matrix.md` (defines acceptance criteria, not verification steps)
- Dossier structure or section rules → `dossier.md`
- Classification or cross-reference rules → `classification.md`, `cross-reference.md`
- Platform-specific commands → `platform.md`

## Key Design Decisions

### Two-Phase Verification

Verification happens in two distinct phases:

1. **Pre-write scan** (before dossier generation): Cross-reference the final confirmed table against original cross-reference results. This catches changes that happened during discussion.

2. **Post-write checks** (after dossier write): Verify the dossier file itself is complete and correct. This catches generation errors.

Both phases must pass. The entry skill enforces this.

### The 🔴 Gate

If any 🔴 item remains unresolved after Step 4 interaction, the skill MUST NOT write the dossier. It must return to Step 3 for further discussion. This is a hard gate — no override, no workaround.

### Regression Scenarios

The following scenarios must continue to work correctly after any protocol change:

| Scenario | Critical behavior | Source |
|----------|------------------|--------|
| `thread_outdated unresolved` | Must read current code, not analogize to minimized | eval-matrix.md |
| `thread_outdated + thread_resolved` | `thread_outdated` alone is never a shortcut to skip verification | eval-matrix.md |
| `minimized comment` | Author retracted, no action needed | eval-matrix.md |
| `zero-actionable` | Overview table must show even when zero items | eval-matrix.md |
| `partial fix` | Fix attempt that doesn't fully address concern still = `valid` | eval-matrix.md |
| `duplicate reply` | Merge duplicates, reply to each author individually | eval-matrix.md |
| `cross-file` | Fix commented file only, guardrail the cross-file pattern | eval-matrix.md |

### No Placeholder Leakage

The dossier post-write check must scan for `{{...}}` template variables. Any unfilled placeholder means the dossier is incomplete and must be regenerated. This prevents Prometheus from receiving a dossier with gaps.
