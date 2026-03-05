from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Any, Callable

from PySide6.QtCore import QCoreApplication, QObject, Signal, Slot
from yt_dlp import YoutubeDL

from app.core.ca import ensure_windows_ca_bundle
from app.core.ffmpeg import resolve_ffmpeg_location, resolve_ffmpeg_path, resolve_ffprobe_path


@dataclass
class DownloadRequest:
    url: str
    output_dir: Path
    format_selector: str
    merge_output_format: str | None = None
    extract_audio_codec: str | None = None
    video_audio_codec: str | None = None
    video_output_container: str | None = None
    proxy_url: str | None = None
    cookiefile: str | None = None
    cookies_from_browser: tuple[str, ...] | None = None
    transcode_compatible: bool = False
    sponsorblock_enabled: bool = False


class DownloadWorker(QObject):
    """Runs a yt-dlp download and reports progress through Qt signals."""

    progress_changed = Signal(int)
    status_changed = Signal(str)
    log_message = Signal(str)
    media_name_changed = Signal(str)
    download_finished = Signal(str)
    download_failed = Signal(str)

    def __init__(self, request: DownloadRequest) -> None:
        super().__init__()
        self._request = request

    @Slot()
    def run(self) -> None:
        try:
            ensure_windows_ca_bundle()
            self.status_changed.emit(_tr("Starting download..."))
            ytdlp_logger = _YtDlpQtLogger(self.log_message.emit)
            uses_cookies = bool(self._request.cookiefile or self._request.cookies_from_browser)
            ydl_opts = {
                "format": self._request.format_selector,
                "outtmpl": str(self._request.output_dir / "%(title)s.%(ext)s"),
                "progress_hooks": [self._on_progress],
                "logger": ytdlp_logger,
                "noplaylist": True,
                "quiet": True,
            }
            postprocessors: list[dict[str, Any]] = []
            if self._request.merge_output_format:
                ydl_opts["merge_output_format"] = self._request.merge_output_format
            if self._request.extract_audio_codec:
                postprocessors.append(
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": self._request.extract_audio_codec,
                        "preferredquality": "192",
                    }
                )
            if self._request.sponsorblock_enabled:
                sponsor_cats = [
                    "sponsor",
                    "intro",
                    "outro",
                    "selfpromo",
                    "preview",
                    "filler",
                    "interaction",
                    "music_offtopic",
                    "hook",
                ]
                postprocessors.insert(
                    0,
                    {
                        "key": "SponsorBlock",
                        "categories": sponsor_cats,
                        "api": "https://sponsor.ajay.app",
                        "when": "after_filter",
                    },
                )
                postprocessors.append(
                    {
                        "key": "ModifyChapters",
                        "remove_sponsor_segments": sponsor_cats,
                    }
                )
                self.log_message.emit(_tr("[sponsorblock] Enabled"))
            if postprocessors:
                ydl_opts["postprocessors"] = postprocessors
            if self._request.proxy_url:
                ydl_opts["proxy"] = self._request.proxy_url
            if self._request.cookiefile:
                ydl_opts["cookiefile"] = self._request.cookiefile
            if self._request.cookies_from_browser:
                ydl_opts["cookiesfrombrowser"] = self._request.cookies_from_browser
            ffmpeg_location = resolve_ffmpeg_location()
            if ffmpeg_location:
                ydl_opts["ffmpeg_location"] = ffmpeg_location
            if uses_cookies and _is_youtube_url(self._request.url):
                ydl_opts["extractor_args"] = {
                    "youtube": {
                        # Current yt-dlp behavior with logged-in cookies can include
                        # clients that require PO token and expose non-downloadable formats.
                        # Keep to clients that are usually usable without manual PO tokens.
                        "player_client": ["tv_downgraded", "web_safari", "web"],
                    }
                }
                # yt-dlp 2025.11.12+ needs an external JS runtime for complete YouTube support.
                # Use node when available to avoid relying on deno-only defaults.
                ydl_opts["js_runtimes"] = {"node": {}}
                # Allow fetching external EJS component when packaged one is unavailable.
                ydl_opts["remote_components"] = ["ejs:github"]
                self.log_message.emit(
                    _tr("[yt-dlp] Applied YouTube compatibility options: player_client + js_runtimes=node + remote_components=ejs:github")
                )

            info = self._download_with_fallback(ydl_opts)

            if self._request.video_audio_codec:
                self._convert_video_audio_codec(
                    info,
                    codec=self._request.video_audio_codec,
                    container=self._request.video_output_container or "mkv",
                )
            elif self._request.transcode_compatible:
                self._transcode_to_compatible(info)

            self.progress_changed.emit(100)
            self.download_finished.emit(_tr("Download completed."))
        except Exception as exc:  # noqa: BLE001
            message = str(exc).strip() or f"{type(exc).__name__} (no details)"
            self.download_failed.emit(message)

    def _download_with_fallback(self, ydl_opts: dict[str, Any], *, _allow_cookieless_retry: bool = True) -> Any:
        requested_format = str(ydl_opts.get("format", "")).strip()
        candidates = [requested_format, "bestvideo+bestaudio/best", "bv*+ba/b", "best"]
        seen: set[str] = set()

        last_error: Exception | None = None
        for candidate in candidates:
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)

            options = dict(ydl_opts)
            options["format"] = candidate
            try:
                if candidate != requested_format:
                    self.log_message.emit(
                        _tr("[format-fallback] Trying fallback format: {fmt}").format(fmt=candidate)
                    )
                with YoutubeDL(options) as ydl:
                    return ydl.extract_info(self._request.url, download=True)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                text = str(exc)
                if not _is_requested_format_unavailable(text):
                    raise
                self.log_message.emit(_tr("[format-fallback] Requested format unavailable, trying next option"))

        derived = self._derive_fallback_from_available_formats(ydl_opts)
        if derived and derived not in seen:
            self.log_message.emit(_tr("[format-fallback] Trying derived format: {fmt}").format(fmt=derived))
            options = dict(ydl_opts)
            options["format"] = derived
            try:
                with YoutubeDL(options) as ydl:
                    return ydl.extract_info(self._request.url, download=True)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if not _is_requested_format_unavailable(str(exc)):
                    raise
                self.log_message.emit(_tr("[format-fallback] Requested format unavailable, trying next option"))
        if not derived:
            self.log_message.emit(
                _tr("[format-fallback] Could not derive any downloadable format. Check cookies/auth and media restrictions.")
            )

        if _allow_cookieless_retry and ("cookiefile" in ydl_opts or "cookiesfrombrowser" in ydl_opts):
            self.log_message.emit(_tr("[format-fallback] Retrying without cookies"))
            cookieless_opts = dict(ydl_opts)
            cookieless_opts.pop("cookiefile", None)
            cookieless_opts.pop("cookiesfrombrowser", None)
            return self._download_with_fallback(cookieless_opts, _allow_cookieless_retry=False)

        if last_error is not None:
            if _is_requested_format_unavailable(str(last_error)):
                raise RuntimeError(
                    _tr(
                        "No downloadable formats were returned for this URL with current settings. "
                        "This is usually auth/cookies/DRM restriction, not format syntax."
                    )
                )
            raise last_error
        raise RuntimeError(_tr("Download failed: no valid format candidates"))

    def _derive_fallback_from_available_formats(self, ydl_opts: dict[str, Any]) -> str | None:
        probe_opts = dict(ydl_opts)
        probe_opts.pop("progress_hooks", None)
        probe_opts["skip_download"] = True
        probe_opts["quiet"] = True
        # Do not force a format during probe: some extractors fail format selection
        # but still return a usable formats list.
        probe_opts.pop("format", None)

        try:
            with YoutubeDL(probe_opts) as ydl:
                info = ydl.extract_info(self._request.url, download=False)
        except Exception:  # noqa: BLE001
            return None

        if isinstance(info, dict):
            entries = info.get("entries")
            if isinstance(entries, list) and entries and isinstance(entries[0], dict):
                info = entries[0]

        if not isinstance(info, dict):
            return None
        formats = info.get("formats")
        if not isinstance(formats, list) or not formats:
            return None

        av_formats = [f for f in formats if isinstance(f, dict) and str(f.get("vcodec", "none")) != "none" and str(f.get("acodec", "none")) != "none"]
        if av_formats:
            best_av = max(av_formats, key=_format_score)
            fid = str(best_av.get("format_id", "")).strip()
            return fid or None

        video_only = [f for f in formats if isinstance(f, dict) and str(f.get("vcodec", "none")) != "none" and str(f.get("acodec", "none")) == "none"]
        audio_only = [f for f in formats if isinstance(f, dict) and str(f.get("acodec", "none")) != "none" and str(f.get("vcodec", "none")) == "none"]
        if video_only and audio_only:
            best_v = max(video_only, key=_format_score)
            best_a = max(audio_only, key=_format_score)
            vid = str(best_v.get("format_id", "")).strip()
            aid = str(best_a.get("format_id", "")).strip()
            if vid and aid:
                return f"{vid}+{aid}"

        best_any = max([f for f in formats if isinstance(f, dict)], key=_format_score, default=None)
        if isinstance(best_any, dict):
            fid = str(best_any.get("format_id", "")).strip()
            return fid or None
        return None

    def _on_progress(self, info: dict[str, Any]) -> None:
        status = info.get("status")

        if status == "downloading":
            title = _extract_media_title(info)
            if title:
                self.media_name_changed.emit(title)
            downloaded = info.get("downloaded_bytes", 0)
            total = info.get("total_bytes") or info.get("total_bytes_estimate") or 0
            raw_percent = int(downloaded / total * 100) if total else 0
            percent = int(raw_percent * self._download_progress_cap() / 100)
            self.progress_changed.emit(percent)

            speed = info.get("speed")
            eta = info.get("eta")
            parts = [_tr("Progress: {percent}%").format(percent=raw_percent)]
            if speed:
                parts.append(_tr("Speed: {speed}").format(speed=self._human_speed(speed)))
            if eta is not None:
                parts.append(_tr("ETA: {seconds}s").format(seconds=eta))
            self.status_changed.emit(" | ".join(parts))

        elif status == "finished":
            self.progress_changed.emit(self._download_progress_cap())
            filename = info.get("filename", "file")
            self.media_name_changed.emit(Path(filename).stem)
            self.status_changed.emit(
                _tr("Finished processing: {filename}").format(filename=Path(filename).name)
            )
        elif status == "processing":
            title = _extract_media_title(info)
            if title:
                self.media_name_changed.emit(title)

    @staticmethod
    def _human_speed(speed_bytes_per_sec: float) -> str:
        units = ["B/s", "KB/s", "MB/s", "GB/s"]
        value = float(speed_bytes_per_sec)
        unit = units[0]
        for unit in units:
            if value < 1024 or unit == units[-1]:
                break
            value /= 1024
        return f"{value:.1f} {unit}"

    def _transcode_to_compatible(self, info: Any) -> None:
        ffmpeg = resolve_ffmpeg_path()
        if not ffmpeg:
            raise RuntimeError(_tr("ffmpeg is required for compatible transcoding but was not found"))

        files = _collect_downloaded_files(info)
        if not files:
            self.log_message.emit(_tr("[transcode] No output files detected, skipping transcoding"))
            return

        ffprobe = resolve_ffprobe_path()
        durations = [_probe_duration_seconds(ffprobe, file_path) for file_path in files]
        known_total = sum(duration for duration in durations if duration is not None)
        completed_seconds = 0.0

        self.status_changed.emit(_tr("Transcoding to compatible format..."))
        for index, file_path in enumerate(files):
            duration = durations[index]
            output_path = self._transcode_file(
                ffmpeg,
                file_path,
                duration,
                completed_seconds,
                known_total,
            )
            self.log_message.emit(
                _tr("[transcode] {src} -> {dst}").format(src=file_path.name, dst=output_path.name)
            )
            if duration is not None:
                completed_seconds += duration
                self._emit_transcode_progress(completed_seconds, known_total)

    def _transcode_file(
        self,
        ffmpeg_bin: str,
        source_path: Path,
        duration_seconds: float | None,
        completed_seconds: float,
        total_seconds: float,
    ) -> Path:
        source = source_path.resolve()
        is_audio = source.suffix.lower() in {".mp3", ".m4a", ".aac", ".flac", ".wav", ".ogg", ".opus"}

        if is_audio:
            target = source.with_suffix(".mp3")
            temp = source.with_name(f"{source.stem}.compat.mp3")
            cmd = [
                ffmpeg_bin,
                "-y",
                "-i",
                str(source),
                "-progress",
                "pipe:2",
                "-nostats",
                "-vn",
                "-c:a",
                "libmp3lame",
                "-b:a",
                "192k",
                str(temp),
            ]
        else:
            target = source.with_suffix(".mp4")
            temp = source.with_name(f"{source.stem}.compat.mp4")
            cmd = [
                ffmpeg_bin,
                "-y",
                "-i",
                str(source),
                "-progress",
                "pipe:2",
                "-nostats",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-movflags",
                "+faststart",
                str(temp),
            ]

        proc = subprocess.Popen(
            cmd,
            stderr=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )

        stderr_lines: list[str] = []
        if proc.stderr is not None:
            for line in proc.stderr:
                stderr_lines.append(line.rstrip())
                if line.startswith("out_time_ms="):
                    if duration_seconds is None or total_seconds <= 0:
                        continue
                    try:
                        out_time_ms = int(line.split("=", 1)[1].strip())
                    except ValueError:
                        continue
                    current_seconds = max(0.0, out_time_ms / 1_000_000)
                    self._emit_transcode_progress(completed_seconds + current_seconds, total_seconds)

        return_code = proc.wait()
        if return_code != 0:
            error_line = stderr_lines[-1] if stderr_lines else _tr("unknown ffmpeg error")
            raise RuntimeError(_tr("Transcoding failed for {name}: {error}").format(name=source.name, error=error_line))

        if source.exists() and source != target:
            source.unlink()
        if target.exists():
            target.unlink()
        temp.replace(target)
        return target

    def _convert_video_audio_codec(self, info: Any, codec: str, container: str) -> None:
        ffmpeg = resolve_ffmpeg_path()
        if not ffmpeg:
            raise RuntimeError(_tr("ffmpeg is required for audio codec conversion but was not found"))

        files = _collect_downloaded_files(info)
        video_files = [path for path in files if path.suffix.lower() not in {".mp3", ".m4a", ".aac", ".flac", ".wav", ".ogg", ".opus"}]
        if not video_files:
            return

        self.status_changed.emit(_tr("Converting video audio codec..."))
        for path in video_files:
            source = path.resolve()
            target = source.with_suffix(f".{container}")
            temp = source.with_name(f"{source.stem}.audiocodec.{container}")
            cmd = [
                ffmpeg,
                "-y",
                "-i",
                str(source),
                "-c:v",
                "copy",
                "-c:a",
                "libmp3lame" if codec == "mp3" else ("libopus" if codec == "opus" else "aac"),
                "-b:a",
                "192k" if codec in {"mp3", "aac"} else "160k",
                str(temp),
            ]
            if codec == "opus" and container == "mp4":
                cmd.insert(-1, "-strict")
                cmd.insert(-1, "-2")
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if proc.returncode != 0:
                stderr_tail = (proc.stderr or "").strip().splitlines()
                error_line = stderr_tail[-1] if stderr_tail else _tr("unknown ffmpeg error")
                raise RuntimeError(
                    _tr("Audio codec conversion failed for {name}: {error}").format(
                        name=source.name,
                        error=error_line,
                    )
                )
            if source.exists():
                source.unlink()
            if target.exists():
                target.unlink()
            temp.replace(target)
            self.log_message.emit(_tr("[audio-codec] {src} -> {dst}").format(src=source.name, dst=target.name))

    def _download_progress_cap(self) -> int:
        return 90 if self._request.transcode_compatible else 100

    def _emit_transcode_progress(self, processed_seconds: float, total_seconds: float) -> None:
        if total_seconds <= 0:
            return
        ratio = max(0.0, min(1.0, processed_seconds / total_seconds))
        percent = 90 + int(ratio * 10)
        self.progress_changed.emit(percent)
        self.status_changed.emit(_tr("Transcoding progress: {percent}%").format(percent=int(ratio * 100)))


