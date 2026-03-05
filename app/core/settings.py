from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from PySide6.QtCore import QSettings


PROXY_SCHEMES = ("socks4", "socks5", "socks5h", "http", "https")


@dataclass
class ProxySettings:
    enabled: bool = False
    scheme: str = "socks5h"
    host: str = ""
    port: int = 1080
    username: str = ""
    password: str = ""

    def build_proxy_url(self) -> str | None:
        if not self.enabled:
            return None

        scheme = self.scheme if self.scheme in PROXY_SCHEMES else "socks5h"
        host = self.host.strip()
        if not host:
            return None

        if self.port < 1 or self.port > 65535:
            return None

        auth = ""
        if self.username:
            user = quote(self.username, safe="")
            pwd = quote(self.password, safe="")
            auth = f"{user}:{pwd}@"

        return f"{scheme}://{auth}{host}:{self.port}"

    def masked_proxy_label(self) -> str:
        if not self.enabled:
            return "disabled"

        scheme = self.scheme if self.scheme in PROXY_SCHEMES else "socks5h"
        host = self.host.strip() or "?"
        port = self.port if 1 <= self.port <= 65535 else "?"

        if self.username:
            return f"{scheme}://{self.username}:***@{host}:{port}"
        return f"{scheme}://{host}:{port}"


@dataclass
class CookiesSettings:
    mode: str = "none"  # none | browser | file
    browser: str = "firefox"
    browser_profile: str = ""
    file_path: str = ""

    def validate(self) -> str | None:
        if self.mode == "browser":
            profile = self.browser_profile.strip()
            if not profile:
                return "Browser profile is required"
            if ("/" in profile or "\\" in profile) and not Path(profile).exists():
                return "Browser profile path does not exist"
        if self.mode == "file":
            path = self.file_path.strip()
            if not path:
                return "Cookies file path is required"
            if not Path(path).exists():
                return "Cookies file does not exist"
        return None

    def cookiefile_option(self) -> str | None:
        if self.mode != "file":
            return None
        path = self.file_path.strip()
        return path or None

    def cookiesfrombrowser_option(self) -> tuple[str, ...] | None:
        if self.mode != "browser":
            return None
        browser = self.browser.strip() or "firefox"
        profile = self.browser_profile.strip()
        if profile:
            return (browser, profile)
        return (browser,)

    def summary(self) -> str:
        if self.mode == "file":
            return f"file: {self.file_path.strip() or '?'}"
        if self.mode == "browser":
            if self.browser_profile.strip():
                return f"browser: {self.browser} ({self.browser_profile.strip()})"
            return f"browser: {self.browser}"
        return "disabled"


@dataclass
class ComponentsSettings:
    use_embedded_binaries: bool = True
    use_embedded_libraries: bool = True


def load_proxy_settings(settings: QSettings) -> ProxySettings:
    settings.beginGroup("proxy")
    proxy = ProxySettings(
        enabled=_as_bool(settings.value("enabled", False)),
        scheme=str(settings.value("scheme", "socks5h") or "socks5h"),
        host=str(settings.value("host", "") or ""),
        port=_as_int(settings.value("port", 1080), 1080),
        username=str(settings.value("username", "") or ""),
        password=str(settings.value("password", "") or ""),
    )
    settings.endGroup()

    if proxy.scheme not in PROXY_SCHEMES:
        proxy.scheme = "socks5h"
    return proxy


def load_cookies_settings(settings: QSettings) -> CookiesSettings:
    mode = str(settings.value("cookies/mode", "none") or "none").strip().lower()
    if mode not in {"none", "browser", "file"}:
        mode = "none"
    return CookiesSettings(
        mode=mode,
        browser=str(settings.value("cookies/browser", "firefox") or "firefox"),
        browser_profile=str(settings.value("cookies/browser_profile", "") or ""),
        file_path=str(settings.value("cookies/file_path", "") or ""),
    )


def save_cookies_settings(settings: QSettings, cookies: CookiesSettings) -> None:
    settings.setValue("cookies/mode", cookies.mode)
    settings.setValue("cookies/browser", cookies.browser)
    settings.setValue("cookies/browser_profile", cookies.browser_profile)
    settings.setValue("cookies/file_path", cookies.file_path)
    settings.sync()


def ensure_default_settings(settings: QSettings) -> None:
    defaults: dict[str, object] = {
        "ui/language": "",
        "ui/theme": "system",
        "ui/minimize_to_tray_on_close": True,
        "download/transcode_compatible": False,
        "download/sponsorblock_enabled": False,
        "proxy/enabled": False,
        "proxy/scheme": "socks5h",
        "proxy/host": "",
        "proxy/port": 1080,
        "proxy/username": "",
        "proxy/password": "",
        "cookies/mode": "none",
        "cookies/browser": "firefox",
        "cookies/browser_profile": "",
        "cookies/file_path": "",
        "components/use_embedded_binaries": True,
        "components/use_embedded_libraries": True,
    }

    for key, value in defaults.items():
        if not settings.contains(key):
            settings.setValue(key, value)
    settings.sync()


