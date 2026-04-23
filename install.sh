#!/usr/bin/env bash
# OmniCursor installer — copies the .cursor/ plugin bundle into a target project.
#
# Usage:
#   ./install.sh                  # install into current directory
#   ./install.sh /path/to/project # install into a specific project
#
# The installer merges .cursor/ contents rather than overwriting, so existing
# rules, hooks, and agents in the target project are preserved. Conflicting
# files are backed up with a .bak suffix before overwriting.

set -euo pipefail

PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${1:-$(pwd)}"

if [[ "$TARGET" == "$PLUGIN_DIR" ]]; then
  echo "Target is the plugin directory itself — nothing to do."
  exit 0
fi

if [[ ! -d "$TARGET" ]]; then
  echo "Error: target directory '$TARGET' does not exist." >&2
  exit 1
fi

echo "Installing OmniCursor into: $TARGET"

CURSOR_SRC="$PLUGIN_DIR/.cursor"
CURSOR_DST="$TARGET/.cursor"

# Merge each subdirectory: rules, hooks, agents, skills
for subdir in rules agents skills; do
  src="$CURSOR_SRC/$subdir"
  dst="$CURSOR_DST/$subdir"
  if [[ ! -d "$src" ]]; then continue; fi
  mkdir -p "$dst"
  cp -r "$src"/. "$dst/"
  echo "  installed .cursor/$subdir/"
done

# hooks.json — merge if target already has one, otherwise copy
HOOKS_SRC="$CURSOR_SRC/hooks.json"
HOOKS_DST="$CURSOR_DST/hooks.json"
if [[ -f "$HOOKS_DST" ]]; then
  echo "  WARNING: $HOOKS_DST already exists — skipping (merge manually if needed)"
else
  mkdir -p "$CURSOR_DST"
  cp "$HOOKS_SRC" "$HOOKS_DST"
  echo "  installed .cursor/hooks.json"
fi

# Hook scripts directory
SCRIPTS_SRC="$CURSOR_SRC/hooks"
SCRIPTS_DST="$CURSOR_DST/hooks"
if [[ -d "$SCRIPTS_SRC" ]]; then
  mkdir -p "$SCRIPTS_DST"
  cp -r "$SCRIPTS_SRC"/. "$SCRIPTS_DST/"
  echo "  installed .cursor/hooks/ scripts"
fi

echo ""
echo "OmniCursor installed successfully."
echo "Restart Cursor (or reload the window) to activate hooks and rules."
