from __future__ import annotations

import os
import platform
import sys
import tarfile
import tempfile
import json
import urllib.request
import zipfile
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QToolButton,
    QVBoxLayout,
)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _download_file(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = destination.with_suffix(destination.suffix + ".tmp")
    request = urllib.request.Request(url, headers={"User-Agent": "yt-dlpMaster-updater"})
    with urllib.request.urlopen(request, timeout=120) as response, tmp_path.open("wb") as out_file:  # noqa: S310
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            out_file.write(chunk)
    os.replace(tmp_path, destination)


def _fetch_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "yt-dlpMaster-updater"})
    with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
        payload = response.read().decode("utf-8")
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError("Unexpected JSON payload")
    return data


def _extract_from_zip(archive_path: Path, binary_name: str, destination: Path) -> None:
    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            if Path(member.filename).name.lower() != binary_name.lower():
                continue
            with archive.open(member) as source, destination.open("wb") as target:
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    target.write(chunk)
            return
    raise FileNotFoundError(f"{binary_name} not found in {archive_path.name}")


def _extract_from_tar(archive_path: Path, binary_name: str, destination: Path) -> None:
    with tarfile.open(archive_path, mode="r:*") as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            if Path(member.name).name.lower() != binary_name.lower():
                continue
            source = archive.extractfile(member)
            if source is None:
                break
            with source, destination.open("wb") as target:
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    target.write(chunk)
            return
    raise FileNotFoundError(f"{binary_name} not found in {archive_path.name}")


