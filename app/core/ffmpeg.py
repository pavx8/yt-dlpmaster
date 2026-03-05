from __future__ import annotations

from pathlib import Path
import os
import shutil
import sys


def resolve_ffmpeg_path() -> str | None:
    return _resolve_binary("ffmpeg")


def resolve_ffprobe_path() -> str | None:
    return _resolve_binary("ffprobe")


def resolve_ffmpeg_location() -> str | None:
    ffmpeg_path = resolve_ffmpeg_path()
    if not ffmpeg_path:
        return None
    return str(Path(ffmpeg_path).parent)


def _resolve_binary(name: str) -> str | None:
    executable = f"{name}.exe" if sys.platform.startswith("win") else name
    embedded = _resolve_embedded_binary(executable)
    system = shutil.which(name)
    if _use_embedded_binaries():
        return embedded or system
    return system or embedded


def _resolve_embedded_binary(executable: str) -> str | None:
    for base_dir in _candidate_base_dirs():
        for rel in ("bin", "", "ffmpeg", "ffmpeg/bin"):
            candidate = base_dir / rel / executable
            if candidate.exists() and candidate.is_file():
                return str(candidate)
    return None


def _candidate_base_dirs() -> list[Path]:
    candidates: list[Path] = []
    # PyInstaller one-file extraction directory.
    meipass = getattr(sys, "_MEIPASS", None)
    if isinstance(meipass, str) and meipass:
        candidates.append(Path(meipass))

    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent)
    else:
        package_dir = Path(__file__).resolve().parent.parent
        candidates.append(package_dir)
        candidates.append(package_dir.parent)
    unique: list[Path] = []
    for candidate in candidates:
        if candidate not in unique:
            unique.append(candidate)
    return unique


def _use_embedded_binaries() -> bool:
    return os.environ.get("YTDLPM_USE_EMBEDDED_BINARIES", "1").strip() != "0"
