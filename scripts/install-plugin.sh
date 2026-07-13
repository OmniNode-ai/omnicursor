#!/usr/bin/env bash
# install-plugin.sh — Install OmniCursor as a Cursor user plugin.
#
# Stages the curated runtime payload (A10.4) into build/plugin/ — per-entry
# symlinks back into this repository — and exposes it to Cursor via a single
# symlink at ~/.cursor/plugins/local/omnicursor. Dev junk (tests/, docker/,
# eval/, compose.yaml, .git, ...) never reaches the installed plugin.
#
# Hooks resolve their real location with Path(__file__).resolve(), so they
# execute against this checkout regardless of the symlink chain; the payload
# controls what Cursor (and anyone auditing the install) sees.
#
# Usage:
#   ./scripts/install-plugin.sh
#   ./scripts/install-plugin.sh --dry-run
#   ./scripts/install-plugin.sh --status
#   ./scripts/install-plugin.sh --uninstall            # keeps ~/.omnicursor/ data
#   ./scripts/install-plugin.sh --uninstall --purge    # also removes ~/.omnicursor/

set -euo pipefail

OMNICURSOR_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLUGIN_NAME="omnicursor"
PLUGIN_PARENT="${CURSOR_PLUGINS_LOCAL:-$HOME/.cursor/plugins/local}"
TARGET="$PLUGIN_PARENT/$PLUGIN_NAME"
STAGING="$OMNICURSOR_ROOT/build/plugin"

# Curated runtime payload (A10.4): repo-root-relative entries staged into
# build/plugin/. src/omnicursor (not src/) keeps egg-info out; config/ ships
# the event registry the emit daemon is spawned with (daemon_ensure.py
# resolves it via REPO_ROOT — see P6 in the phase plan).
PAYLOAD_ENTRIES=(
    ".cursor"
    ".cursor-plugin"
    "src/omnicursor"
    "config"
    "pyproject.toml"
    "README.md"
    "LICENSE"
    "CHANGELOG.md"
)

DRY_RUN=0
UNINSTALL=0
STATUS=0
PURGE=0

for arg in "$@"; do
    case "$arg" in
        --dry-run)   DRY_RUN=1 ;;
        --uninstall) UNINSTALL=1 ;;
        --status)    STATUS=1 ;;
        --purge)     PURGE=1 ;;
        -*)          echo "Unknown flag: $arg" >&2; exit 1 ;;
        *)           echo "Unexpected argument: $arg" >&2; exit 1 ;;
    esac
done

if [ "$PURGE" = "1" ] && [ "$UNINSTALL" != "1" ]; then
    echo "ERROR: --purge only applies with --uninstall" >&2
    exit 1
fi