class _YtDlpQtLogger:
    """Adapt yt-dlp logger callbacks to a Qt signal emitter."""

    def __init__(self, emit_log: Callable[[str], None]) -> None:
        self._emit_log = emit_log

    def debug(self, msg: str) -> None:
        self._emit_if_nonempty(f"[yt-dlp] {msg}")

    def warning(self, msg: str) -> None:
        self._emit_if_nonempty(f"[yt-dlp][warning] {msg}")

    def error(self, msg: str) -> None:
        self._emit_if_nonempty(f"[yt-dlp][error] {msg}")

    def _emit_if_nonempty(self, msg: str) -> None:
        text = msg.strip()
        if text:
            self._emit_log(text)


def _tr(text: str) -> str:
    return QCoreApplication.translate("DownloadWorker", text)


def _collect_downloaded_files(info: Any) -> list[Path]:
    paths: list[Path] = []
    seen: set[str] = set()

    if not isinstance(info, dict):
        return paths

    candidates: list[str] = []
    requested = info.get("requested_downloads")
    if isinstance(requested, list):
        for item in requested:
            if isinstance(item, dict):
                filepath = item.get("filepath")
                if isinstance(filepath, str):
                    candidates.append(filepath)

    for key in ("filepath", "_filename"):
        value = info.get(key)
        if isinstance(value, str):
            candidates.append(value)

    for candidate in candidates:
        normalized = str(Path(candidate))
        if normalized in seen:
            continue
        seen.add(normalized)
        path = Path(candidate)
        if path.exists():
            paths.append(path)
    return paths


