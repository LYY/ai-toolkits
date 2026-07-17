#!/usr/bin/env bash
set -euo pipefail

resolve_repo_root() {
    local candidate="${1:-}"
    if [ -z "$candidate" ]; then
        git rev-parse --show-toplevel
        return
    fi
    if [ ! -d "$candidate" ]; then
        printf 'FST001: repo root is not a directory: %s\n' "$candidate" >&2
        exit 1
    fi
    cd "$candidate" && pwd -P
}

REPO_ROOT="$(resolve_repo_root "${1:-}")"
SKILL_MD="$REPO_ROOT/skills/financial-systems-testing/SKILL.md"
REFERENCE_DIR="$REPO_ROOT/skills/financial-systems-testing/references"
REQUIRED_REFERENCES=(
    "money-ledger-invariants.md"
    "transaction-lifecycles.md"
    "risk-credit-settlement.md"
    "resilience-reconciliation.md"
)
REQUIRED_REFERENCE_HEADINGS=(
    "## Use When"
    "## Required Facts"
    "## Invariants and Oracles"
    "## Test Scenarios"
    "## Completion Criteria"
)

errors=0

report() {
    printf '%s: %s\n' "$1" "$2" >&2
    errors=1
}

require_files() {
    local missing=false
    if [ ! -f "$SKILL_MD" ]; then
        report "FST001" "required file missing: skills/financial-systems-testing/SKILL.md"
        missing=true
    fi
    for reference in "${REQUIRED_REFERENCES[@]}"; do
        if [ ! -f "$REFERENCE_DIR/$reference" ]; then
            report "FST001" "required file missing: skills/financial-systems-testing/references/$reference"
            missing=true
        fi
    done
    if "$missing"; then
        exit 1
    fi
}

frontmatter_end_line() {
    awk 'NR > 1 && /^---[[:space:]]*$/ { print NR; exit }' "$SKILL_MD"
}

check_frontmatter() {
    local end_line
    end_line="$(frontmatter_end_line)"
    if [ "$(sed -n '1p' "$SKILL_MD")" != "---" ] || [ -z "$end_line" ]; then
        report "FST002" "invalid frontmatter"
        return
    fi
    local frontmatter
    frontmatter="$(sed -n "2,$((end_line - 1))p" "$SKILL_MD")"
    if [ "$(printf '%s\n' "$frontmatter" | grep -Ec '^name:[[:space:]]*financial-systems-testing[[:space:]]*$')" -ne 1 ] || \
        [ "$(printf '%s\n' "$frontmatter" | grep -Ec '^description:[[:space:]]*.+$')" -ne 1 ]; then
        report "FST002" "invalid frontmatter/name"
    fi
}

skill_description() {
    awk '/^---[[:space:]]*$/ { marks++; next } marks == 1 && /^description:[[:space:]]*/ { sub(/^description:[[:space:]]*/, ""); print; exit }' "$SKILL_MD"
}

check_description() {
    local description
    description="$(skill_description)"
    if [ -z "$description" ] || ! printf '%s\n' "$description" | grep -qiE '(money|balances?|ledger|trading|orders?|positions?|payments?|wallets?|credit|risk|clearing|settlement|reconciliation|finance reference data)'; then
        report "FST003" "description lacks a finance-domain trigger"
        return
    fi
    if printf '%s\n' "$description" | grep -qiE '^Use when (writing|creating|running) (any |generic )?tests?\.?$'; then
        report "FST003" "description triggers on generic testing alone"
    fi
}

on_demand_loading() {
    awk '
        /^## On-Demand Loading[[:space:]]*$/ { in_section = 1; next }
        in_section && /^## / { exit }
        in_section { print }
    ' "$SKILL_MD"
}

