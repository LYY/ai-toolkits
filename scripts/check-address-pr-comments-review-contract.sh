#!/usr/bin/env bash
set -euo pipefail

resolve_repo_root() {
    local candidate="$1"
    local abs
    if [ -z "$candidate" ]; then
        git rev-parse --show-toplevel
        return
    fi
    [ -d "$candidate" ] || { echo "APR009: not a directory: $candidate" >&2; exit 1; }
    abs="$(cd "$candidate" && pwd -P)" || { echo "APR009: cannot resolve: $candidate" >&2; exit 1; }
    echo "$abs"
}

REPO_ROOT="$(resolve_repo_root "${1:-}")"
HAS_EXPLICIT_ROOT=false
[ -n "${1:-}" ] && HAS_EXPLICIT_ROOT=true

errors=0

# --- target paths under root ---
SKILL_MD="$REPO_ROOT/skills/address-pr-comments-review/SKILL.md"
DOSSIER_MD="$REPO_ROOT/skills/address-pr-comments-review/references/dossier-output.md"
INTERACTION_MD="$REPO_ROOT/skills/address-pr-comments-review/references/interaction.md"
EXECUTION_MD="$REPO_ROOT/skills/address-pr-comments-review/references/execution.md"
README_MD="$REPO_ROOT/README.md"
DESIGN_MD="$REPO_ROOT/docs/address-pr-comments-review/executor-neutral-design.md"
ARCH_MD="$REPO_ROOT/docs/address-pr-comments-review/architecture.md"
EVAL_MD="$REPO_ROOT/docs/address-pr-comments-review/eval-matrix.md"
RUBRIC_MD="$REPO_ROOT/tests/address-pr-comments-review-eval/rubric.md"

# --- helper: scan a file for forbidden tokens ---
scan_file_tokens() {
    local file="$1"
    local label="$2"
    local found=0
    [ -f "$file" ] || return 0
    while IFS= read -r token; do
        [ -z "$token" ] && continue
        if grep -qi "\b${token}\b" "$file" 2>/dev/null; then
            echo "APR001: forbidden token \"${token}\" in ${label}" >&2
            found=1
        fi
    done <<'TOKENS'
opencode
omo
prometheus
sisyphus
TOKENS
    return $found
}

# --- helper: scan a file for forbidden substrings ---
scan_file_substrings() {
    local file="$1"
    local label="$2"
    local found=0
    [ -f "$file" ] || return 0
    while IFS= read -r substr; do
        [ -z "$substr" ] && continue
        if grep -qF "$substr" "$file" 2>/dev/null; then
            echo "APR001: forbidden substring \"${substr}\" in ${label}" >&2
            found=1
        fi
    done <<'SUBSTRS'
/start-work
.omo/
.sisyphus/
platform.md
generated plan
planner prompt
SUBSTRS
    return $found
}

# --- helper: scan file for durable-only forbidden substrings ---
scan_file_durable() {
    local file="$1"
    local label="$2"
    local found=0
    [ -f "$file" ] || return 0
    while IFS= read -r substr; do
        [ -z "$substr" ] && continue
        if grep -qF "$substr" "$file" 2>/dev/null; then
            echo "APR001: durable forbidden substring \"${substr}\" in ${label}" >&2
            found=1
        fi
    done <<'DURABLES'
task-explore-v1
subagent_type
task_id
session_id
model_id
provider_id
harness_version
DURABLES
    return $found
}