def _format_score(fmt: dict[str, Any]) -> tuple[float, float, float]:
    height = _safe_float(fmt.get("height"))
    tbr = _safe_float(fmt.get("tbr"))
    fps = _safe_float(fmt.get("fps"))
    return (height, tbr, fps)


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _extract_media_title(info: Any) -> str | None:
    if not isinstance(info, dict):
        return None
    info_dict = info.get("info_dict")
    if isinstance(info_dict, dict):
        title = info_dict.get("title")
        if isinstance(title, str) and title.strip():
            return title.strip()
    filename = info.get("filename")
    if isinstance(filename, str) and filename.strip():
        return Path(filename).stem
    return None


def _is_requested_format_unavailable(message: str) -> bool:
    text = message.strip().lower()
    return (
        "requested format is not available" in text
        or "requested format not available" in text
        or "no video formats found" in text
    )


def _is_youtube_url(url: str) -> bool:
    text = (url or "").strip().lower()
    return "youtube.com/" in text or "youtu.be/" in text


def _probe_duration_seconds(ffprobe_bin: str | None, source_path: Path) -> float | None:
    if not ffprobe_bin:
        return None
    cmd = [
        ffprobe_bin,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(source_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        return None
    try:
        return float((proc.stdout or "").strip())
    except ValueError:
        return None
