from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata
import os
import platform
from pathlib import Path
import sys


@dataclass(frozen=True)
class CaBundleInfo:
    certifi_version: str
    certifi_bundle_path: str
    ssl_cert_file: str
    requests_ca_bundle: str


def _certifi_bundle_path() -> str:
    embedded = _embedded_ca_bundle_path()
    if embedded:
        return embedded
    try:
        import certifi
    except Exception:  # noqa: BLE001
        return ""
    try:
        return certifi.where() or ""
    except Exception:  # noqa: BLE001
        return ""


def _embedded_ca_bundle_path() -> str:
    for base_dir in _candidate_base_dirs():
        for rel in ("bin/certifi.pem", "certifi/cacert.pem", "cacert.pem"):
            candidate = base_dir / rel
            if candidate.exists() and candidate.is_file():
                return str(candidate)
    return ""


def _candidate_base_dirs() -> list[Path]:
    candidates: list[Path] = []
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


def _certifi_version() -> str:
    try:
        return metadata.version("certifi")
    except metadata.PackageNotFoundError:
        return "not installed"


def get_ca_bundle_info() -> CaBundleInfo:
    return CaBundleInfo(
        certifi_version=_certifi_version(),
        certifi_bundle_path=_certifi_bundle_path(),
        ssl_cert_file=os.environ.get("SSL_CERT_FILE", "").strip(),
        requests_ca_bundle=os.environ.get("REQUESTS_CA_BUNDLE", "").strip(),
    )


def ensure_windows_ca_bundle() -> CaBundleInfo:
    """Configure CA env vars on Windows via certifi when SSL_CERT_FILE is missing."""
    info = get_ca_bundle_info()
    if not _use_embedded_libraries():
        if os.environ.get("YTDLPM_SSL_SET_BY_APP") == "1":
            os.environ.pop("SSL_CERT_FILE", None)
            os.environ.pop("REQUESTS_CA_BUNDLE", None)
            os.environ.pop("YTDLPM_SSL_SET_BY_APP", None)
        return get_ca_bundle_info()
    if platform.system().lower() != "windows":
        return info
    if info.ssl_cert_file:
        return info
    if not info.certifi_bundle_path:
        return info

    os.environ["SSL_CERT_FILE"] = info.certifi_bundle_path
    if not info.requests_ca_bundle:
        os.environ["REQUESTS_CA_BUNDLE"] = info.certifi_bundle_path
    os.environ["YTDLPM_SSL_SET_BY_APP"] = "1"
    return get_ca_bundle_info()


def _use_embedded_libraries() -> bool:
    return os.environ.get("YTDLPM_USE_EMBEDDED_LIBRARIES", "1").strip() != "0"
