from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QLibraryInfo, QLocale, QSettings, QTranslator
from PySide6.QtWidgets import QApplication

from app.core.ca import ensure_windows_ca_bundle
from app.core.settings import (
    apply_components_settings,
    ensure_default_settings,
    load_components_settings,
    load_ui_language,
)
from app.ui.main_window import MainWindow


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _i18n_dir() -> Path:
    return Path(__file__).resolve().parent / "i18n"


def _resolve_lrelease() -> str | None:
    for name in ("pyside6-lrelease", "lrelease-qt6", "lrelease"):
        resolved = shutil.which(name)
        if resolved:
            return resolved

    for candidate in (
        "/usr/lib/qt6/bin/lrelease",
        "/usr/lib64/qt6/bin/lrelease",
        "/usr/lib/qt6/libexec/lrelease",
        "/usr/lib64/qt6/libexec/lrelease",
        "/usr/lib/qt/bin/lrelease",
        "/usr/lib64/qt/bin/lrelease",
    ):
        path = Path(candidate)
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
    return None


def _auto_build_translations() -> None:
    i18n_dir = _i18n_dir()
    ts_files = sorted(i18n_dir.glob("*.ts"))
    if not ts_files:
        return

    outdated_ts: list[Path] = []
    for ts_file in ts_files:
        qm_file = ts_file.with_suffix(".qm")
        if (not qm_file.exists()) or qm_file.stat().st_mtime < ts_file.stat().st_mtime:
            outdated_ts.append(ts_file)

    if not outdated_ts:
        return

    lrelease = _resolve_lrelease()
    if not lrelease:
        print(
            "Warning: translation sources changed, but lrelease tool was not found. "
            "Install Qt Linguist tools or PySide6 tools package.",
            file=sys.stderr,
        )
        return

    for ts_file in outdated_ts:
        try:
            subprocess.run([lrelease, str(ts_file)], check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            details = (exc.stderr or exc.stdout or "").strip()
            if details:
                print(f"Warning: failed to build translation {ts_file.name}: {details}", file=sys.stderr)
            else:
                print(f"Warning: failed to build translation {ts_file.name}", file=sys.stderr)


def _create_portable_settings() -> QSettings:
    if getattr(sys, "frozen", False):
        app_dir = Path(sys.executable).resolve().parent
    else:
        app_dir = _project_root()
    settings_path = app_dir / "settings.ini"
    return QSettings(str(settings_path), QSettings.IniFormat)


def _install_app_translator(app: QApplication, language: str | None) -> QTranslator | None:
    locale_name = language or QLocale.system().name()
    base_name = locale_name.split(".")[0]
    i18n_dir = _i18n_dir()
    candidates = [base_name]
    if "_" in base_name:
        candidates.append(base_name.split("_", 1)[0])

    translator = QTranslator(app)
    for candidate in candidates:
        qm_path = i18n_dir / f"yt-dlpmaster_{candidate}.qm"
        if qm_path.exists() and translator.load(str(qm_path)):
            app.installTranslator(translator)
            return translator
    return None


def _install_qt_translator(app: QApplication, language: str | None) -> QTranslator | None:
    locale_name = language or QLocale.system().name()
    base_name = locale_name.split(".")[0]
    candidates = [base_name]
    if "_" in base_name:
        candidates.append(base_name.split("_", 1)[0])

    translator = QTranslator(app)
    translations_dir = QLibraryInfo.path(QLibraryInfo.TranslationsPath)
    for candidate in candidates:
        if translator.load(f"qtbase_{candidate}", translations_dir):
            app.installTranslator(translator)
            return translator
    return None


def _resolve_language(arg_lang: str | None, settings: QSettings) -> str | None:
    if arg_lang:
        return arg_lang
    saved_lang = load_ui_language(settings)
    return saved_lang or None


def main() -> int:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument(
        "--lang",
        help="UI language code, for example: ru_RU or en",
    )
    args, qt_args = parser.parse_known_args()

    settings = _create_portable_settings()
    ensure_default_settings(settings)
    apply_components_settings(load_components_settings(settings))
    ensure_windows_ca_bundle()
    _auto_build_translations()
    language = _resolve_language(args.lang, settings)

    app = QApplication([sys.argv[0], *qt_args])
    _qt_translator = _install_qt_translator(app, language)
    _translator = _install_app_translator(app, language)
    if language and _translator is None:
        print(
            f"Warning: translation for '{language}' was not found. "
            "Check .ts files in app/i18n",
            file=sys.stderr,
        )
    window = MainWindow(settings)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
