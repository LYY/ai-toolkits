#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
SOURCE_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd -P)"
MANIFEST="$SCRIPT_DIR/manifest.tsv"
CHECKER="$SOURCE_ROOT/scripts/check-financial-systems-testing-contract.sh"

apply_mutation() {
    local root="$1"
    local mutation="$2"
    local skill="$root/skills/financial-systems-testing/SKILL.md"
    local references="$root/skills/financial-systems-testing/references"

    case "$mutation" in
        none) ;;
        missing-skill) rm "$skill" ;;
        invalid-frontmatter)
            perl -0pi -e 's/name: financial-systems-testing/name: wrong-name/' "$skill"
            ;;
        generic-description)
            perl -0pi -e 's/description: .*/description: Use when writing tests./' "$skill"
            ;;
        missing-on-demand-reference)
            perl -0pi -e 's/^\| `money-ledger-invariants\.md` \|.*\n//m' "$skill"
            ;;
        duplicate-on-demand-reference)
            perl -0pi -e 's/(## Public-Skill Routing)/| `money-ledger-invariants.md` | duplicate |\n\n$1/' "$skill"
            ;;
        extra-runtime-references)
            cp "$references/money-ledger-invariants.md" "$references/extra-one.md"
            cp "$references/money-ledger-invariants.md" "$references/extra-two.md"
            ;;
        missing-reference-heading)
            perl -0pi -e 's/## Completion Criteria/## Completion/' "$references/money-ledger-invariants.md"
            ;;
        forbidden-runtime-content)
            printf '%s\n' 'b1-finance runtime content' >> "$skill"
            ;;
        forbidden-compliance-name)
            printf '%s\n' 'PCI DSS instruction' >> "$skill"
            ;;
        reference-skill-backlink)
            printf '%s\n' 'See [skill](../SKILL.md).' >> "$references/money-ledger-invariants.md"
            ;;
        reference-sibling-link)
            printf '%s\n' 'See [sibling](money-ledger-invariants.md).' >> "$references/transaction-lifecycles.md"
            ;;
        reference-docs-link)
            printf '%s\n' 'See [maintainer](../../../docs/financial-systems-testing/eval-results.md).' >> "$references/transaction-lifecycles.md"
            ;;
        reference-absolute-path)
            printf '%s\n' 'See /Users/example/financial.md.' >> "$references/transaction-lifecycles.md"
            ;;
        reference-public-skill-route)
            printf '%s\n' 'Use `tdd` for generic testing mechanics.' >> "$references/transaction-lifecycles.md"
            ;;
        missing-public-skill-routing)
            perl -0pi -e 's/## Public-Skill Routing/## Skill Routing/' "$skill"
            ;;
        missing-completion-criterion)
            perl -0pi -e 's/## Completion Criterion/## Completion/' "$skill"
            ;;
        *)
            printf 'unknown mutation: %s\n' "$mutation" >&2
            return 2
            ;;
    esac
}

total=0
passed=0
failed=0

while IFS=$'\t' read -r case_id mutation expected_exit expected_diagnostic; do
    [ -z "$case_id" ] && continue
    case "$case_id" in
        \#*|case_id) continue ;;
    esac

    tmp_root="$(mktemp -d "${TMPDIR:-/tmp}/fst-contract.XXXXXX")"
    mkdir -p "$tmp_root/skills"
    cp -R "$SOURCE_ROOT/skills/financial-systems-testing" "$tmp_root/skills/"
    apply_mutation "$tmp_root" "$mutation"

    stderr="$tmp_root/stderr.log"
    if bash "$CHECKER" "$tmp_root" >/dev/null 2>"$stderr"; then
        actual_exit=0
    else
        actual_exit=$?
    fi
    actual_diagnostic="$(grep -Eo 'FST00[1-9]' "$stderr" | head -n 1 || true)"

    total=$((total + 1))
    if [ "$expected_diagnostic" = "-" ]; then
        diagnostic_matches="$( [ -z "$actual_diagnostic" ] && printf true || printf false )"
    else
        diagnostic_matches="$( [ "$actual_diagnostic" = "$expected_diagnostic" ] && printf true || printf false )"
    fi
    if [ "$actual_exit" -eq "$expected_exit" ] && [ "$diagnostic_matches" = true ]; then
        passed=$((passed + 1))
        printf 'OK %s\n' "$case_id"
    else
        failed=$((failed + 1))
        printf 'FAIL %s expected exit=%s diagnostic=%s got exit=%s diagnostic=%s\n' \
            "$case_id" "$expected_exit" "$expected_diagnostic" "$actual_exit" "$actual_diagnostic" >&2
        cat "$stderr" >&2
    fi
    rm -rf "$tmp_root"
done < "$MANIFEST"

printf 'total=%s passed=%s failed=%s\n' "$total" "$passed" "$failed"
[ "$failed" -eq 0 ]
