#!/usr/bin/env bash
set -euo pipefail

# Install hf_fast_mdl as a global CLI on macOS.
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

ensure_path_in_zsh() {
  local bin_dir="$1"
  local line="export PATH=\"$bin_dir:\$PATH\""

  for rc in "$HOME/.zprofile" "$HOME/.zshrc"; do
    if [[ ! -f "$rc" ]]; then
      touch "$rc"
    fi
    if ! grep -Fq "$line" "$rc"; then
      printf "\n# Added by hf_fast_mdl installer\n%s\n" "$line" >> "$rc"
    fi
  done
}

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 is required but not found." >&2
  exit 1
fi

if command -v pipx >/dev/null 2>&1; then
  echo "Installing with pipx (recommended)..."
  pipx ensurepath >/dev/null 2>&1 || true
  pipx install --force "$REPO_DIR"
  echo
  echo "If this is your first pipx install, open a new terminal session."
  echo "Installed. You can now run:"
  echo "  hf_fast_mdl --help"
  echo "  hfmdl --help"
  exit 0
fi

echo "pipx not found; falling back to user install via pip..."
python3 -m pip install --user --upgrade "$REPO_DIR"

USER_BASE="$(python3 -m site --user-base)"
BIN_DIR="$USER_BASE/bin"
ensure_path_in_zsh "$BIN_DIR"

echo
echo "Added $BIN_DIR to ~/.zprofile and ~/.zshrc if needed."
echo "Run this once now to use it immediately in current shell:"
echo "  export PATH=\"$BIN_DIR:\$PATH\""
echo

echo "Installed. You can now run:"
echo "  hf_fast_mdl --help"
echo "  hfmdl --help"
