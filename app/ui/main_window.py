from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import QEvent, QRectF, QSettings, QSize, Qt, QThread, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QPainter, QPainterPath, QPen, QPixmap, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QComboBox,
    QProgressBar,
    QToolButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QMenu,
    QSystemTrayIcon,
    QStyle,
)

from app.core.downloader import DownloadRequest, DownloadWorker
from app.core.analyzer import AnalyzeRequest, AnalyzeWorker
from app.core.ca import ensure_windows_ca_bundle
from app.core.settings import (
    ComponentsSettings,
    apply_components_settings,
    CookiesSettings,
    ProxySettings,
    load_cookies_settings,
    load_components_settings,
    load_minimize_to_tray_on_close,
    load_sponsorblock_enabled,
    load_transcode_compatible,
    load_proxy_settings,
    load_ui_language,
    load_ui_theme,
    save_cookies_settings,
    save_components_settings,
    save_minimize_to_tray_on_close,
    save_proxy_settings,
    save_sponsorblock_enabled,
    save_transcode_compatible,
    save_ui_language,
    save_ui_theme,
)
from app.ui.about_dialog import AboutDialog
from app.ui.cookies_dialog import CookiesDialog
from app.ui.icon_utils import tinted_theme_icon
from app.ui.proxy_dialog import ProxyDialog
from app.ui.settings_dialog import SettingsDialog
from app.ui.updater_dialog import UpdaterDialog


DEFAULT_PRESETS = [
    {
        "label": "Best available + audio aac + container mp4",
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "extract_audio_codec": None,
        "video_audio_codec": "aac",
        "video_output_container": "mp4",
    },
    {
        "label": "Best available + audio mp3 + container mp4",
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "extract_audio_codec": None,
        "video_audio_codec": "mp3",
        "video_output_container": "mp4",
    },
    {
        "label": "Best available + audio opus + container mp4",
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "extract_audio_codec": None,
        "video_audio_codec": "opus",
        "video_output_container": "mp4",
    },
    {
        "label": "Small size + audio aac + container mp4",
        "format": "worstvideo+worstaudio/worst",
        "merge_output_format": "mp4",
        "extract_audio_codec": None,
        "video_audio_codec": "aac",
        "video_output_container": "mp4",
    },
    {
        "label": "Small size + audio mp3 + container mp4",
        "format": "worstvideo+worstaudio/worst",
        "merge_output_format": "mp4",
        "extract_audio_codec": None,
        "video_audio_codec": "mp3",
        "video_output_container": "mp4",
    },
    {
        "label": "Small size + audio opus + container mp4",
        "format": "worstvideo+worstaudio/worst",
        "merge_output_format": "mp4",
        "extract_audio_codec": None,
        "video_audio_codec": "opus",
        "video_output_container": "mp4",
    },
    {
        "label": "Audio only (mp3)",
        "format": "bestaudio/best",
        "merge_output_format": None,
        "extract_audio_codec": "mp3",
        "video_audio_codec": None,
        "video_output_container": None,
    },
    {
        "label": "Audio only (opus)",
        "format": "bestaudio[acodec*=opus]/bestaudio/best",
        "merge_output_format": None,
        "extract_audio_codec": "opus",
        "video_audio_codec": None,
        "video_output_container": None,
    },
]
WINDOW_DEFAULT_WIDTH = 760
WINDOW_MIN_WIDTH = 760
LOG_PANEL_HEIGHT = 180
PREVIEW_WIDTH = 220
PREVIEW_HEIGHT = 124
PREVIEW_TOP_OFFSET = 0
PREVIEW_CORNER_RADIUS = 10
PREVIEW_BORDER_WIDTH = 1


