from __future__ import annotations

from PySide6.QtCore import QEvent, QSize
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QStyle,
)

from app.ui.icon_utils import tinted_theme_icon


LANGUAGE_OPTIONS = [
    ("", "system"),
    ("en_US", "English (US)"),
    ("ru_RU", "Russian"),
]

THEME_OPTIONS = [
    ("system", "system"),
    ("light", "Light"),
    ("dark", "Dark"),
]


class SettingsDialog(QDialog):
    def __init__(
        self,
        current_language: str,
        current_theme: str,
        minimize_to_tray_on_close: bool,
        use_embedded_binaries: bool,
        use_embedded_libraries: bool,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Settings"))

        self.language_combo = QComboBox()
        current_index = 0
        for index, (code, label) in enumerate(LANGUAGE_OPTIONS):
            if label == "system":
                display = self.tr("System default", "Language option")
            else:
                display = self.tr(label)
            self.language_combo.addItem(display, code)
            if code == current_language:
                current_index = index
        self.language_combo.setCurrentIndex(current_index)

        self.theme_combo = QComboBox()
        theme_index = 0
        for index, (code, label) in enumerate(THEME_OPTIONS):
            if label == "system":
                display = self.tr("System default", "Theme option")
            else:
                display = self.tr(label)
            self.theme_combo.addItem(display, code)
            if code == current_theme:
                theme_index = index
        self.theme_combo.setCurrentIndex(theme_index)

        self.minimize_to_tray_checkbox = QCheckBox(self.tr("Minimize to tray on close"))
        self.minimize_to_tray_checkbox.setChecked(minimize_to_tray_on_close)

        self.ffmpeg_source_combo = QComboBox()
        self.ffmpeg_source_combo.addItem(self.tr("Use bundled FFmpeg"), "bundled")
        self.ffmpeg_source_combo.addItem(self.tr("Use system FFmpeg"), "system")
        self.ffmpeg_source_combo.setCurrentIndex(0 if use_embedded_binaries else 1)

        self.libraries_source_combo = QComboBox()
        self.libraries_source_combo.addItem(self.tr("Use bundled libraries"), "bundled")
        self.libraries_source_combo.addItem(self.tr("Use system libraries"), "system")
        self.libraries_source_combo.setCurrentIndex(0 if use_embedded_libraries else 1)

        tabs = QTabWidget()
        tabs.addTab(self._build_general_tab(), self.tr("General"))
        tabs.addTab(self._build_components_tab(), self.tr("Components"))

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self._save_btn = buttons.button(QDialogButtonBox.Save)
        self._cancel_btn = buttons.button(QDialogButtonBox.Cancel)
        if self._save_btn is not None:
            self._save_btn.setText(self.tr("Save"))
        if self._cancel_btn is not None:
            self._cancel_btn.setText(self.tr("Cancel"))
        self._normalize_button_widths([self._save_btn, self._cancel_btn])
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(buttons)
        self.setMinimumWidth(420)
        self.setFixedHeight(self.sizeHint().height())
        self._update_button_icons()

    def selected_language(self) -> str:
        return str(self.language_combo.currentData())

    def selected_theme(self) -> str:
        return str(self.theme_combo.currentData())

    def selected_minimize_to_tray_on_close(self) -> bool:
        return self.minimize_to_tray_checkbox.isChecked()

    def selected_use_embedded_binaries(self) -> bool:
        return str(self.ffmpeg_source_combo.currentData()) == "bundled"

    def selected_use_embedded_libraries(self) -> bool:
        return str(self.libraries_source_combo.currentData()) == "bundled"

    def _build_general_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)
        form.addRow(self.tr("Language:"), self.language_combo)
        form.addRow(self.tr("Theme:"), self.theme_combo)
        form.addRow(self.minimize_to_tray_checkbox)
        return widget

    def _build_components_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)
        form.addRow(self.tr("FFmpeg:"), self.ffmpeg_source_combo)
        form.addRow(self.tr("Libraries:"), self.libraries_source_combo)
        return widget

    @staticmethod
    def _normalize_button_widths(buttons: list[QPushButton | None]) -> None:
        items = [button for button in buttons if button is not None]
        if not items:
            return
        width = max(button.sizeHint().width() for button in items)
        for button in items:
            button.setFixedWidth(width)

    def _update_button_icons(self) -> None:
        icon_size = QSize(16, 16)
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

    def changeEvent(self, event) -> None:
        if event.type() in {
            QEvent.Type.PaletteChange,
            QEvent.Type.ApplicationPaletteChange,
            QEvent.Type.StyleChange,
        }:
            self._update_button_icons()
        super().changeEvent(event)
