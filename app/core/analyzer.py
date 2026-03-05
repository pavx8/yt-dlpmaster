from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from PySide6.QtCore import QCoreApplication, QObject, Signal, Slot
from yt_dlp import YoutubeDL

from app.core.ca import ensure_windows_ca_bundle
from app.core.ffmpeg import resolve_ffmpeg_location


@dataclass
class AnalyzeRequest:
    url: str
    proxy_url: str | None = None
    cookiefile: str | None = None
    cookies_from_browser: tuple[str, ...] | None = None


class AnalyzeWorker(QObject):
    status_changed = Signal(str)
    analysis_finished = Signal(list)
    preview_ready = Signal(str, str, bytes)
    analysis_failed = Signal(str)

    def __init__(self, request: AnalyzeRequest) -> None:
        super().__init__()
        self._request = request

    @Slot()
    def run(self) -> None:
        try:
            ensure_windows_ca_bundle()
            self.status_changed.emit(_tr("Analyzing URL..."))
            ydl_opts: dict[str, Any] = {
                "quiet": True,
                "noplaylist": True,
                "skip_download": True,
            }
            if self._request.proxy_url:
                ydl_opts["proxy"] = self._request.proxy_url
            if self._request.cookiefile:
                ydl_opts["cookiefile"] = self._request.cookiefile
            if self._request.cookies_from_browser:
                ydl_opts["cookiesfrombrowser"] = self._request.cookies_from_browser
            ffmpeg_location = resolve_ffmpeg_location()
            if ffmpeg_location:
                ydl_opts["ffmpeg_location"] = ffmpeg_location
            if (self._request.cookiefile or self._request.cookies_from_browser) and _is_youtube_url(self._request.url):
                ydl_opts["extractor_args"] = {
                    "youtube": {
                        "player_client": ["tv_downgraded", "web_safari", "web"],
                    }
                }
                ydl_opts["js_runtimes"] = {"node": {}}
                ydl_opts["remote_components"] = ["ejs:github"]

            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self._request.url, download=False)
                title, duration, image_bytes = _extract_preview_data(info, ydl)

            presets = _detect_presets(info)
            self.preview_ready.emit(title, duration, image_bytes)
            self.analysis_finished.emit(presets)
        except Exception as exc:  # noqa: BLE001
            self.analysis_failed.emit(str(exc).strip() or f"{type(exc).__name__} (no details)")


def _detect_presets(info: Any) -> list[dict[str, Any]]:
    if isinstance(info, dict):
        entries = info.get("entries")
        if isinstance(entries, list) and entries and isinstance(entries[0], dict):
            info = entries[0]

    if not isinstance(info, dict):
        return _default_presets()

    formats = info.get("formats")
    if not isinstance(formats, list):
        formats = []

    has_audio = any(_has_audio(fmt) for fmt in formats)
    has_video = any(_has_video(fmt) for fmt in formats)
    if not has_audio and not has_video:
        return _default_presets()

    presets: list[dict[str, Any]] = []
    heights = sorted({_height(fmt) for fmt in formats if _has_video(fmt) and _height(fmt) > 0}, reverse=True)
    selected_heights = [height for height in heights if height >= 144]
    for height in selected_heights:
        presets.append(
            {
                "label": f"{height}p + audio mp3 + container mp4",
                "format": _height_bound_format_selector(height),
                "merge_output_format": "mp4",
                "extract_audio_codec": None,
                "video_audio_codec": "mp3",
                "video_output_container": "mp4",
            }
        )
        presets.append(
            {
                "label": f"{height}p + audio opus + container mp4",
                "format": _height_bound_format_selector(height),
                "merge_output_format": "mp4",
                "extract_audio_codec": None,
                "video_audio_codec": "opus",
                "video_output_container": "mp4",
            }
        )

    if has_video and has_audio and not presets:
        presets.append(
            {
                "label": "Best available + audio (mp4)",
                "format": "bestvideo+bestaudio/best",
                "merge_output_format": "mp4",
                "extract_audio_codec": None,
                "video_audio_codec": None,
                "video_output_container": None,
            }
        )
        presets.append(
            {
                "label": "Best available + audio mp3 + container mp4",
                "format": "bestvideo+bestaudio/best",
                "merge_output_format": "mp4",
                "extract_audio_codec": None,
                "video_audio_codec": "mp3",
                "video_output_container": "mp4",
            }
        )
        presets.append(
            {
                "label": "Best available + audio opus + container mp4",
                "format": "bestvideo+bestaudio/best",
                "merge_output_format": "mp4",
                "extract_audio_codec": None,
                "video_audio_codec": "opus",
                "video_output_container": "mp4",
            }
        )

    if has_audio:
        presets.append(
            {
                "label": "Audio only (mp3)",
                "format": "bestaudio/best",
                "merge_output_format": None,
                "extract_audio_codec": "mp3",
                "video_audio_codec": None,
                "video_output_container": None,
            }
        )
        presets.append(
            {
                "label": "Audio only (opus)",
                "format": "bestaudio[acodec*=opus]/bestaudio/best",
                "merge_output_format": None,
                "extract_audio_codec": "opus",
                "video_audio_codec": None,
                "video_output_container": None,
            }
        )

    if not presets:
        return _default_presets()

    return _dedupe_presets(presets)


