#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
I18N_DIR="$ROOT_DIR/app/i18n"

resolve_lrelease() {
  if command -v pyside6-lrelease >/dev/null 2>&1; then
    echo "pyside6-lrelease"
    return 0
  fi
  if command -v lrelease-qt6 >/dev/null 2>&1; then
    echo "lrelease-qt6"
    return 0
  fi
  if command -v lrelease >/dev/null 2>&1; then
    echo "lrelease"
    return 0
  fi

  for p in \
    /usr/lib/qt6/bin/lrelease \
    /usr/lib64/qt6/bin/lrelease \
    /usr/lib/qt6/libexec/lrelease \
    /usr/lib64/qt6/libexec/lrelease \
    /usr/lib/qt/bin/lrelease \
    /usr/lib64/qt/bin/lrelease
  do
    if [ -x "$p" ]; then
      echo "$p"
      return 0
    fi
  done

  return 1
}

if ! LRELEASE_BIN="$(resolve_lrelease)"; then
  echo "lrelease tool not found."
  echo "Install Qt Linguist tools (Qt6) or PySide6 tools package, then retry."
  echo "Examples:"
  echo "  - Arch: sudo pacman -S qt6-tools"
  echo "  - Fedora: sudo dnf install qt6-qttools"
  echo "  - Debian/Ubuntu: sudo apt install qt6-tools-dev-tools"
  exit 1
fi

for ts in "$I18N_DIR"/*.ts; do
  [ -f "$ts" ] || continue
  "$LRELEASE_BIN" "$ts"
done

echo "Translations compiled to .qm files in $I18N_DIR"