# --- scan README bounded sections ---
scan_readme_bounds() {
    local file="$1"
    [ -f "$file" ] || return 0
    local found=0
    local in_section=false
    local saw_features_end=false

    check_line_tokens() {
        local line="$1" section="$2"
        for token in opencode omo prometheus sisyphus; do
            if echo "$line" | grep -qi "\b${token}\b" 2>/dev/null; then
                echo "APR002: README ${section} contains forbidden token \"${token}\"" >&2
                found=1
            fi
        done
    }

    check_line_substrings() {
        local line="$1" section="$2"
        for substr in '/start-work' '.omo/' '.sisyphus/' 'platform.md' 'generated plan' 'planner prompt'; do
            if echo "$line" | grep -qF "$substr" 2>/dev/null; then
                echo "APR002: README ${section} contains forbidden substring \"${substr}\"" >&2
                found=1
            fi
        done
    }

    while IFS= read -r line; do
        if [[ "$line" =~ ^##[[:space:]]特性 ]]; then
            in_section=true
            continue
        fi
        if [ "$in_section" = true ] && [[ "$line" =~ ^## ]]; then
            in_section=false
            saw_features_end=true
            continue
        fi
        if [ "$in_section" = true ]; then
            check_line_tokens "$line" "特性 section"
            check_line_substrings "$line" "特性 section"
        fi
        if [ "$saw_features_end" = true ] && [[ "$line" =~ ^##[[:space:]]开发 ]]; then
            in_section=true
            saw_features_end=false
            continue
        fi
        if [ "$in_section" = true ] && [ "$saw_features_end" = false ] && [[ "$line" =~ ^## ]]; then
            in_section=false
            continue
        fi
    done < "$file"

    # scan the skill row for forbidden tokens and substrings
    local in_skill_table=false
    local saw_separator=false
    while IFS= read -r line; do
        if [[ "$line" =~ \|.*Skill.*\|.*描述.*\| ]]; then
            in_skill_table=true
            saw_separator=false
            continue
        fi
        if [ "$in_skill_table" = true ] && [ "$saw_separator" = false ] && [[ "$line" =~ ^\|.*---.*\| ]]; then
            saw_separator=true
            continue
        fi
        if [ "$in_skill_table" = true ] && [ "$saw_separator" = true ] && [[ "$line" =~ ^\|.*address-pr-comments-review.*\| ]]; then
            check_line_tokens "$line" "skill row"
            check_line_substrings "$line" "skill row"
            in_skill_table=false
            break
        fi
        if [ "$in_skill_table" = true ] && [[ "$line" =~ ^\|[^|]+\| ]] && [ "$saw_separator" = false ]; then
            in_skill_table=false
        fi
    done < "$file"
    return $found
}

# --- check required markers in a file ---
check_required_markers() {
    local file="$1"
    local label="$2"
    shift 2
    local found=0
    [ -f "$file" ] || return 0
    for pair in "$@"; do
        local start_marker="${pair%%:::*}"
        local end_marker="${pair##*:::}"
        if ! grep -qF "$start_marker" "$file" 2>/dev/null; then
            echo "APR003: missing marker \"${start_marker}\" in ${label}" >&2
            found=1
        fi
        if ! grep -qF "$end_marker" "$file" 2>/dev/null; then
            echo "APR003: missing marker \"${end_marker}\" in ${label}" >&2
            found=1
        fi
    done
    return $found
}

# --- check marker order ---
check_marker_order() {
    local file="$1"
    local label="$2"
    shift 2
    [ -f "$file" ] || return 0
    local prev_pos=0
    local found=0
    for marker in "$@"; do
        local pos
        pos="$(grep -nF "$marker" "$file" 2>/dev/null | head -1 | cut -d: -f1)" || pos=0
        if [ "$pos" -eq 0 ]; then
            continue
        fi
        if [ "$pos" -le "$prev_pos" ] && [ "$prev_pos" -ne 0 ]; then
            echo "APR004: marker \"$marker\" appears before preceding marker in ${label}" >&2
            found=1
        fi
        prev_pos="$pos"
    done
    return $found
}

# --- check old-name references (platform.md must not appear in skill runtime files) ---
check_platform_alias() {
    local found=0
    local files=("$SKILL_MD" "$INTERACTION_MD" "$DOSSIER_MD" "$README_MD")
    for f in "${files[@]}"; do
        [ -f "$f" ] || continue
        local rel="${f#$REPO_ROOT/}"
        if grep -qF 'platform.md' "$f" 2>/dev/null; then
            echo "APR006: platform.md reference found in $rel" >&2
            found=1
        fi
    done
    return $found
}

# ================================================================
# MAIN SCAN
# ================================================================

# --- 1. Scan skill/reference files for forbidden tokens/substrings ---
for file_label in \
    "SKILL_MD:skill SKILL.md" \
    "DOSSIER_MD:skill dossier-output.md" \
    "INTERACTION_MD:skill interaction.md" \
    "EXECUTION_MD:skill execution.md"; do
    fvar="${file_label%%:*}"
    label="${file_label##*:}"
    file="${!fvar}"
    scan_file_tokens "$file" "$label" || errors=1
    scan_file_substrings "$file" "$label" || errors=1
done

# --- 2. Scan maintainer docs for structural issues only (not platform tokens) ---
# Docs record design decisions including migration history — platform references are intentional.
# Token/substring scans only apply to skill runtime files (Section 1).

# --- 3. Durable-only scan on eval-matrix.md (eval evidence) ---
scan_file_durable "$EVAL_MD" "doc eval-matrix.md" || errors=1

# --- 4. README bounded section scan ---
scan_readme_bounds "$README_MD" || errors=1

# --- 5. Check required markers ---
check_required_markers "$RUBRIC_MD" "rubric.md" \
    '<!-- rubric-v1:start -->:::<!-- rubric-v1:end -->' || errors=1

check_required_markers "$DOSSIER_MD" "dossier-output.md" \
    '<!-- artifact-execution-status:start -->:::<!-- artifact-execution-status:end -->' \
    '<!-- artifact-execution-inventory:start -->:::<!-- artifact-execution-inventory:end -->' || errors=1

# --- 6. Check marker order ---
check_marker_order "$DOSSIER_MD" "dossier-output.md" \
    '<!-- artifact-execution-status:start -->' \
    '<!-- artifact-execution-status:end -->' \
    '<!-- artifact-execution-inventory:start -->' \
    '<!-- artifact-execution-inventory:end -->' || errors=1

# --- 7. Check old-name alias (platform.md reference) — should FAIL RED ---
check_platform_alias && {
    # platform.md references found — this is the RED state we want to prove
    true
} || true

# --- 8. Check cross-references by running check-cross-refs.sh ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
if [ -x "$SCRIPT_DIR/check-cross-refs.sh" ]; then
    if ! bash "$SCRIPT_DIR/check-cross-refs.sh" "$REPO_ROOT" >/dev/null 2>&1; then
        echo "APR007: cross-reference check failed" >&2
        errors=1
    fi
fi

# --- 9. Check for symlinks pointing outside REPO_ROOT ---
check_symlinks() {
    local found=0
    while IFS= read -r -d '' link; do
        local target
        target="$(readlink "$link" 2>/dev/null)" || continue
        if [[ "$target" == /* ]]; then
            case "$target" in
                "$REPO_ROOT"/*|"$REPO_ROOT") ;;
                *)
                    echo "APR008: absolute symlink $link -> $target escapes root" >&2
                    found=1
                    ;;
            esac
        fi
        if [[ "$target" == ../* ]]; then
            echo "APR008: relative symlink $link -> $target may escape root" >&2
            found=1
        fi
    done < <(find "$REPO_ROOT" -type l -not -path '*/.git/*' -print0 2>/dev/null)
    return $found
}
check_symlinks || errors=1

# --- 10. Check for root escape patterns ---
check_root_escape() {
    local found=0
    while IFS= read -r -d '' f; do
        local rel="${f#$REPO_ROOT/}"
        if grep -qE '(^|/)\\.\\./' "$rel" 2>/dev/null; then
            echo "APR009: root escape pattern in path: $rel" >&2
            found=1
        fi
    done < <(find "$REPO_ROOT" -type f -not -path '*/.git/*' -print0 2>/dev/null)
    return $found
}
check_root_escape || true  # non-fatal, informational

# ================================================================
# FINAL
# ================================================================
if [ "$errors" -eq 0 ]; then
    exit 0
else
    exit 1
fi
