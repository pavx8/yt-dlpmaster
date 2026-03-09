from __future__ import annotations

from typing import Any

from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStyle,
    QVBoxLayout,
)
from yt_dlp import YoutubeDL

from app.core.ca import ensure_windows_ca_bundle
from app.core.settings import CookiesSettings, autodetect_browser_profiles
from app.ui.icon_utils import tinted_theme_icon


BROWSER_OPTIONS = ["firefox", "chrome", "chromium", "edge", "opera", "brave", "safari"]


class CookiesDialog(QDialog):
    def __init__(
        self,
        current: CookiesSettings,
        parent=None,
        initial_test_url: str = "",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Cookies"))

        self.mode_combo = QComboBox()
        self.mode_combo.addItem(self.tr("Disabled"), "none")
        self.mode_combo.addItem(self.tr("From browser"), "browser")
        self.mode_combo.addItem(self.tr("From file"), "file")

        self.browser_combo = QComboBox()
        for browser in BROWSER_OPTIONS:
            self.browser_combo.addItem(browser)

        self.profile_combo = QComboBox()
        self.profile_combo.setEditable(True)
        self.detect_btn = QPushButton(self.tr("Refresh"))
        self.detect_btn.clicked.connect(self._detect_profiles)

        profile_row = QHBoxLayout()
        profile_row.addWidget(self.profile_combo)
        profile_row.addWidget(self.detect_btn)

        self.file_input = QLineEdit(current.file_path)
        self.file_btn = QPushButton(self.tr("Browse"))
        self.file_btn.clicked.connect(self._pick_file)

        file_row = QHBoxLayout()
        file_row.addWidget(self.file_input)
        file_row.addWidget(self.file_btn)

        form = QFormLayout()
        form.addRow(self.tr("Mode:"), self.mode_combo)
        form.addRow(self.tr("Browser:"), self.browser_combo)
        form.addRow(self.tr("Browser profile:"), profile_row)
        form.addRow(self.tr("Cookies file:"), file_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self._save_btn = buttons.button(QDialogButtonBox.Save)
        self._cancel_btn = buttons.button(QDialogButtonBox.Cancel)
        if self._save_btn is not None:
            self._save_btn.setText(self.tr("Save"))
        if self._cancel_btn is not None:
            self._cancel_btn.setText(self.tr("Cancel"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.test_btn = QPushButton(self.tr("Test cookies"))
        self.test_btn.clicked.connect(self._test_cookies)
        self.test_url_input = QLineEdit(initial_test_url.strip())
        self.test_url_input.setPlaceholderText(self.tr("https://www.youtube.com/watch?v=..."))

        test_row = QHBoxLayout()
        test_row.setContentsMargins(0, 0, 0, 0)
        test_row.addWidget(self.test_url_input, 1)
        test_row.addWidget(self.test_btn, 0)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(test_row)
        layout.addWidget(buttons)
        self._normalize_button_widths([self.detect_btn, self.file_btn, self.test_btn, self._save_btn, self._cancel_btn])

        self.mode_combo.currentIndexChanged.connect(self._update_enabled_state)
        self.browser_combo.currentIndexChanged.connect(self._detect_profiles)

        mode_index = self.mode_combo.findData(current.mode)
        self.mode_combo.setCurrentIndex(mode_index if mode_index >= 0 else 0)
        browser_index = self.browser_combo.findText(current.browser)
        self.browser_combo.setCurrentIndex(browser_index if browser_index >= 0 else 0)
        self._detect_profiles()
        self.profile_combo.setEditText(current.browser_profile)
        self._update_enabled_state()
        self._update_button_icons()

    @staticmethod
    def _normalize_button_widths(buttons: list[QPushButton | None]) -> None:
        items = [button for button in buttons if button is not None]
        if not items:
            return
        width = max(button.sizeHint().width() for button in items)
        for button in items:
            button.setFixedWidth(width)

    def value(self) -> CookiesSettings:
        return CookiesSettings(
            mode=str(self.mode_combo.currentData()),
            browser=self.browser_combo.currentText(),
            browser_profile=self.profile_combo.currentText().strip(),
            file_path=self.file_input.text().strip(),
        )

    def _pick_file(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Select cookies file"),
            self.file_input.text(),
            self.tr("Text files (*.txt);;All files (*)"),
        )
        if selected:
            self.file_input.setText(selected)

    def _update_enabled_state(self) -> None:
        mode = str(self.mode_combo.currentData())
        browser_mode = mode == "browser"
        file_mode = mode == "file"
        self.browser_combo.setEnabled(browser_mode)
        self.profile_combo.setEnabled(browser_mode)
        self.detect_btn.setEnabled(browser_mode)
        self.file_input.setEnabled(file_mode)
        self.file_btn.setEnabled(file_mode)
        self.test_btn.setEnabled(mode in {"browser", "file"})

    def _detect_profiles(self) -> None:
        browser = self.browser_combo.currentText()
        current = self.profile_combo.currentText().strip()
        detected = autodetect_browser_profiles(browser)
        self.profile_combo.clear()
        self.profile_combo.addItems(detected)
        if current:
            self.profile_combo.setEditText(current)
        elif detected:
            self.profile_combo.setCurrentIndex(0)

    def _test_cookies(self) -> None:
        cookies = self.value()
        error = cookies.validate()
        if error:
            QMessageBox.warning(self, self.tr("Invalid cookies"), error)
            return
        test_url = self.test_url_input.text().strip()
        if not test_url:
            QMessageBox.warning(self, self.tr("Cookies"), self.tr("Test URL is empty."))
            return
        result = _test_cookies_source(cookies, test_url)
        if result is None:
            QMessageBox.information(self, self.tr("Cookies"), self.tr("Cookies source is available."))
            return
        QMessageBox.critical(self, self.tr("Cookies test failed"), result)

    def _update_button_icons(self) -> None:
        icon_size = QSize(16, 16)
        self.detect_btn.setIcon(
            tinted_theme_icon(
                self,
                "view-refresh-symbolic",
                QStyle.StandardPixmap.SP_BrowserReload,
                icon_size,
            )
        )
        self.file_btn.setIcon(
            tinted_theme_icon(
                self,
                "document-open-symbolic",
                QStyle.StandardPixmap.SP_DialogOpenButton,
                icon_size,
            )
        )
        self.test_btn.setIcon(
            tinted_theme_icon(
                self,
                "dialog-ok-apply-symbolic",
                QStyle.StandardPixmap.SP_DialogApplyButton,
                icon_size,
            )
        )
        if self._save_btn is not None:
            self._save_btn.setIcon(
                tinted_theme_icon(
                    self,
                    "document-save-symbolic",
                    QStyle.StandardPixmap.SP_DialogSaveButton,
                    icon_size,
                )
            )
            self._save_btn.setIconSize(icon_size)
        if self._cancel_btn is not None:
            self._cancel_btn.setIcon(
                tinted_theme_icon(
                    self,
                    "dialog-cancel-symbolic",
                    QStyle.StandardPixmap.SP_DialogCancelButton,
                    icon_size,
                )
            )
            self._cancel_btn.setIconSize(icon_size)
        self.detect_btn.setIconSize(icon_size)
        self.file_btn.setIconSize(icon_size)
        self.test_btn.setIconSize(icon_size)
        self._normalize_button_widths([self.detect_btn, self.file_btn, self.test_btn, self._save_btn, self._cancel_btn])

    def changeEvent(self, event) -> None:
        if event.type() in {
            QEvent.Type.PaletteChange,
            QEvent.Type.ApplicationPaletteChange,
            QEvent.Type.StyleChange,
        }:
            self._update_button_icons()
        super().changeEvent(event)


def _test_cookies_source(cookies: CookiesSettings, url: str) -> str | None:
    ensure_windows_ca_bundle()
    opts: dict[str, Any] = {
        "quiet": True,
        "skip_download": True,
    }
    cookiefile = cookies.cookiefile_option()
    browser = cookies.cookiesfrombrowser_option()
    if cookiefile:
        opts["cookiefile"] = cookiefile
    if browser:
        opts["cookiesfrombrowser"] = browser
    try:
        with YoutubeDL(opts) as ydl:
            ydl.extract_info(url, download=False)
    except Exception as exc:  # noqa: BLE001
        return str(exc).strip() or f"{type(exc).__name__} (no details)"
    return None