check_on_demand_loading() {
    local table
    table="$(on_demand_loading)"
    local table_rows
    table_rows="$(printf '%s\n' "$table" | grep '^|' || true)"
    local expected_count=0
    for reference in "${REQUIRED_REFERENCES[@]}"; do
        local count
        count="$(printf '%s\n' "$table_rows" | grep -Fc "\`$reference\`" || true)"
        if [ "$count" -ne 1 ]; then
            report "FST004" "On-Demand Loading must list $reference exactly once"
            return
        fi
        expected_count=$((expected_count + 1))
    done
    local listed_count
    listed_count="$(printf '%s\n' "$table_rows" | grep -Eo '\`[^\`]+\.md\`' | wc -l | tr -d ' ')"
    if [ "$listed_count" -ne "$expected_count" ]; then
        report "FST004" "On-Demand Loading contains an unexpected reference"
    fi
}

check_runtime_reference_count() {
    local count
    count="$(find "$REFERENCE_DIR" -maxdepth 1 -type f -name '*.md' | wc -l | tr -d ' ')"
    if [ "$count" -gt 5 ]; then
        report "FST005" "more than five runtime references"
    fi
}

check_reference_headings() {
    local reference
    for reference in "${REQUIRED_REFERENCES[@]}"; do
        local path="$REFERENCE_DIR/$reference"
        local heading
        for heading in "${REQUIRED_REFERENCE_HEADINGS[@]}"; do
            if ! grep -qF "$heading" "$path"; then
                report "FST006" "$reference lacks heading: $heading"
                break
            fi
        done
    done
}

check_forbidden_runtime_content() {
    local path
    local files=("$SKILL_MD")
    for reference in "${REQUIRED_REFERENCES[@]}"; do
        files+=("$REFERENCE_DIR/$reference")
    done
    for path in "${files[@]}"; do
        if grep -qiE 'b1-|EnterPlanMode|80%|required manual production mutation|fixed library|universal rounding|SOX|PCI DSS|PSD2|MiFID|Basel|GDPR|HIPAA|AML|KYC|OFAC|FINRA|\bFCA\b|\bSEC\b' "$path"; then
            report "FST007" "forbidden runtime content in ${path#$REPO_ROOT/}"
            return
        fi
    done
}

check_reference_topology() {
    local reference
    for reference in "${REQUIRED_REFERENCES[@]}"; do
        local path="$REFERENCE_DIR/$reference"
        if grep -qE '\]\([^)]*(\.\./)+SKILL\.md[^)]*\)' "$path"; then
            report "FST008" "$reference links back to SKILL.md"
            return
        fi
        if grep -qE '\]\([^)]*references/[^)]*\.md[^)]*\)|\]\([A-Za-z0-9_-]+\.md[^)]*\)' "$path"; then
            report "FST008" "$reference links to a sibling reference"
            return
        fi
        if grep -qE 'docs/' "$path"; then
            report "FST008" "$reference links into maintainer docs"
            return
        fi
        if grep -qE '(^|[[:space:]`(])/(Users|home|private|tmp|var|Volumes)/' "$path"; then
            report "FST008" "$reference contains a local absolute path"
            return
        fi
        if grep -qE '\`(tdd|codeprobe-testing|debugging|systematic-debugging|test-driven-development|golang-concurrency|golang-security)\`' "$path"; then
            report "FST008" "$reference contains public-skill routing"
            return
        fi
    done
}

check_skill_routing_and_completion() {
    if ! grep -qF '## Public-Skill Routing' "$SKILL_MD" || \
        ! grep -qiE 'test-first.*`tdd`|`tdd`.*test-first' "$SKILL_MD" || \
        ! grep -qiE 'audit.*`codeprobe-testing`|`codeprobe-testing`.*audit' "$SKILL_MD" || \
        ! grep -qiE 'debug.*`(debugging|systematic-debugging)`|`(debugging|systematic-debugging)`.*debug' "$SKILL_MD" || \
        ! grep -qiE 'tests-after.*finance oracle|finance oracle.*tests-after' "$SKILL_MD" || \
        ! grep -qiE 'public skill is unavailable' "$SKILL_MD" || \
        ! grep -qiE 'follow target project conventions' "$SKILL_MD" || \
        ! grep -qiE 'implement only the finance oracle' "$SKILL_MD" || \
        ! grep -qiE 'omit generic tutorial content' "$SKILL_MD"; then
        report "FST009" "public-skill routing or fallback missing"
        return
    fi
    if ! grep -qF '## Completion Criterion' "$SKILL_MD" || \
        ! grep -qiE 'every detected financial touchpoint' "$SKILL_MD" || \
        ! grep -qiE 'source.*invariant.*oracle.*applicable cases|source.*applicable cases.*invariant.*oracle' "$SKILL_MD" || \
        ! grep -qiE 'evidence-backed.*not applicable' "$SKILL_MD"; then
        report "FST009" "completion criterion missing"
    fi
}

require_files
check_frontmatter
check_description
check_on_demand_loading
check_runtime_reference_count
check_reference_headings
check_forbidden_runtime_content
check_reference_topology
check_skill_routing_and_completion

[ "$errors" -eq 0 ]
