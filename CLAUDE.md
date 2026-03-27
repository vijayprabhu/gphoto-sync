# gphotos-sync Development Guidelines

Last updated: 2026-03-26

## Tech Stack

- **Language**: Python 3.9+
- **Browser automation**: `playwright>=1.40.0` (Chromium — run `playwright install chromium` after pip install)
- **Config format**: YAML via `pyyaml` (`yaml.safe_load` only — never `yaml.load`)
- **Testing**: `pytest`
- **Storage**: Local filesystem only — no database

## Project Structure

```
src/
├── photo_sync.py      # CLI entry point and run orchestration
├── config.py          # SyncConfig dataclass + argparse (--config, --profile, --dest, --date, --start-date, --end-date)
├── config_loader.py   # YAML loading, profile validation, profile selection
├── browser.py         # Playwright session lifecycle (ensure_session, close_session)
├── scraper.py         # Google Photos navigation and Shift+D download per date
└── downloader.py      # Date resolution, browser+scraper orchestration, run_sync()

tests/
├── unit/
│   ├── test_config.py
│   ├── test_config_loader.py
│   ├── test_downloader.py
│   └── test_photo_sync.py
└── integration/       # (empty — manual validation via quickstart.md)
```

## Commands

```bash
python -m pytest                          # run all tests
python -m src.photo_sync --profile <name> # run a single profile sync
python -m src.photo_sync --profile all    # run all profiles sequentially
```

## Code Style

- Python 3.9+ conventions; no f-string `=` (3.8+), no `match` (3.10+), no `ExceptionGroup` (3.11+)
- All path construction via `pathlib.Path` — never string concatenation or `os.path.join`
- `yaml.safe_load()` only — `yaml.load()` without a Loader is banned
- Playwright: synchronous API (`from playwright.sync_api import sync_playwright`) — no `asyncio`
- stdout: run output only — errors always go to stderr

## Key Constraints (from constitution)

- All path fields in YAML config must be absolute — relative paths rejected at validation time
- Config validation runs before any browser is opened
- `--profile all` is sequential — no concurrency
- No new dependencies without a `research.md` Decision entry
- `playwright_state.json` is the session file — never commit it; in `.gitignore`

## Per-Profile File Layout

```
~/.gphotos-sync/
└── config.yml                  # all profiles (--config to override path)

<token_dir>/                    # one per profile, specified in config.yml
└── playwright_state.json       # browser session (auto-created after first login; do not commit)

<destination>/                  # downloaded photos
└── YYYY/MM/DD/filename.jpg     # pathlib.Path — platform-appropriate separator
```

## Recently Completed Features

| Spec | Feature | Key modules changed |
|------|---------|-------------------|
| 001 | Download new photos from Google Photos | `photo_sync.py`, `auth.py`, `client.py`, `downloader.py`, `config.py` |
| 002 | Playwright multi-profile sync (replaces Google Photos API) | `browser.py` (new), `scraper.py` (new), `downloader.py`, `config.py`, `config_loader.py`, `photo_sync.py`; deleted `auth.py`, `client.py` |

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