_stage_payload() {
    if [ "$DRY_RUN" = "1" ]; then
        echo "  [dry-run] rm -rf $STAGING && mkdir -p $STAGING"
        for entry in "${PAYLOAD_ENTRIES[@]}"; do
            echo "  [dry-run] ln -s $OMNICURSOR_ROOT/$entry $STAGING/$entry"
        done
        return
    fi
    rm -rf "$STAGING"
    mkdir -p "$STAGING"
    for entry in "${PAYLOAD_ENTRIES[@]}"; do
        case "$entry" in
            */*) mkdir -p "$STAGING/$(dirname "$entry")" ;;
        esac
        ln -s "$OMNICURSOR_ROOT/$entry" "$STAGING/$entry"
        echo "  staged: $entry"
    done
}

_link() {
    local src="$1" dst="$2"
    if [ "$DRY_RUN" = "1" ]; then
        echo "  [dry-run] mkdir -p $(dirname "$dst")"
        echo "  [dry-run] ln -sfn $src $dst"
        return
    fi
    mkdir -p "$(dirname "$dst")"
    ln -sfn "$src" "$dst"
}

_status_icon() {
    local dst="$1"
    if [ -L "$dst" ] && [ "$(readlink -f "$dst")" = "$(readlink -f "$STAGING")" ]; then
        echo "linked"
    elif [ -L "$dst" ] && [ "$(readlink -f "$dst")" = "$(readlink -f "$OMNICURSOR_ROOT")" ]; then
        echo "legacy"
    elif [ -e "$dst" ]; then
        echo "manual"
    else
        echo "missing"
    fi
}

if [ "$STATUS" = "1" ]; then
    echo "OmniCursor plugin: $TARGET"
    icon="$(_status_icon "$TARGET")"
    case "$icon" in
        linked)  echo "  status: installed (symlink → $STAGING)" ;;
        legacy)  echo "  status: legacy whole-repo install — rerun ./scripts/install-plugin.sh to migrate to the curated payload" ;;
        manual)  echo "  status: path exists but is not our symlink" ;;
        missing) echo "  status: not installed" ;;
    esac
    exit 0
fi

if [ "$UNINSTALL" = "1" ]; then
    echo "Removing OmniCursor plugin symlink..."
    if [ -L "$TARGET" ]; then
        resolved="$(readlink -f "$TARGET")"
        if [ "$resolved" = "$(readlink -f "$STAGING")" ] || [ "$resolved" = "$(readlink -f "$OMNICURSOR_ROOT")" ]; then
            if [ "$DRY_RUN" = "1" ]; then
                echo "  [dry-run] rm $TARGET"
            else
                rm "$TARGET"
                echo "  removed: $TARGET"
            fi
        else
            echo "  skip: $TARGET exists but is not managed by this script" >&2
            exit 1
        fi
    elif [ -e "$TARGET" ]; then
        echo "  skip: $TARGET exists but is not managed by this script" >&2
        exit 1
    else
        echo "  nothing to remove"
    fi

    if [ -d "$STAGING" ]; then
        if [ "$DRY_RUN" = "1" ]; then
            echo "  [dry-run] rm -rf $STAGING"
        else
            rm -rf "$STAGING"
            echo "  removed staging: $STAGING"
        fi
    fi

    # A10.5 — opt-in local-data purge. Plain --uninstall never touches
    # ~/.omnicursor/ (learned_patterns.json, outbox.jsonl, events.jsonl,
    # emit.sock/pid, event-spool/, logs/, hooks-disabled marker).
    if [ "$PURGE" = "1" ]; then
        OMNICURSOR_DATA="${OMNICURSOR_DATA_DIR:-$HOME/.omnicursor}"
        case "$OMNICURSOR_DATA" in
            ""|"/"|"$HOME")
                echo "  refuse to purge unsafe data dir: '$OMNICURSOR_DATA'" >&2
                exit 1
                ;;
        esac
        if [ -d "$OMNICURSOR_DATA" ]; then
            if [ "$DRY_RUN" = "1" ]; then
                echo "  [dry-run] rm -rf $OMNICURSOR_DATA"
            else
                rm -rf "$OMNICURSOR_DATA"
                echo "  purged local data: $OMNICURSOR_DATA"
            fi
        else
            echo "  no local data to purge ($OMNICURSOR_DATA)"
        fi
    fi
    exit 0
fi

echo "Installing OmniCursor Cursor plugin..."
[ "$DRY_RUN" = "1" ] && echo "(dry-run — no files written)"
echo "  source: $OMNICURSOR_ROOT"
echo "  staging: $STAGING"
echo "  target: $TARGET"
echo ""

if [ -e "$TARGET" ] && [ ! -L "$TARGET" ]; then
    echo "ERROR: $TARGET exists and is not a symlink. Remove or rename it first." >&2
    exit 1
fi

if [ -L "$TARGET" ]; then
    resolved="$(readlink -f "$TARGET")"
    if [ "$resolved" != "$(readlink -f "$STAGING")" ] && [ "$resolved" != "$(readlink -f "$OMNICURSOR_ROOT")" ]; then
        echo "ERROR: $TARGET points elsewhere. Use --uninstall on the other install first." >&2
        exit 1
    fi
fi

_stage_payload
_link "$STAGING" "$TARGET"
echo "  linked"

echo ""
echo "Next steps:"
echo "  1. Restart Cursor or run: Developer: Reload Window"
echo "  2. Settings → Rules — confirm OmniCursor rules/skills are available"
echo "  3. Open any project — hooks and routing apply globally via the plugin"