def save_proxy_settings(settings: QSettings, proxy: ProxySettings) -> None:
    settings.beginGroup("proxy")
    settings.setValue("enabled", proxy.enabled)
    settings.setValue("scheme", proxy.scheme)
    settings.setValue("host", proxy.host.strip())
    settings.setValue("port", int(proxy.port))
    settings.setValue("username", proxy.username)
    settings.setValue("password", proxy.password)
    settings.endGroup()
    settings.sync()


def load_ui_language(settings: QSettings) -> str:
    value = str(settings.value("ui/language", "") or "").strip()
    return value


def save_ui_language(settings: QSettings, language_code: str) -> None:
    settings.setValue("ui/language", language_code.strip())
    settings.sync()


def load_ui_theme(settings: QSettings) -> str:
    value = str(settings.value("ui/theme", "system") or "system").strip().lower()
    if value not in {"system", "light", "dark"}:
        return "system"
    return value


def save_ui_theme(settings: QSettings, theme_code: str) -> None:
    value = (theme_code or "system").strip().lower()
    if value not in {"system", "light", "dark"}:
        value = "system"
    settings.setValue("ui/theme", value)
    settings.sync()


def load_minimize_to_tray_on_close(settings: QSettings) -> bool:
    return _as_bool(settings.value("ui/minimize_to_tray_on_close", True))


def save_minimize_to_tray_on_close(settings: QSettings, enabled: bool) -> None:
    settings.setValue("ui/minimize_to_tray_on_close", bool(enabled))
    settings.sync()


def load_transcode_compatible(settings: QSettings) -> bool:
    return _as_bool(settings.value("download/transcode_compatible", False))


def save_transcode_compatible(settings: QSettings, enabled: bool) -> None:
    settings.setValue("download/transcode_compatible", bool(enabled))
    settings.sync()


def load_sponsorblock_enabled(settings: QSettings) -> bool:
    return _as_bool(settings.value("download/sponsorblock_enabled", False))


def save_sponsorblock_enabled(settings: QSettings, enabled: bool) -> None:
    settings.setValue("download/sponsorblock_enabled", bool(enabled))
    settings.sync()


def load_components_settings(settings: QSettings) -> ComponentsSettings:
    return ComponentsSettings(
        use_embedded_binaries=_as_bool(settings.value("components/use_embedded_binaries", True)),
        use_embedded_libraries=_as_bool(settings.value("components/use_embedded_libraries", True)),
    )


def save_components_settings(settings: QSettings, components: ComponentsSettings) -> None:
    settings.setValue("components/use_embedded_binaries", bool(components.use_embedded_binaries))
    settings.setValue("components/use_embedded_libraries", bool(components.use_embedded_libraries))
    settings.sync()


def apply_components_settings(components: ComponentsSettings) -> None:
    import os

    os.environ["YTDLPM_USE_EMBEDDED_BINARIES"] = "1" if components.use_embedded_binaries else "0"
    os.environ["YTDLPM_USE_EMBEDDED_LIBRARIES"] = "1" if components.use_embedded_libraries else "0"


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _as_int(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def autodetect_browser_profiles(browser: str) -> list[str]:
    home = Path.home()
    mapping: dict[str, list[Path]] = {
        "firefox": [home / ".mozilla" / "firefox"],
        "chrome": [home / ".config" / "google-chrome"],
        "chromium": [home / ".config" / "chromium"],
        "edge": [home / ".config" / "microsoft-edge"],
        "brave": [home / ".config" / "BraveSoftware" / "Brave-Browser"],
        "opera": [home / ".config" / "opera"],
        "safari": [],
    }
    roots = mapping.get(browser, [])
    profiles: list[str] = []
    for root in roots:
        if not root.exists():
            continue
        if browser == "firefox":
            for path in root.glob("*.default*"):
                if path.is_dir():
                    profiles.append(str(path))
        else:
            for name in ("Default", "Profile 1", "Profile 2", "Profile 3"):
                path = root / name
                if path.exists() and path.is_dir():
                    profiles.append(str(path))
    # de-duplicate while preserving order
    seen: set[str] = set()
    uniq: list[str] = []
    for profile in profiles:
        if profile in seen:
            continue
        seen.add(profile)
        uniq.append(profile)
    return uniq