def _has_audio(fmt: Any) -> bool:
    return isinstance(fmt, dict) and str(fmt.get("acodec", "none")) != "none"


def _has_video(fmt: Any) -> bool:
    return isinstance(fmt, dict) and str(fmt.get("vcodec", "none")) != "none"


def _height(fmt: Any) -> int:
    if not isinstance(fmt, dict):
        return 0
    value = fmt.get("height")
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _tr(text: str) -> str:
    return QCoreApplication.translate("AnalyzeWorker", text)


def _is_youtube_url(url: str) -> bool:
    text = (url or "").strip().lower()
    return "youtube.com/" in text or "youtu.be/" in text


def _extract_preview_data(info: Any, ydl: YoutubeDL) -> tuple[str, str, bytes]:
    title = ""
    duration = ""
    thumbnail_url = ""
    if isinstance(info, dict):
        entries = info.get("entries")
        if isinstance(entries, list) and entries and isinstance(entries[0], dict):
            info = entries[0]

        title_value = info.get("title")
        if isinstance(title_value, str):
            title = title_value.strip()
        duration = _format_duration(info.get("duration"))

        thumbnails = info.get("thumbnails")
        if isinstance(thumbnails, list) and thumbnails:
            thumbnail_url = _pick_thumbnail_url(thumbnails)
        if not thumbnail_url:
            single = info.get("thumbnail")
            if isinstance(single, str):
                thumbnail_url = single.strip()

    if not thumbnail_url:
        return title, duration, b""

    try:
        with ydl.urlopen(thumbnail_url) as response:
            data = response.read()
    except Exception:  # noqa: BLE001
        return title, duration, b""
    return title, duration, data


def _format_duration(value: Any) -> str:
    try:
        total = int(value)
    except (TypeError, ValueError):
        return ""
    if total < 0:
        return ""
    hours, rem = divmod(total, 3600)
    minutes, seconds = divmod(rem, 60)
    if hours > 0:
        return f"{hours:d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:d}:{seconds:02d}"


def _pick_thumbnail_url(thumbnails: list[Any]) -> str:
    best_url = ""
    best_score = -1
    for item in thumbnails:
        if not isinstance(item, dict):
            continue
        raw_url = item.get("url")
        if not isinstance(raw_url, str) or not raw_url.strip():
            continue
        url = raw_url.strip()
        ext = _thumbnail_ext(url)
        width = _safe_int(item.get("width"))
        height = _safe_int(item.get("height"))
        area = width * height if width > 0 and height > 0 else 0

        # Prefer widely supported formats first, then bigger thumbnail.
        ext_bonus = 100_000_000 if ext in {"jpg", "jpeg", "png"} else 0
        score = ext_bonus + area
        if score > best_score:
            best_score = score
            best_url = url
    return best_url


def _thumbnail_ext(url: str) -> str:
    path = urlparse(url).path.lower()
    if "." not in path:
        return ""
    return path.rsplit(".", 1)[1]


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _height_bound_format_selector(height: int) -> str:
    # Use <= height to avoid failures on sources where exact-height variants
    # are not available in a mergable combination.
    return (
        f"bestvideo[height<={height}]+bestaudio/"
        f"best[height<={height}]/best"
    )


def _default_presets() -> list[dict[str, Any]]:
    return [
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


def _dedupe_presets(presets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str, bool]] = set()
    result: list[dict[str, Any]] = []
    for preset in presets:
        key = (
            str(preset.get("label", "")),
            str(preset.get("format", "")),
            str(preset.get("merge_output_format") or ""),
            str(preset.get("extract_audio_codec") or ""),
            str(preset.get("video_audio_codec") or ""),
            str(preset.get("video_output_container") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(preset)
    return result
