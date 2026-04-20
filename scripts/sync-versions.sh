#!/usr/bin/env bash
# Sync all workspace sub-package versions to match the root package version.
# Also rewrites the exact-version pins for geneweaver-* dependencies in the root
# pyproject.toml so that a published geneweaver-api==X.Y.Z always
# pulls exactly geneweaver-core==X.Y.Z, geneweaver-db==X.Y.Z, etc.
#
# Usage:
#   ./scripts/sync-versions.sh                     # apply root version to all sub-packages and update README.md
#   ./scripts/sync-versions.sh --no-readme         # skip rewriting GitHub URLs in README.md
#   ./scripts/sync-versions.sh --dry-run           # preview without writing
#   ./scripts/sync-versions.sh --dry-run --no-readme  # preview package syncs only
set -euo pipefail

ROOT_VERSION=$(grep '^version = ' pyproject.toml | head -1 | awk -F'=' '{print $2}' | tr -d ' "')
DRY_RUN=""
UPDATE_README="yes"

for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN="--dry-run" ;;
        --no-readme) UPDATE_README="" ;;
        *) echo "Unknown argument: $arg"; exit 1 ;;
    esac
done

echo "Root version: $ROOT_VERSION"

for toml in packages/*/pyproject.toml; do
    pkg_name=$(grep '^name = ' "$toml" | head -1 | awk -F'=' '{print $2}' | tr -d ' "')
    current=$(grep '^version = ' "$toml" | head -1 | awk -F'=' '{print $2}' | tr -d ' "')

    if [ "$current" = "$ROOT_VERSION" ]; then
        echo "  $pkg_name: $current (already in sync)"
    else
        echo "  $pkg_name: $current -> $ROOT_VERSION"
        if [ -z "$DRY_RUN" ]; then
            sed -i.bak -E "s/^version = ".*"/version = "\"${ROOT_VERSION}\""/" "$toml"
            rm -f "$toml.bak"
        fi
    fi
done

# Rewrite exact-version pins for geneweaver-* workspace packages in root pyproject.toml.
echo ""
echo "Root pyproject.toml geneweaver-* pin rewrite: -> ^${ROOT_VERSION}"
if [ -n "$DRY_RUN" ]; then
    echo "  Lines in pyproject.toml that would be updated:"
    grep -nE '^(geneweaver-(core|db|client))\s*=\s*.*' pyproject.toml | sed "s/^/    /" || echo "    (no matching lines found)"
else
    sed -i.bak -E 's/^(geneweaver-(core|db|client))[[:space:]]*=[[:space:]]*".*"/\1 = "^'"${ROOT_VERSION}"'"/' pyproject.toml
    rm -f pyproject.toml.bak
    echo "  pyproject.toml updated."
fi

if [ -n "$UPDATE_README" ]; then
    echo ""
    echo "README.md GitHub URL rewrite: blob/(main|v*) -> blob/v${ROOT_VERSION}"
    if [ -n "$DRY_RUN" ]; then
        # Show lines that would change without writing
        echo "  Lines in README.md that would be updated:"
        grep -nE "(github\.com|raw\.githubusercontent\.com)/TheJacksonLaboratory/geneweaver-api/(blob/)?(main|v[^/]+)/" README.md | sed "s/^/    /" || echo "    (no matching URLs found)"
    else
        sed -i.bak -E -e "s#/blob/(main|v[^/]*)/#/blob/v${ROOT_VERSION}/#g" -e "s#geneweaver-api/(main|v[^/]*)/#geneweaver-api/v${ROOT_VERSION}/#g" README.md
        rm -f README.md.bak
        echo "  README.md updated."
    fi
fi

if [ -z "$DRY_RUN" ]; then
    echo ""
    echo "Run 'uv lock' to update the lockfile."
fi
