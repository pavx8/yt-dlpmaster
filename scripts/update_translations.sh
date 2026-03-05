#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
I18N_DIR="$ROOT_DIR/app/i18n"

resolve_lupdate() {
  if command -v pyside6-lupdate >/dev/null 2>&1; then
    echo "pyside6-lupdate"
    return 0
  fi
  if command -v lupdate-qt6 >/dev/null 2>&1; then
    echo "lupdate-qt6"
    return 0
  fi
  if command -v lupdate >/dev/null 2>&1; then
    echo "lupdate"
    return 0
  fi

  for p in \
    /usr/lib/qt6/bin/lupdate \
    /usr/lib64/qt6/bin/lupdate \
    /usr/lib/qt6/libexec/lupdate \
    /usr/lib64/qt6/libexec/lupdate \
    /usr/lib/qt/bin/lupdate \
    /usr/lib64/qt/bin/lupdate
  do
    if [ -x "$p" ]; then
      echo "$p"
      return 0
    fi
  done

  return 1
}

if ! LUPDATE_BIN="$(resolve_lupdate)"; then
  echo "lupdate tool not found."
  echo "Install Qt Linguist tools (Qt6) or PySide6 tools package, then retry."
  echo "Examples:"
  echo "  - Arch: sudo pacman -S qt6-tools"
  echo "  - Fedora: sudo dnf install qt6-qttools"
  echo "  - Debian/Ubuntu: sudo apt install qt6-tools-dev-tools"
  exit 1
fi

"$LUPDATE_BIN" "$ROOT_DIR/app/cli.py" "$ROOT_DIR/app/ui" "$ROOT_DIR/app/core" -ts "$I18N_DIR/yt-dlpmaster_ru.ts"

echo "Translation source updated: $I18N_DIR/yt-dlpmaster_ru.ts"
