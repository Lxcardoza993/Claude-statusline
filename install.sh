#!/usr/bin/env bash
# One-shot installer for the Claude Statusline shared customizations (non-plugin path).
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/Lxcardoza993/Claude-statusline/main/install.sh | bash
#   # or clone and run: ./install.sh
#
# For the richer path (auto health-check hook + /claude-statusline commands + updates),
# install as a Claude Code plugin instead — see README.md.
set -euo pipefail

REPO="Lxcardoza993/Claude-statusline"
BRANCH="main"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "==> Cloning $REPO..."
if ! command -v git >/dev/null 2>&1; then
  echo "git not found. Install git, or use the plugin path (see README)." >&2
  exit 1
fi
git clone --depth 1 -b "$BRANCH" "https://github.com/$REPO.git" "$TMP/repo" 2>/dev/null \
  || git clone --depth 1 "https://github.com/$REPO.git" "$TMP/repo"

echo "==> Running installer (copies statusline.py + wires settings.json)..."
python3 "$TMP/repo/claude-statusline/scripts/install.py"

echo
echo "==> Done. Restart Claude Code for the env vars to take effect."
echo "    Tip: for an auto health-check hook and /claude-statusline commands, install as a plugin:"
echo "      /plugin marketplace add Lxcardoza993/Claude-statusline"
echo "      /plugin install claude-statusline@claude-statusline-market"
