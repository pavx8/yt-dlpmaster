# yt-dlpMaster

Desktop GUI for `yt-dlp` built with Python and PySide6.

English: `README.md` | [Русский](README.ru.md)

## Key Features
| Status | Feature |
| --- | --- |
| ✅ | Desktop GUI built with `Python + PySide6` |
| ✅ | Video URL input, output folder selection, and basic download presets |
| ✅ | URL analysis before download: title, duration, preview, preset refresh |
| ✅ | Background downloads with progress, status, and log output |
| ✅ | Proxy support (`socks4`, `socks5`, `socks5h`, `http`, `https`) |
| ✅ | Cookies support from browser profiles and `cookies.txt` |
| ✅ | Cookies testing from the UI |
| ✅ | Optional `ffmpeg` transcoding |
| ✅ | Audio extraction and conversion to `mp3` / `opus` / `aac` |
| ✅ | `SponsorBlock` integration |
| ✅ | Runtime switching between bundled and system components |
| ✅ | Settings for language, theme, and window behavior |
| ✅ | System tray integration and minimize-on-close |
| ✅ | Built-in updater for `yt-dlp`, `yt-dlp-ejs`, `ffmpeg`, and `certifi` |
| ✅ | Basic two-language localization: `ru_RU` / `en_US` |
| ⬜ | Advanced localization via WebLate |
| ⬜ | Download queue and multiple URLs at once |
| ⬜ | Playlist downloads |
| ⬜ | Pause, resume, cancel, and retry controls |
| ⬜ | Download history and quick file actions |
| ⬜ | Log export and richer error diagnostics |
| ⬜ | Auto-update for the app itself |
| ⬜ | Packaged releases (`AppImage`, `exe`, portable bundle`) |

## Roadmap
| Area | Item | Status |
| --- | --- | --- |
| Foundation | Basic GUI for `yt-dlp` | ✅ |
| Foundation | Link analysis and preview | ✅ |
| Foundation | Background downloads and logging | ✅ |
| Foundation | Settings, localization, tray, and component updater | ✅ |
| Reliability | Unit tests for `settings`, `cookies`, `proxy`, and `format fallback` | ⬜ |
| Reliability | Smoke/integration tests for analysis and downloads | ⬜ |
| Reliability | CI for `lint`, tests, and translation builds | ⬜ |
| Reliability | More detailed errors for auth/network/DRM/ffmpeg | ⬜ |
| Downloads UX | Task queue | ⬜ |
| Downloads UX | Multiple URLs and playlist support | ⬜ |
| Downloads UX | Pause/Resume/Cancel/Retry | ⬜ |
| Downloads UX | Download history with "open file" and "open folder" actions | ⬜ |
| Formats | Manual selection of available formats | ⬜ |
| Formats | Display container, codecs, and estimated size before download | ⬜ |
| Formats | Options for subtitles, metadata, thumbnail, and naming templates | ⬜ |
| Release | Linux/Windows release packaging | ⬜ |
| Release | App self-update | ⬜ |
| Release | More detailed user documentation | ⬜ |

## Requirements
- Python `>=3.10,<3.15`
- Poetry
- `ffmpeg` in `PATH` or bundled binaries in the project

## Quick Start
```bash
poetry install
poetry run yt-dlpmaster
```

Run with explicit UI language:
```bash
poetry run yt-dlpmaster --lang ru_RU
```

## Localization Workflow
- Translation sources are stored in `app/i18n/*.ts`.
- Binary translation files are `app/i18n/*.qm`.
- On app start, `.qm` files are built automatically if missing or older than `.ts`.

Manual commands:
```bash
./scripts/build_translations.sh
./scripts/update_translations.sh
```

## Project Layout
- `app/cli.py` - CLI entrypoint (`yt-dlpmaster`)
- `app/ui/` - Qt UI layer
- `app/core/` - download, ffmpeg, settings, CA helpers
- `app/i18n/` - translations (`.ts` / `.qm`)
- `scripts/` - translation utility scripts

## Notes
- Settings are stored in portable mode in `settings.ini` at the project root.
- The app prefers bundled binaries/libraries when enabled in settings.
- `ffmpeg` discovery checks local bundled paths first, then system `PATH`.
