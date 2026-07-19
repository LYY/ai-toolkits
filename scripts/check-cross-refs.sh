#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -gt 1 ]; then
    printf 'usage: %s [repo-root]\n' "$0" >&2
    exit 2
fi

if [ "$#" -eq 1 ]; then
    REPO_ROOT="$(cd "$1" && pwd -P)"
else
    REPO_ROOT="$(git rev-parse --show-toplevel)"
fi
errors=0

red()  { printf '\033[31m%s\033[0m\n' "$*"; }
green() { printf '\033[32m%s\033[0m\n' "$*"; }

extract_refs() {
    local file="$1"
    perl -ne '
        while (/`([^`]*\.md)`/g) {
            my $ref = $1;
            next if $ref =~ /^https?:/;
            next if $ref =~ /[<>]/;
            next if $ref =~ /\s/;
            next if $ref eq "SKILL.md";
            next if $ref =~ /[*?]/;
            next if $ref eq ".md" || $ref =~ /^(?:file|ref-file|path)\.md$/;
            print "$ref\n";
        }
        while (/\(([^)]*\.md)\)/g) {
            my $ref = $1;
            next if $ref =~ /^https?:/;
            next if $ref =~ /[<>]/;
            next if $ref =~ /\s/;
            next if $ref eq "SKILL.md";
            next if $ref =~ /[*?]/;
            next if $ref eq ".md" || $ref =~ /^(?:file|ref-file|path)\.md$/;
            print "$ref\n";
        }
    ' "$file" 2>/dev/null || true
}

resolve_ref() {
    local base_dir="$1"
    local ref="$2"
    if [[ "$ref" == /* ]]; then
        echo "$REPO_ROOT$ref"
    elif [[ "$ref" == ./* ]] || [[ "$ref" == ../* ]]; then
        realpath "$base_dir/$ref" 2>/dev/null || echo "$base_dir/$ref"
    else
        echo "$base_dir/$ref"
    fi
}

check_ref() {
    local display_src="$1"
    local base_dir="$2"
    local ref="$3"
    shift 3
    local -a fallback_dirs=("$@")

    local resolved
    resolved="$(resolve_ref "$base_dir" "$ref")"
    [ -f "$resolved" ] && return 0

    for fb in "${fallback_dirs[@]}"; do
        resolved="$(resolve_ref "$fb" "$ref")"
        [ -f "$resolved" ] && return 0
    done

    red "  ❌ $display_src → $ref"
    errors=1
    return 1
}

skill_refs_dirs=()
for d in "$REPO_ROOT"/skills/*/references/; do
    [ -d "$d" ] && skill_refs_dirs+=("$d")
done

echo "=== Cross-Reference Dead Link Check ==="

# 1. Skills reference files
for ref_dir in "${skill_refs_dirs[@]}"; do
    skill_name="$(basename "$(dirname "$ref_dir")")"
    skill_root="$REPO_ROOT/skills/$skill_name"
    for src in "$ref_dir"*.md; do
        [ -f "$src" ] || continue
        src_name="$(basename "$src")"
        while IFS= read -r ref; do
            [ -z "$ref" ] && continue
            [ "$ref" = "$src_name" ] && continue
            check_ref "skills/$skill_name/references/$src_name" "$ref_dir" "$ref"
        done < <(extract_refs "$src")
        if grep -q 'SKILL\.md' "$src" 2>/dev/null; then
            [ -f "$skill_root/SKILL.md" ] || {
                red "  ❌ skills/$skill_name/references/$src_name → SKILL.md (not found)"
                errors=1
            }
        fi
    done
done

# 2. Docs — allow references to skill ref files + root files as fallback
if [ -d "$REPO_ROOT/docs" ]; then
    while IFS= read -r -d '' src; do
        src_rel="${src#$REPO_ROOT/}"
        src_dir="$(dirname "$src")"
        while IFS= read -r ref; do
            [ -z "$ref" ] && continue
            check_ref "$src_rel" "$src_dir" "$ref" "${skill_refs_dirs[@]}" "$REPO_ROOT"
        done < <(extract_refs "$src")
    done < <(find "$REPO_ROOT/docs" -name '*.md' -print0)
fi

# 3. Root-level markdown files
for src in "$REPO_ROOT"/*.md; do
    [ -f "$src" ] || continue
    src_name="$(basename "$src")"
    while IFS= read -r ref; do
        [ -z "$ref" ] && continue
        [ "$ref" = "$src_name" ] && continue
        check_ref "$src_name" "$REPO_ROOT" "$ref"
    done < <(extract_refs "$src")
done

# 4. Script references — generic: any scripts/*.py referenced from reference .md files
for src in "${skill_refs_dirs[@]}"/*.md; do
    [ -f "$src" ] || continue
    skill_dir="$(dirname "$(dirname "$src")")"
    src_rel="${src#$REPO_ROOT/}"
    while IFS= read -r script_ref; do
        [ -z "$script_ref" ] && continue
        [ -f "$skill_dir/$script_ref" ] || {
            red "  ❌ $src_rel → $script_ref (not found)"
            errors=1
        }
    done < <(perl -ne '
        while (/`(scripts\/[^`]+\.py)`/g)  { print "$1\n"; }
        while (/\((scripts\/[^)]+\.py)\)/g) { print "$1\n"; }
    ' "$src" 2>/dev/null || true)
done

echo ""
if [ "$errors" -eq 0 ]; then
    green "✓ All cross-references valid"
    exit 0
else
    red "✗ $errors dead reference(s) found"
    exit 1
fi