class RoundedPreviewLabel(QLabel):
    def __init__(self, radius: int, border_width: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._radius = radius
        self._border_width = border_width
        self._preview_pixmap = QPixmap()

    def setPreviewPixmap(self, pixmap: QPixmap) -> None:
        self._preview_pixmap = self._prepare_cover_pixmap(pixmap, self.width(), self.height())
        self.update()

    def clearPreviewPixmap(self) -> None:
        self._preview_pixmap = QPixmap()
        self.update()

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

            rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
            clip_path = QPainterPath()
            clip_path.addRoundedRect(rect, self._radius, self._radius)

            painter.fillPath(clip_path, self.palette().brush(QPalette.ColorRole.Base))
            painter.save()
            painter.setClipPath(clip_path)
            if not self._preview_pixmap.isNull():
                painter.drawPixmap(0, 0, self._preview_pixmap)
            painter.restore()

            border_pen = QPen(self.palette().color(QPalette.ColorRole.Mid))
            border_pen.setWidth(self._border_width)
            painter.setPen(border_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(clip_path)

            if self._preview_pixmap.isNull() and self.text():
                text_rect = self.rect().adjusted(8, 6, -8, -6)
                painter.setPen(self.palette().color(QPalette.ColorRole.Text))
                painter.drawText(text_rect, self.alignment() | Qt.TextFlag.TextWordWrap, self.text())
        finally:
            painter.end()

    @staticmethod
    def _cover_source_rect(pixmap: QPixmap, target_width: int, target_height: int) -> QRectF:
        if pixmap.isNull() or target_width <= 0 or target_height <= 0:
            return QRectF(0, 0, max(pixmap.width(), 1), max(pixmap.height(), 1))

        source_width = pixmap.width()
        source_height = pixmap.height()
        source_ratio = source_width / source_height
        target_ratio = target_width / target_height

        if source_ratio > target_ratio:
            new_width = source_height * target_ratio
            offset_x = (source_width - new_width) / 2
            return QRectF(offset_x, 0, new_width, source_height)

        new_height = source_width / target_ratio
        offset_y = (source_height - new_height) / 2
        return QRectF(0, offset_y, source_width, new_height)

    @staticmethod
    def _prepare_cover_pixmap(pixmap: QPixmap, target_width: int, target_height: int) -> QPixmap:
        if pixmap.isNull() or target_width <= 0 or target_height <= 0:
            return QPixmap()
        scaled = pixmap.scaled(
            target_width,
            target_height,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x_offset = max((scaled.width() - target_width) // 2, 0)
        y_offset = max((scaled.height() - target_height) // 2, 0)
        return scaled.copy(x_offset, y_offset, target_width, target_height)


class MainWindow(QMainWindow):
    def __init__(self, settings: QSettings) -> None:
        super().__init__()
        self._settings = settings
        self._proxy_settings: ProxySettings = load_proxy_settings(self._settings)
        self._cookies_settings: CookiesSettings = load_cookies_settings(self._settings)
        self._transcode_compatible = load_transcode_compatible(self._settings)
        self._sponsorblock_enabled = load_sponsorblock_enabled(self._settings)
        self._ui_theme = load_ui_theme(self._settings)
        self._minimize_to_tray_on_close = load_minimize_to_tray_on_close(self._settings)
        self._quit_requested = False
        self._tray_notice_shown = False
        self.setWindowTitle("yt-dlpMaster")
        self.setMinimumWidth(WINDOW_MIN_WIDTH)
        self.resize(WINDOW_DEFAULT_WIDTH, 200)
        self._apply_theme(self._ui_theme)
        self._create_menu()

        self._thread: QThread | None = None
        self._worker: DownloadWorker | None = None
        self._analysis_thread: QThread | None = None
        self._analysis_worker: AnalyzeWorker | None = None
        self._active_download = False
        self._current_status = self.tr("Ready")
        self._current_media_name = "-"
        self._current_progress = 0

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText(self.tr("https://www.youtube.com/watch?v=..."))
        self.analyze_btn = QPushButton(self.tr("Analysis"))
        self.analyze_btn.clicked.connect(self._analyze_url)

        self.path_input = QLineEdit(str(Path.home() / "Downloads"))
        self.path_browse_btn = QPushButton(self.tr("Browse"))
        self.path_browse_btn.clicked.connect(self._pick_folder)
        self._normalize_action_button_widths()

        self.format_combo = QComboBox()
        self._set_available_presets(DEFAULT_PRESETS, keep_current=False)

        self.download_btn = QPushButton(self.tr("Download"))
        self.download_btn.clicked.connect(self._start_download)
        self.transcode_checkbox = QCheckBox(self.tr("Transcode downloaded files to compatible format"))
        self.transcode_checkbox.setChecked(self._transcode_compatible)
        self.transcode_checkbox.toggled.connect(self._on_transcode_toggled)
        self.sponsorblock_checkbox = QCheckBox(self.tr("SponsorBlock"))
        self.sponsorblock_checkbox.setChecked(self._sponsorblock_enabled)
        self.sponsorblock_checkbox.toggled.connect(self._on_sponsorblock_toggled)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        self.status_label = QLabel(self.tr("Ready"))
        self.status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.log_toggle_btn = QToolButton()
        self.log_toggle_btn.setCheckable(True)
        self.log_toggle_btn.setChecked(False)
        self.log_toggle_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.log_toggle_btn.toggled.connect(self._toggle_log_panel)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        log_size_policy = self.log_output.sizePolicy()
        log_size_policy.setRetainSizeWhenHidden(False)
        self.log_output.setSizePolicy(log_size_policy)
        self._set_log_constraints(False)
        self._update_log_toggle_ui(False)
        self._lock_log_toggle_width()
        self._update_action_and_button_icons()

        self.preview_image = RoundedPreviewLabel(PREVIEW_CORNER_RADIUS, PREVIEW_BORDER_WIDTH)
        self.preview_image.setText(self.tr("Preview will be available after analysis"))
        self.preview_image.setAlignment(Qt.AlignCenter)
        self.preview_image.setFixedSize(PREVIEW_WIDTH, PREVIEW_HEIGHT)
        self.preview_image.setWordWrap(True)
        self.preview_title_label = QLabel(self.tr("Title: -"))
        self.preview_title_label.setWordWrap(True)
        self.preview_title_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.preview_title_label.setFixedWidth(PREVIEW_WIDTH)
        self.preview_duration_label = QLabel(self.tr("Duration: -"))
        self.preview_duration_label.setWordWrap(True)
        self.preview_duration_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.preview_duration_label.setFixedWidth(PREVIEW_WIDTH)
        self.preview_duration_sb_label = QLabel(self.tr("Duration with SponsorBlock: -"))
        self.preview_duration_sb_label.setWordWrap(True)
        self.preview_duration_sb_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.preview_duration_sb_label.setFixedWidth(PREVIEW_WIDTH)

        central = QWidget()
        self.setCentralWidget(central)

        outer_layout = QVBoxLayout(central)
        outer_layout.setAlignment(Qt.AlignTop)

        page_layout = QHBoxLayout()
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(10)
        controls_group = QGroupBox()
        right_widget = QWidget()
        right_widget.setFixedWidth(PREVIEW_WIDTH + 8)
        page_layout.addWidget(controls_group, 1)
        page_layout.addWidget(right_widget, 0)
        outer_layout.addLayout(page_layout)

        root_layout = QVBoxLayout(controls_group)
        root_layout.setAlignment(Qt.AlignTop)

        form_layout = QFormLayout()
        url_layout = QHBoxLayout()
        url_layout.addWidget(self.url_input)
        url_layout.addWidget(self.analyze_btn)
        form_layout.addRow(self.tr("URL:"), url_layout)

        path_layout = QHBoxLayout()
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(self.path_browse_btn)
        form_layout.addRow(self.tr("Save to:"), path_layout)

        form_layout.addRow(self.tr("Preset:"), self.format_combo)
        root_layout.addLayout(form_layout)

        options_row = QHBoxLayout()
        options_row.setContentsMargins(0, 0, 0, 0)
        options_row.setSpacing(10)
        options_row.addWidget(self.transcode_checkbox, 0, Qt.AlignLeft)
        options_row.addWidget(self.sponsorblock_checkbox, 0, Qt.AlignLeft)
        options_row.addStretch(1)
        root_layout.addLayout(options_row)
        root_layout.addWidget(self.download_btn)
        root_layout.addWidget(self.progress_bar)

        preview_layout = QVBoxLayout(right_widget)
        preview_layout.setContentsMargins(0, PREVIEW_TOP_OFFSET, 0, 0)
        preview_layout.setAlignment(Qt.AlignTop)
        preview_layout.addWidget(self.preview_image, 0, Qt.AlignCenter)
        preview_layout.addWidget(self.preview_title_label, 0, Qt.AlignLeft)
        preview_layout.addWidget(self.preview_duration_label, 0, Qt.AlignLeft)
        preview_layout.addWidget(self.preview_duration_sb_label, 0, Qt.AlignLeft)

        status_row = QHBoxLayout()
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.addWidget(self.log_toggle_btn, 0, Qt.AlignLeft)
        status_row.addStretch(1)
        status_row.addWidget(self.status_label, 0, Qt.AlignRight)
        outer_layout.addLayout(status_row)
        outer_layout.addWidget(self.log_output)
        self._fit_window_height_to_content()
        self._setup_tray()

    def _create_menu(self) -> None:
        settings_action = QAction(self.tr("Settings"), self)
        settings_action.triggered.connect(self._show_settings)

        cookies_action = QAction(self.tr("Cookies"), self)
        cookies_action.triggered.connect(self._show_cookies)

        proxy_action = QAction(self.tr("Proxy"), self)
        proxy_action.triggered.connect(self._show_proxy)

        updater_action = QAction("Обновлятор", self)
        updater_action.triggered.connect(self._show_updater)

        about_action = QAction(self.tr("About"), self)
        about_action.triggered.connect(self._show_about)

        self.menuBar().addAction(settings_action)
        self.menuBar().addAction(cookies_action)
        self.menuBar().addAction(proxy_action)
        self.menuBar().addAction(updater_action)
        self.menuBar().addAction(about_action)

    def _pick_folder(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            self.tr("Select output folder"),
            self.path_input.text(),
        )
        if selected:
            self.path_input.setText(selected)

    def _start_download(self) -> None:
        url = self.url_input.text().strip()
        output_dir = Path(self.path_input.text().strip())

        if not url:
            QMessageBox.warning(self, self.tr("Missing URL"), self.tr("Please enter a video URL."))
            return

        if not output_dir.exists() or not output_dir.is_dir():
            QMessageBox.warning(self, self.tr("Invalid folder"), self.tr("Please choose a valid output folder."))
            return

        if self._thread is not None:
            QMessageBox.information(self, self.tr("Busy"), self.tr("A download is already in progress."))
            return

        if self._analysis_thread is not None:
            QMessageBox.information(self, self.tr("Busy"), self.tr("Analysis is already in progress."))
            return

        preset = self._selected_preset()
        if preset is None:
            QMessageBox.warning(self, self.tr("Preset unavailable"), self.tr("Please analyze URL or choose a preset."))
            return

        self.progress_bar.setValue(0)
        self.log_output.clear()
        self._append_log(self.tr("URL: {url}").format(url=url))
        self._append_log(self.tr("Output: {path}").format(path=output_dir))
        self._append_log(self.tr("Proxy: {proxy}").format(proxy=self._proxy_settings.masked_proxy_label()))
        self._append_log(self.tr("Cookies: {cookies}").format(cookies=self._cookies_settings.summary()))
        self._append_log(
            self.tr("Transcode compatible format: {state}").format(
                state=self.tr("enabled") if self._transcode_compatible else self.tr("disabled")
            )
        )
        self._append_log(
            self.tr("SponsorBlock: {state}").format(
                state=self.tr("enabled") if self._sponsorblock_enabled else self.tr("disabled")
            )
        )

        proxy_url = self._proxy_settings.build_proxy_url()
        if self._proxy_settings.enabled and proxy_url is None:
            QMessageBox.warning(self, self.tr("Invalid proxy"), self.tr("Please check proxy settings."))
            return
        cookies_error = self._cookies_settings.validate()
        if cookies_error:
            QMessageBox.warning(self, self.tr("Invalid cookies"), self._localize_cookies_error(cookies_error))
            return

        request = DownloadRequest(
            url=url,
            output_dir=output_dir,
            format_selector=str(preset.get("format", "bestvideo+bestaudio/best")),
            merge_output_format=self._as_optional_str(preset.get("merge_output_format")),
            extract_audio_codec=self._as_optional_str(preset.get("extract_audio_codec")),
            video_audio_codec=self._as_optional_str(preset.get("video_audio_codec")),
            video_output_container=self._as_optional_str(preset.get("video_output_container")),
            proxy_url=proxy_url,
            cookiefile=self._cookies_settings.cookiefile_option(),
            cookies_from_browser=self._cookies_settings.cookiesfrombrowser_option(),
            transcode_compatible=self._transcode_compatible,
            sponsorblock_enabled=self._sponsorblock_enabled,
        )
        worker = DownloadWorker(request)

        thread = QThread(self)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.progress_changed.connect(self._on_progress)
        worker.status_changed.connect(self._on_status)
        worker.media_name_changed.connect(self._on_media_name_changed)
        worker.log_message.connect(self._append_log)
        worker.download_finished.connect(self._on_finished)
        worker.download_failed.connect(self._on_failed)

        worker.download_finished.connect(thread.quit)
        worker.download_failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_thread)

        self._thread = thread
        self._worker = worker
        self.download_btn.setEnabled(False)
        self.analyze_btn.setEnabled(False)
        self._active_download = True
        self._current_progress = 0
        self._current_media_name = "-"
        self._on_status(self.tr("Preparing download..."))
        thread.start()

    def _on_progress(self, value: int) -> None:
        self.progress_bar.setValue(value)
        self._current_progress = value
        self._update_tray_tooltip()

    def _on_status(self, message: str) -> None:
        self.status_label.setText(message)
        self._current_status = message
        self._append_log(message)
        self._update_tray_tooltip()

    def _on_media_name_changed(self, name: str) -> None:
        if not name:
            return
        self._current_media_name = name
        self._update_tray_tooltip()

    def _on_finished(self, message: str) -> None:
        self.status_label.setText(message)
        self._current_status = message
        self._append_log(message)
        self.download_btn.setEnabled(True)
        self.analyze_btn.setEnabled(True)
        self._active_download = False
        self._current_progress = 100
        self._update_tray_tooltip()

    def _on_failed(self, error: str) -> None:
        self._on_status(self.tr("Error: {error}").format(error=error))
        self._set_log_expanded(True)
        self.download_btn.setEnabled(True)
        self.analyze_btn.setEnabled(True)
        self._active_download = False
        self._update_tray_tooltip()
        QMessageBox.critical(self, self.tr("Download failed"), error)

    def _clear_thread(self) -> None:
        self._thread = None
        self._worker = None

    def _append_log(self, text: str) -> None:
        self.log_output.append(text)

    def _toggle_log_panel(self, expanded: bool) -> None:
        self._set_log_constraints(expanded)
        self._update_log_toggle_ui(expanded)
        self._fit_window_height_to_content()

    def _set_log_expanded(self, expanded: bool) -> None:
        if self.log_toggle_btn.isChecked() != expanded:
            self.log_toggle_btn.setChecked(expanded)
            return
        self._toggle_log_panel(expanded)

    def _update_log_toggle_ui(self, expanded: bool) -> None:
        self.log_toggle_btn.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self.log_toggle_btn.setText(self.tr("Hide log") if expanded else self.tr("Show log"))

    def _lock_log_toggle_width(self) -> None:
        current = self.log_toggle_btn.isChecked()
        widths: list[int] = []
        for expanded in (False, True):
            self._update_log_toggle_ui(expanded)
            widths.append(self.log_toggle_btn.sizeHint().width())
        self.log_toggle_btn.setFixedWidth(max(widths))
        self._update_log_toggle_ui(current)

    def _fit_window_height_to_content(self) -> None:
        central = self.centralWidget()
        if central is None:
            return

        layout = central.layout()
        if layout is not None:
            layout.activate()

        target_height = self.sizeHint().height()
        self.setMinimumHeight(target_height)
        self.setMaximumHeight(target_height)
        self.resize(max(self.width(), WINDOW_MIN_WIDTH), target_height)

    def _set_log_constraints(self, expanded: bool) -> None:
        if expanded:
            self.log_output.setMinimumHeight(LOG_PANEL_HEIGHT)
            self.log_output.setMaximumHeight(16777215)
            self.log_output.setVisible(True)
            return

        self.log_output.setMinimumHeight(0)
        self.log_output.setMaximumHeight(0)
        self.log_output.setVisible(False)

    def _show_settings(self) -> None:
        current_language = load_ui_language(self._settings)
        current_theme = load_ui_theme(self._settings)
        current_components = load_components_settings(self._settings)
        dialog = SettingsDialog(
            current_language,
            current_theme,
            self._minimize_to_tray_on_close,
            current_components.use_embedded_binaries,
            current_components.use_embedded_libraries,
            self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        selected_language = dialog.selected_language()
        selected_theme = dialog.selected_theme()
        selected_minimize_to_tray = dialog.selected_minimize_to_tray_on_close()

        if selected_language != current_language:
            save_ui_language(self._settings, selected_language)
            QMessageBox.information(
                self,
                self.tr("Settings"),
                self.tr("Language will be applied after restart."),
            )

        if selected_minimize_to_tray != self._minimize_to_tray_on_close:
            self._minimize_to_tray_on_close = selected_minimize_to_tray
            save_minimize_to_tray_on_close(self._settings, selected_minimize_to_tray)

        if selected_theme != current_theme:
            self._ui_theme = selected_theme
            save_ui_theme(self._settings, selected_theme)
            self._apply_theme(selected_theme)

        selected_components = ComponentsSettings(
            use_embedded_binaries=dialog.selected_use_embedded_binaries(),
            use_embedded_libraries=dialog.selected_use_embedded_libraries(),
        )
        if selected_components != current_components:
            save_components_settings(self._settings, selected_components)
            apply_components_settings(selected_components)
            ensure_windows_ca_bundle()

    def _show_proxy(self) -> None:
        dialog = ProxyDialog(self._proxy_settings, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        self._proxy_settings = dialog.value()
        save_proxy_settings(self._settings, self._proxy_settings)

    def _show_cookies(self) -> None:
        dialog = CookiesDialog(
            self._cookies_settings,
            self,
            initial_test_url=self.url_input.text(),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        cookies = dialog.value()
        error = cookies.validate()
        if error:
            QMessageBox.warning(self, self.tr("Invalid cookies"), self._localize_cookies_error(error))
            return
        self._cookies_settings = cookies
        save_cookies_settings(self._settings, cookies)

    def _show_about(self) -> None:
        AboutDialog(self).exec()

    def _show_updater(self) -> None:
        UpdaterDialog(self).exec()

    def _on_transcode_toggled(self, enabled: bool) -> None:
        self._transcode_compatible = enabled
        save_transcode_compatible(self._settings, enabled)

    def _on_sponsorblock_toggled(self, enabled: bool) -> None:
        self._sponsorblock_enabled = enabled
        save_sponsorblock_enabled(self._settings, enabled)

    def _analyze_url(self) -> None:
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, self.tr("Missing URL"), self.tr("Please enter a video URL."))
            return
        if self._analysis_thread is not None:
            QMessageBox.information(self, self.tr("Busy"), self.tr("Analysis is already in progress."))
            return
        if self._thread is not None:
            QMessageBox.information(self, self.tr("Busy"), self.tr("A download is already in progress."))
            return

        proxy_url = self._proxy_settings.build_proxy_url()
        if self._proxy_settings.enabled and proxy_url is None:
            QMessageBox.warning(self, self.tr("Invalid proxy"), self.tr("Please check proxy settings."))
            return
        cookies_error = self._cookies_settings.validate()
        if cookies_error:
            QMessageBox.warning(self, self.tr("Invalid cookies"), self._localize_cookies_error(cookies_error))
            return

        request = AnalyzeRequest(
            url=url,
            proxy_url=proxy_url,
            cookiefile=self._cookies_settings.cookiefile_option(),
            cookies_from_browser=self._cookies_settings.cookiesfrombrowser_option(),
        )
        worker = AnalyzeWorker(request)
        thread = QThread(self)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.status_changed.connect(self._on_status)
        worker.preview_ready.connect(self._on_preview_ready)
        worker.analysis_finished.connect(self._on_analysis_finished)
        worker.analysis_failed.connect(self._on_analysis_failed)

        worker.analysis_finished.connect(thread.quit)
        worker.analysis_failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_analysis_thread)

        self._analysis_thread = thread
        self._analysis_worker = worker
        self.analyze_btn.setEnabled(False)
        self.download_btn.setEnabled(False)
        self.preview_title_label.setText(self.tr("Title: -"))
        self.preview_duration_label.setText(self.tr("Duration: -"))
        self.preview_duration_sb_label.setText(self.tr("Duration with SponsorBlock: -"))
        thread.start()

    def _on_analysis_finished(self, presets: list) -> None:
        normalized = [preset for preset in presets if isinstance(preset, dict)]
        self._set_available_presets(normalized, keep_current=True)
        preset_labels = []
        for preset in normalized:
            label = str(preset.get("label", "")).strip()
            if not label:
                continue
            preset_labels.append(self._display_preset_label(label))
        if preset_labels:
            self._append_log(
                self.tr("Detected presets: {presets}").format(presets=", ".join(preset_labels))
            )
        self._on_status(self.tr("Analysis completed. Presets updated."))
        self.analyze_btn.setEnabled(True)
        self.download_btn.setEnabled(True)

    def _on_analysis_failed(self, error: str) -> None:
        self._on_status(self.tr("Analysis error: {error}").format(error=error))
        QMessageBox.critical(self, self.tr("Analysis failed"), error)
        self.analyze_btn.setEnabled(True)
        self.download_btn.setEnabled(True)

    def _on_preview_ready(self, title: str, duration: str, image_data: bytes) -> None:
        self.preview_title_label.setText(
            self.tr("Title: {title}").format(title=title if title else "-")
        )
        self.preview_duration_label.setText(
            self.tr("Duration: {duration}").format(duration=duration if duration else "-")
        )
        self.preview_duration_sb_label.setText(
            self.tr("Duration with SponsorBlock: {duration}").format(duration=duration if duration else "-")
        )
        if title:
            self.preview_image.setToolTip(title)
        else:
            self.preview_image.setToolTip("")
        if not image_data:
            self.preview_image.clearPreviewPixmap()
            self.preview_image.setText(self.tr("Preview is not available"))
            return
        pixmap = QPixmap()
        if not pixmap.loadFromData(image_data):
            return
        self.preview_image.setText("")
        self.preview_image.setPreviewPixmap(pixmap)

    def _clear_analysis_thread(self) -> None:
        self._analysis_thread = None
        self._analysis_worker = None

    def _set_available_presets(self, presets: list[dict], keep_current: bool) -> None:
        current = self._selected_preset() if keep_current else None
        filtered = [preset for preset in presets if isinstance(preset, dict) and str(preset.get("format", "")).strip()]
        if not filtered:
            filtered = list(DEFAULT_PRESETS)

        self.format_combo.clear()
        for preset in filtered:
            label = str(preset.get("label", "")).strip() or self.tr("Custom preset")
            self.format_combo.addItem(self._display_preset_label(label), preset)

        if current:
            current_format = str(current.get("format", ""))
            for index in range(self.format_combo.count()):
                data = self.format_combo.itemData(index)
                if isinstance(data, dict) and str(data.get("format", "")) == current_format:
                    self.format_combo.setCurrentIndex(index)
                    break

    def _selected_preset(self) -> dict | None:
        value = self.format_combo.currentData()
        if not isinstance(value, dict):
            return None
        if not str(value.get("format", "")).strip():
            return None
        return value

    def _normalize_action_button_widths(self) -> None:
        widths = [
            self.path_browse_btn.sizeHint().width(),
            self.analyze_btn.sizeHint().width(),
        ]
        if hasattr(self, "download_btn"):
            widths.append(self.download_btn.sizeHint().width())
        width = max(widths)
        self.path_browse_btn.setFixedWidth(width)
        self.analyze_btn.setFixedWidth(width)
        if hasattr(self, "download_btn"):
            self.download_btn.setFixedWidth(width)

    def _apply_theme(self, theme: str) -> None:
        app = QApplication.instance()
        if app is None:
            return
        style_hints = app.styleHints()
        if theme == "dark":
            style_hints.setColorScheme(Qt.ColorScheme.Dark)
        elif theme == "light":
            style_hints.setColorScheme(Qt.ColorScheme.Light)
        else:
            style_hints.setColorScheme(Qt.ColorScheme.Unknown)

        # Recreate current Qt style to refresh cached icon/arrow painting.
        app.setStyle(app.style().objectName())
        style = app.style()
        for widget in app.allWidgets():
            style.unpolish(widget)
            style.polish(widget)
            widget.update()
        if hasattr(self, "analyze_btn"):
            self._update_action_and_button_icons()
            QTimer.singleShot(0, self._update_action_and_button_icons)
        self._refresh_lineedit_placeholders()
        QTimer.singleShot(0, self._refresh_lineedit_placeholders)

    def _update_action_and_button_icons(self) -> None:
        icon_size = QSize(16, 16)
        self.analyze_btn.setIcon(
            tinted_theme_icon(
                self,
                "view-refresh-symbolic",
                QStyle.StandardPixmap.SP_BrowserReload,
                icon_size,
            )
        )
        self.path_browse_btn.setIcon(
            tinted_theme_icon(
                self,
                "document-open-symbolic",
                QStyle.StandardPixmap.SP_DialogOpenButton,
                icon_size,
            )
        )
        self.download_btn.setIcon(
            tinted_theme_icon(
                self,
                "go-down-symbolic",
                QStyle.StandardPixmap.SP_ArrowDown,
                icon_size,
            )
        )
        self.analyze_btn.setIconSize(icon_size)
        self.path_browse_btn.setIconSize(icon_size)
        self.download_btn.setIconSize(icon_size)

    def changeEvent(self, event) -> None:
        if event.type() in {
            QEvent.Type.PaletteChange,
            QEvent.Type.ApplicationPaletteChange,
            QEvent.Type.StyleChange,
        }:
            if hasattr(self, "analyze_btn"):
                self._update_action_and_button_icons()
        super().changeEvent(event)

    def _refresh_lineedit_placeholders(self) -> None:
        app = QApplication.instance()
        if app is None:
            return
        base_palette = app.palette()
        placeholder_color = base_palette.color(QPalette.Text)
        placeholder_color.setAlpha(128)
        for widget in app.allWidgets():
            if not isinstance(widget, QLineEdit):
                continue
            palette = widget.palette()
            palette.setColor(QPalette.PlaceholderText, placeholder_color)
            widget.setPalette(palette)
            placeholder = widget.placeholderText()
            widget.setPlaceholderText("")
            widget.setPlaceholderText(placeholder)
            widget.update()

    @staticmethod
    def _as_optional_str(value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _localize_cookies_error(self, error: str) -> str:
        translations = {
            "Browser profile is required": self.tr("Browser profile is required"),
            "Browser profile path does not exist": self.tr("Browser profile path does not exist"),
            "Cookies file path is required": self.tr("Cookies file path is required"),
            "Cookies file does not exist": self.tr("Cookies file does not exist"),
        }
        return translations.get(error, error)

    def _display_preset_label(self, label: str) -> str:
        match = re.fullmatch(r"(\d+)p \+ audio \(mp4\)", label)
        if match:
            return self.tr("{height}p + audio (mp4)").format(height=match.group(1))
        match = re.fullmatch(r"(\d+)p \+ audio mp3 \+ container mp4", label)
        if match:
            return self.tr("{height}p + audio mp3 + container mp4").format(height=match.group(1))
        match = re.fullmatch(r"(\d+)p \+ audio opus \+ container mp4", label)
        if match:
            return self.tr("{height}p + audio opus + container mp4").format(height=match.group(1))

        translations = {
            "Best available + audio aac + container mp4": self.tr("Best available + audio aac + container mp4"),
            "Best available + audio mp3 + container mp4": self.tr("Best available + audio mp3 + container mp4"),
            "Best available + audio opus + container mp4": self.tr("Best available + audio opus + container mp4"),
            "Small size + audio aac + container mp4": self.tr("Small size + audio aac + container mp4"),
            "Small size + audio mp3 + container mp4": self.tr("Small size + audio mp3 + container mp4"),
            "Small size + audio opus + container mp4": self.tr("Small size + audio opus + container mp4"),
            "Audio only (mp3)": self.tr("Audio only (mp3)"),
            "Audio only (opus)": self.tr("Audio only (opus)"),
        }
        return translations.get(label, label)

    def _setup_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self._tray_icon = None
            return

        tray_icon = QSystemTrayIcon(self)
        tray_icon.setIcon(self.windowIcon())
        tray_icon.setToolTip("yt-dlpMaster")
        tray_icon.activated.connect(self._on_tray_activated)

        tray_menu = QMenu(self)
        open_action = QAction(self.tr("Open"), self)
        open_action.triggered.connect(self._restore_from_tray)
        quit_action = QAction(self.tr("Quit"), self)
        quit_action.triggered.connect(self._quit_from_tray)
        tray_menu.addAction(open_action)
        tray_menu.addAction(quit_action)

        tray_icon.setContextMenu(tray_menu)
        tray_icon.show()
        self._tray_icon = tray_icon
        self._update_tray_tooltip()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._restore_from_tray()

    def _restore_from_tray(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def _quit_from_tray(self) -> None:
        self._quit_requested = True
        if self._tray_icon is not None:
            self._tray_icon.hide()
        app = QApplication.instance()
        if app is not None:
            app.quit()
        else:
            self.close()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._quit_requested:
            if self._tray_icon is not None:
                self._tray_icon.hide()
            app = QApplication.instance()
            if app is not None:
                app.quit()
            event.accept()
            return

        if self._minimize_to_tray_on_close and self._tray_icon is not None:
            event.ignore()
            self.hide()
            if not self._tray_notice_shown:
                self._tray_icon.showMessage(
                    "yt-dlpMaster",
                    self.tr("Application is still running in system tray."),
                    QSystemTrayIcon.MessageIcon.Information,
                    2500,
                )
                self._tray_notice_shown = True
            return

        if self._tray_icon is not None:
            self._tray_icon.hide()
        event.accept()

    def _update_tray_tooltip(self) -> None:
        if self._tray_icon is None:
            return
        if self._active_download:
            tooltip = "\n".join(
                [
                    "yt-dlpMaster",
                    self.tr("Status: {status}").format(status=self._current_status),
                    self.tr("Media: {name}").format(name=self._current_media_name),
                    self.tr("Progress: {percent}%").format(percent=self._current_progress),
                ]
            )
        else:
            tooltip = "\n".join(
                [
                    "yt-dlpMaster",
                    self.tr("Status: {status}").format(status=self._current_status),
                ]
            )
        self._tray_icon.setToolTip(tooltip)