class BinaryUpdaterWorker(QObject):
    log = Signal(str)
    progress = Signal(int)
    finished = Signal(bool)

    def __init__(self, root_dir: Path) -> None:
        super().__init__()
        self._root_dir = root_dir
        self._state_path = self._root_dir / "bin" / ".updater_state.json"
        self._state = self._load_state()

    def _log_start(self, component: str) -> None:
        self.log.emit(f"[START] {component}")

    def _log_skip(self, component: str, reason: str) -> None:
        self.log.emit(f"[SKIP] {component}: {reason}")

    def _log_ok(self, component: str, message: str) -> None:
        self.log.emit(f"[OK] {component}: {message}")

    def _log_error(self, component: str, message: str) -> None:
        self.log.emit(f"[ERROR] {component}: {message}")

    def run(self) -> None:
        self.progress.emit(0)
        all_ok = True

        if not self._update_ytdlp_binary():
            all_ok = False
        self.progress.emit(25)
        if not self._update_ytdlp_ejs_static():
            all_ok = False
        self.progress.emit(50)
        if not self._update_ffmpeg():
            all_ok = False
        self.progress.emit(75)
        if not self._update_certifi_bundle():
            all_ok = False
        self.progress.emit(100)
        self._save_state()

        self.finished.emit(all_ok)

    def _load_state(self) -> dict:
        try:
            if self._state_path.exists():
                data = json.loads(self._state_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
        return {}

    def _save_state(self) -> None:
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            self._state_path.write_text(json.dumps(self._state, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            self._log_error("state", f"не удалось сохранить состояние обновлятора: {exc}")

    @staticmethod
    def _run_command(command: list[str]) -> tuple[int, str]:
        process = None
        try:
            import subprocess

            process = subprocess.run(command, text=True, capture_output=True, check=False)
            output = process.stdout.strip() or process.stderr.strip() or ""
            return process.returncode, output
        except Exception as exc:  # noqa: BLE001
            return 1, str(exc)

    @staticmethod
    def _fetch_headers(url: str) -> dict[str, str]:
        request = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
            return {k.lower(): v for k, v in response.headers.items()}

    def _update_ytdlp_binary(self) -> bool:
        is_windows = sys.platform.startswith("win")
        target_name = "yt-dlp.exe" if is_windows else "yt-dlp"
        target_path = self._root_dir / "bin" / target_name
        url = (
            "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
            if is_windows
            else "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp"
        )

        self._log_start("yt-dlp (standalone binary)")
        try:
            local_version = ""
            if target_path.exists():
                rc, output = self._run_command([str(target_path), "--version"])
                if rc == 0:
                    local_version = output.strip()

            remote_tag = ""
            try:
                api_payload = _fetch_json("https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest")
                remote_tag = str(api_payload.get("tag_name", "")).strip().lstrip("v")
            except Exception as exc:  # noqa: BLE001
                self.log.emit(f"Не удалось получить remote версию yt-dlp: {exc}")

            if local_version and remote_tag and local_version == remote_tag:
                self._log_skip("yt-dlp", f"уже актуален ({local_version})")
                return True

            _download_file(url, target_path)
            if not is_windows:
                target_path.chmod(0o755)
            rc, output = self._run_command([str(target_path), "--version"])
            installed_version = output.strip() if rc == 0 else "unknown"
            self._state["yt-dlp"] = {"version": installed_version}
            self._log_ok("yt-dlp", f"обновлен: {target_path} (версия: {installed_version})")
            return True
        except Exception as exc:  # noqa: BLE001
            self._log_error("yt-dlp", str(exc))
            return False

    def _update_ffmpeg(self) -> bool:
        is_windows = sys.platform.startswith("win")
        is_linux = sys.platform.startswith("linux")
        self._log_start("ffmpeg/ffprobe")
        bin_dir = self._root_dir / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        ffmpeg_name = "ffmpeg.exe" if is_windows else "ffmpeg"
        ffprobe_name = "ffprobe.exe" if is_windows else "ffprobe"
        ffmpeg_dst = bin_dir / ffmpeg_name
        ffprobe_dst = bin_dir / ffprobe_name

        try:
            with tempfile.TemporaryDirectory(prefix="ytdlpmaster-ffmpeg-") as tmp_dir_str:
                tmp_dir = Path(tmp_dir_str)
                if is_windows:
                    ffmpeg_url = os.environ.get(
                        "FFMPEG_WINDOWS_URL",
                        "https://github.com/BtbN/FFmpeg-Builds/releases/latest/download/ffmpeg-master-latest-win64-lgpl.zip",
                    )
                    archive = tmp_dir / "ffmpeg-win.zip"
                    if self._is_ffmpeg_source_current(ffmpeg_url, ffmpeg_dst, ffprobe_dst):
                        self._log_skip("ffmpeg/ffprobe", "уже актуален")
                        return True
                    _download_file(ffmpeg_url, archive)
                    _extract_from_zip(archive, ffmpeg_name, ffmpeg_dst)
                    _extract_from_zip(archive, ffprobe_name, ffprobe_dst)
                elif is_linux:
                    ffmpeg_url = os.environ.get(
                        "FFMPEG_LINUX_URL",
                        "https://github.com/BtbN/FFmpeg-Builds/releases/latest/download/ffmpeg-master-latest-linux64-lgpl.tar.xz",
                    )
                    archive = tmp_dir / "ffmpeg-linux.tar.xz"
                    if self._is_ffmpeg_source_current(ffmpeg_url, ffmpeg_dst, ffprobe_dst):
                        self._log_skip("ffmpeg/ffprobe", "уже актуален")
                        return True
                    _download_file(ffmpeg_url, archive)
                    _extract_from_tar(archive, ffmpeg_name, ffmpeg_dst)
                    _extract_from_tar(archive, ffprobe_name, ffprobe_dst)
                else:
                    self._log_error("ffmpeg/ffprobe", f"неподдерживаемая платформа: {sys.platform}")
                    return False

            if not is_windows:
                ffmpeg_dst.chmod(0o755)
                ffprobe_dst.chmod(0o755)
            ffmpeg_version = self._detect_ffmpeg_version(ffmpeg_dst)
            pending = str(self._state.get("ffmpeg", {}).get("pending_fingerprint", ""))
            self._state["ffmpeg"] = {
                "source_fingerprint": pending,
                "version": ffmpeg_version,
            }
            self._log_ok("ffmpeg", f"обновлен: {ffmpeg_dst}")
            self._log_ok("ffprobe", f"обновлен: {ffprobe_dst}")
            return True
        except Exception as exc:  # noqa: BLE001
            self._log_error("ffmpeg/ffprobe", str(exc))
            return False

    def _is_ffmpeg_source_current(
        self,
        primary_url: str,
        ffmpeg_dst: Path,
        ffprobe_dst: Path,
        *,
        extra_urls: list[str] | None = None,
    ) -> bool:
        if not ffmpeg_dst.exists() or not ffprobe_dst.exists():
            return False
        self._state.setdefault("ffmpeg", {})
        self._state["ffmpeg"]["pending_fingerprint"] = ""
        urls = [primary_url]
        if extra_urls:
            urls = extra_urls
        fingerprints: list[str] = []
        for url in urls:
            try:
                headers = self._fetch_headers(url)
            except Exception:
                return False
            etag = headers.get("etag", "")
            modified = headers.get("last-modified", "")
            length = headers.get("content-length", "")
            fingerprints.append(f"{url}|{etag}|{modified}|{length}")
        fingerprint = ";".join(fingerprints)
        self._state["ffmpeg"]["pending_fingerprint"] = fingerprint
        saved = str(self._state.get("ffmpeg", {}).get("source_fingerprint", ""))
        return bool(saved and saved == fingerprint)

    def _detect_ffmpeg_version(self, ffmpeg_path: Path) -> str:
        rc, output = self._run_command([str(ffmpeg_path), "-version"])
        if rc != 0 or not output:
            return "unknown"
        first_line = output.splitlines()[0].strip()
        return first_line or "unknown"

    def _update_ytdlp_ejs_static(self) -> bool:
        self._log_start("yt-dlp-ejs (static)")
        target_dir = self._root_dir / "bin" / "yt-dlp-ejs" / "yt" / "solver"
        core_path = target_dir / "core.min.js"
        lib_path = target_dir / "lib.min.js"

        ok, changed = self._update_ytdlp_ejs_from_github(core_path, lib_path)
        if ok:
            if changed:
                self._log_ok("yt-dlp-ejs core", f"обновлен: {core_path}")
                self._log_ok("yt-dlp-ejs lib", f"обновлен: {lib_path}")
            return True

        self._log_error("yt-dlp-ejs", "источник GitHub недоступен или невалиден")
        return False

    def _update_ytdlp_ejs_from_github(self, core_path: Path, lib_path: Path) -> tuple[bool, bool]:
        release_api_url = os.environ.get(
            "YTDLP_EJS_GITHUB_RELEASE_API_URL",
            "https://api.github.com/repos/yt-dlp/ejs/releases/latest",
        ).strip()
        try:
            payload = _fetch_json(release_api_url)
            remote_version = str(payload.get("tag_name", "")).strip().lstrip("v")
            local_version = str(self._state.get("yt-dlp-ejs", {}).get("version", "")).strip()
            if remote_version and local_version and remote_version == local_version and core_path.exists() and lib_path.exists():
                self._log_skip("yt-dlp-ejs", f"уже актуален ({local_version})")
                return True, False
            assets = payload.get("assets")
            if not isinstance(assets, list):
                raise ValueError("Invalid 'assets' in GitHub release JSON")

            wheel_url = None
            for item in assets:
                if not isinstance(item, dict):
                    continue
                filename = str(item.get("filename", ""))
                if filename.endswith("-py3-none-any.whl"):
                    wheel_url = str(item.get("browser_download_url", "")).strip()
                    break
            if not wheel_url:
                for item in assets:
                    if not isinstance(item, dict):
                        continue
                    filename = str(item.get("filename", ""))
                    if filename.endswith(".whl"):
                        wheel_url = str(item.get("browser_download_url", "")).strip()
                        if wheel_url:
                            break
            if not wheel_url:
                raise ValueError("Wheel asset URL not found in GitHub release")

            with tempfile.TemporaryDirectory(prefix="ytdlpmaster-ejs-") as tmp_dir_str:
                tmp_dir = Path(tmp_dir_str)
                wheel_path = tmp_dir / "yt_dlp_ejs.whl"
                _download_file(wheel_url, wheel_path)

                with zipfile.ZipFile(wheel_path) as wheel:
                    core_member = "yt_dlp_ejs/yt/solver/core.min.js"
                    lib_member = "yt_dlp_ejs/yt/solver/lib.min.js"
                    core_data = wheel.read(core_member)
                    lib_data = wheel.read(lib_member)
                core_path.parent.mkdir(parents=True, exist_ok=True)
                core_path.write_bytes(core_data)
                lib_path.write_bytes(lib_data)
                self._state["yt-dlp-ejs"] = {"version": remote_version or "unknown"}
            return True, True
        except Exception as exc:  # noqa: BLE001
            self._log_error("yt-dlp-ejs", f"GitHub источник не подошел: {exc}")
            return False, False

    def _update_certifi_bundle(self) -> bool:
        target_path = self._root_dir / "bin" / "certifi.pem"
        url = "https://raw.githubusercontent.com/certifi/python-certifi/master/certifi/cacert.pem"
        self._log_start("certifi CA bundle")
        try:
            headers = {}
            try:
                headers = self._fetch_headers(url)
            except Exception as exc:  # noqa: BLE001
                self._log_error("certifi CA bundle", f"не удалось получить HEAD: {exc}")
            if headers and target_path.exists():
                fingerprint = f"{url}|{headers.get('etag','')}|{headers.get('last-modified','')}|{headers.get('content-length','')}"
                saved = str(self._state.get("certifi", {}).get("source_fingerprint", ""))
                if saved and saved == fingerprint:
                    self._log_skip("certifi CA bundle", "уже актуален")
                    return True
                self._state["certifi"] = {"source_fingerprint": fingerprint}
            _download_file(url, target_path)
            if "certifi" not in self._state:
                self._state["certifi"] = {}
            self._log_ok("certifi CA bundle", f"обновлен: {target_path}")
            return True
        except Exception as exc:  # noqa: BLE001
            self._log_error("certifi CA bundle", str(exc))
            return False


class UpdaterDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Обновлятор")
        self.setMinimumSize(540, 170)

        self._root_dir = _project_root()
        self._thread: QThread | None = None
        self._worker: BinaryUpdaterWorker | None = None

        root = QVBoxLayout(self)

        os_label = platform.system() or "Unknown OS"
        self._info_label = QLabel(
            f"Компоненты: yt-dlp, yt-dlp-ejs (static), ffmpeg/ffprobe, certifi | ОС: {os_label}"
        )
        self._info_label.setWordWrap(True)
        root.addWidget(self._info_label)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        root.addWidget(self._progress)

        self._log_toggle_btn = QToolButton()
        self._log_toggle_btn.setCheckable(True)
        self._log_toggle_btn.setChecked(False)
        self._log_toggle_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._log_toggle_btn.setStyleSheet("QToolButton { padding: 0px; margin: 0px; }")
        self._log_toggle_btn.toggled.connect(self._toggle_log_panel)

        self._update_btn = QPushButton("Обновить")
        self._update_btn.clicked.connect(self._start_update)
        self._close_btn = QPushButton("Закрыть")
        self._close_btn.clicked.connect(self.accept)

        controls_row = QHBoxLayout()
        controls_row.setContentsMargins(0, 0, 0, 0)
        controls_row.setSpacing(8)
        controls_row.addWidget(self._log_toggle_btn, 0, Qt.AlignLeft)
        controls_row.addStretch(1)
        controls_row.addWidget(self._update_btn, 0, Qt.AlignRight)
        controls_row.addWidget(self._close_btn, 0, Qt.AlignRight)
        root.addLayout(controls_row)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(400)
        self._set_log_constraints(False)
        self._update_log_toggle_ui(False)
        root.addWidget(self._log, 1)

    def _start_update(self) -> None:
        if self._thread is not None:
            return
        self._log.clear()
        self._append_log("Запуск обновления бинарных компонентов...")
        self._update_btn.setEnabled(False)
        self._close_btn.setEnabled(False)

        worker = BinaryUpdaterWorker(self._root_dir)
        thread = QThread(self)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.log.connect(self._append_log)
        worker.progress.connect(self._on_progress)
        worker.finished.connect(self._on_finished)

        worker.finished.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._on_thread_finished)

        self._worker = worker
        self._thread = thread
        thread.start()

    def _append_log(self, text: str) -> None:
        self._log.appendPlainText(text)
        self._log.verticalScrollBar().setValue(self._log.verticalScrollBar().maximum())

    def _on_finished(self, ok: bool) -> None:
        if ok:
            self._append_log("Готово: обновление завершено.")
        else:
            self._append_log("Обновление завершено с ошибками.")
            self._set_log_expanded(True)
        self._progress.setValue(100)

    def _on_progress(self, value: int) -> None:
        self._progress.setValue(max(0, min(100, value)))

    def _on_thread_finished(self) -> None:
        self._thread = None
        self._worker = None
        self._update_btn.setEnabled(True)
        self._close_btn.setEnabled(True)

    def _toggle_log_panel(self, expanded: bool) -> None:
        self._set_log_constraints(expanded)
        self._update_log_toggle_ui(expanded)
        self.adjustSize()

    def _set_log_expanded(self, expanded: bool) -> None:
        if self._log_toggle_btn.isChecked() != expanded:
            self._log_toggle_btn.setChecked(expanded)
            return
        self._toggle_log_panel(expanded)

    def _set_log_constraints(self, expanded: bool) -> None:
        if expanded:
            self._log.setMinimumHeight(180)
            self._log.setMaximumHeight(16777215)
            self._log.setVisible(True)
            return
        self._log.setMinimumHeight(0)
        self._log.setMaximumHeight(0)
        self._log.setVisible(False)

    def _update_log_toggle_ui(self, expanded: bool) -> None:
        self._log_toggle_btn.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self._log_toggle_btn.setText("Скрыть лог" if expanded else "Показать лог")

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._thread is not None:
            event.ignore()
            return
        super().closeEvent(event)
