# yt-dlpMaster

Desktop GUI for `yt-dlp` built with Python and PySide6.

Русская версия: [README.ru.md](README.ru.md)

## Features
- Video URL input
- Output folder selection
- Download format presets
- Proxy support (`socks4`, `socks5`, `socks5h`, `http`, `https`)
- Cookies support (browser profile or cookies.txt file)
- UI language selection
- Optional compatibility transcoding (H.264/AAC for video, MP3 for audio)
- Download progress and status log
- Runtime switching between bundled/system components

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
