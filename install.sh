#!/usr/bin/env bash
# install.sh — Symlink OmniCursor plugin into a target project.
#
# Hooks resolve back to this repo via Path(__file__).resolve(), so they always
# use the canonical source. Updating OmniCursor updates all installed projects.
#
# Usage:
#   ./install.sh <target-project-path>
#   ./install.sh <target-project-path> --dry-run    # preview without writing
#   ./install.sh <target-project-path> --status     # show link state
#   ./install.sh <target-project-path> --uninstall  # remove symlinks

set -euo pipefail

OMNICURSOR_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ---------------------------------------------------------------------------
# Arg parsing
# ---------------------------------------------------------------------------

DRY_RUN=0
UNINSTALL=0
STATUS=0
TARGET=""

for arg in "$@"; do
    case "$arg" in
        --dry-run)   DRY_RUN=1 ;;
        --uninstall) UNINSTALL=1 ;;
        --status)    STATUS=1 ;;
        -*)          echo "Unknown flag: $arg" >&2; exit 1 ;;
        *)           TARGET="$arg" ;;
    esac
done

if [ -z "$TARGET" ]; then
    echo "Usage: install.sh <target-project-path> [--dry-run | --status | --uninstall]" >&2
    exit 1
fi

TARGET="$(cd "$TARGET" && pwd)"

if [ "$TARGET" = "$OMNICURSOR_ROOT" ]; then
    echo "Target is the OmniCursor repo itself — nothing to do." >&2
    exit 0
fi

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_link() {
    local src="$1" dst="$2"
    if [ "$DRY_RUN" = "1" ]; then
        echo "  [dry-run] ln -sfn $src $dst"
        return
    fi
    ln -sfn "$src" "$dst"
}

_mkdir() {
    local dir="$1"
    [ "$DRY_RUN" = "1" ] && { echo "  [dry-run] mkdir -p $dir"; return; }
    mkdir -p "$dir"
}

_unlink() {
    local dst="$1" src="$2"
    if [ -L "$dst" ] && [ "$(readlink "$dst")" = "$src" ]; then
        [ "$DRY_RUN" = "1" ] && { echo "  [dry-run] rm $dst"; return; }
        rm "$dst"
        echo "  removed: $dst_rel"
    fi
}

_status_icon() {
    local dst="$1" src="$2"
    if [ -L "$dst" ] && [ "$(readlink "$dst")" = "$src" ]; then
        echo "linked"
    elif [ -e "$dst" ]; then
        echo "manual"
    else
        echo "missing"
    fi
}

# ---------------------------------------------------------------------------
# Build link manifest
# ---------------------------------------------------------------------------
# Format: "dst_path_relative_to_target|abs_src_path"

declare -a LINKS=(
    ".cursor/hooks.json|$OMNICURSOR_ROOT/.cursor/hooks.json"
    ".cursor/hooks|$OMNICURSOR_ROOT/.cursor/hooks"
    ".cursor/agents|$OMNICURSOR_ROOT/.cursor/agents"
)

for rule in "$OMNICURSOR_ROOT/.cursor/rules/"*.mdc; do
    [ -f "$rule" ] || continue
    name="$(basename "$rule")"
    LINKS+=(".cursor/rules/$name|$rule")
done

for skill in "$OMNICURSOR_ROOT/skills/"*.md; do
    [ -f "$skill" ] || continue
    [ "$(basename "$skill")" = "README.md" ] && continue
    name="$(basename "$skill")"
    LINKS+=("skills/$name|$skill")
done

# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

if [ "$STATUS" = "1" ]; then
    echo "OmniCursor plugin status in: $TARGET"
    echo ""
    for entry in "${LINKS[@]}"; do
        dst_rel="${entry%%|*}"
        src="${entry##*|}"
        dst="$TARGET/$dst_rel"
        icon="$(_status_icon "$dst" "$src")"
        case "$icon" in
            linked)  echo "  ✓ $dst_rel" ;;
            manual)  echo "  ~ $dst_rel  (file exists, not our symlink)" ;;
            missing) echo "  ✗ $dst_rel  (not installed)" ;;
        esac
    done
    exit 0
fi

# ---------------------------------------------------------------------------
# Uninstall
# ---------------------------------------------------------------------------

if [ "$UNINSTALL" = "1" ]; then
    echo "Removing OmniCursor symlinks from: $TARGET"
    echo ""
    for entry in "${LINKS[@]}"; do
        dst_rel="${entry%%|*}"
        src="${entry##*|}"
        dst="$TARGET/$dst_rel"
        if [ -L "$dst" ] && [ "$(readlink "$dst")" = "$src" ]; then
            [ "$DRY_RUN" = "1" ] && { echo "  [dry-run] rm $dst"; continue; }
            rm "$dst"
            echo "  removed: $dst_rel"
        fi
    done
    echo ""
    echo "Done. Symlinks removed (directories left intact)."
    exit 0
fi

# ---------------------------------------------------------------------------
# Install
# ---------------------------------------------------------------------------

echo "Installing OmniCursor into: $TARGET"
[ "$DRY_RUN" = "1" ] && echo "(dry-run — no files written)"
echo ""

_mkdir "$TARGET/.cursor"
_mkdir "$TARGET/.cursor/rules"
_mkdir "$TARGET/skills"

for entry in "${LINKS[@]}"; do
    dst_rel="${entry%%|*}"
    src="${entry##*|}"
    dst="$TARGET/$dst_rel"

    if [ -e "$dst" ] && [ ! -L "$dst" ]; then
        echo "  SKIP $dst_rel — real file found at $dst; remove it manually to install"
        continue
    fi

    if [ -L "$dst" ] && [ "$(readlink "$dst")" = "$src" ]; then
        echo "  ok   $dst_rel  (already linked)"
        continue
    fi

    _link "$src" "$dst"
    echo "  linked: $dst_rel"
done

echo ""
echo "Done. Restart Cursor in $TARGET to activate hooks and rules."
