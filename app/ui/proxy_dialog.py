from __future__ import annotations

from PySide6.QtCore import QEvent, QSize
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QPushButton,
    QStyle,
)

from app.core.settings import PROXY_SCHEMES, ProxySettings
from app.ui.icon_utils import tinted_theme_icon


class ProxyDialog(QDialog):
    def __init__(self, proxy: ProxySettings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Proxy"))

        self.enabled_checkbox = QCheckBox(self.tr("Use proxy"))
        self.enabled_checkbox.setChecked(proxy.enabled)

        self.scheme_combo = QComboBox()
        for scheme in PROXY_SCHEMES:
            self.scheme_combo.addItem(scheme)
        self.scheme_combo.setCurrentText(proxy.scheme)

        self.host_input = QLineEdit(proxy.host)
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(proxy.port)

        self.username_input = QLineEdit(proxy.username)
        self.password_input = QLineEdit(proxy.password)
        self.password_input.setEchoMode(QLineEdit.Password)

        form = QFormLayout()
        form.addRow(self.enabled_checkbox)
        form.addRow(self.tr("Type:"), self.scheme_combo)
        form.addRow(self.tr("Host:"), self.host_input)
        form.addRow(self.tr("Port:"), self.port_input)
        form.addRow(self.tr("Username:"), self.username_input)
        form.addRow(self.tr("Password:"), self.password_input)

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
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.setMinimumWidth(460)
        self.setFixedHeight(self.sizeHint().height())
        self._update_button_icons()

        self.enabled_checkbox.toggled.connect(self._update_enabled_state)
        self._update_enabled_state(self.enabled_checkbox.isChecked())

    @staticmethod
    def _normalize_button_widths(buttons: list[QPushButton | None]) -> None:
        items = [button for button in buttons if button is not None]
        if not items:
            return
        width = max(button.sizeHint().width() for button in items)
        for button in items:
            button.setFixedWidth(width)

    def value(self) -> ProxySettings:
        return ProxySettings(
            enabled=self.enabled_checkbox.isChecked(),
            scheme=self.scheme_combo.currentText(),
            host=self.host_input.text().strip(),
            port=int(self.port_input.value()),
            username=self.username_input.text(),
            password=self.password_input.text(),
        )

    def _update_enabled_state(self, enabled: bool) -> None:
        self.scheme_combo.setEnabled(enabled)
        self.host_input.setEnabled(enabled)
        self.port_input.setEnabled(enabled)
        self.username_input.setEnabled(enabled)
        self.password_input.setEnabled(enabled)

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
