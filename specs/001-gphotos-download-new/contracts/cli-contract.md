# CLI Contract: gphotos-sync

**Branch**: `001-gphotos-download-new` | **Date**: 2026-03-22

## Invocation

```
python -m src.photo_sync [OPTIONS]
```

Or (after packaging):

```
gphotos-sync [OPTIONS]
```

---

## Arguments & Options

| Flag | Short | Type | Default | Description |
|---|---|---|---|---|
| `--dest` | `-d` | path | (required) | Local destination root folder for downloads |
| `--config-dir` | `-c` | path | `~/.gphotos-sync/` | Config directory containing credentials and sync state |
| `--date-from` | | date (YYYY-MM-DD) | yesterday (local TZ) | Start of target capture-date range (inclusive) |
| `--date-to` | | date (YYYY-MM-DD) | today (local TZ) | End of target capture-date range (inclusive) |
| `--max-backoff` | | int (seconds) | 300 | Maximum total wait time for exponential backoff retries |
| `--lookback-pages` | | int | 5 | Pages of `mediaItems.list` to scan for upload-date proxy |
| `--dry-run` | | flag | false | List what would be downloaded without downloading |
| `--verbose` | `-v` | flag | false | Print per-photo progress in addition to the summary |
| `--help` | `-h` | flag | | Show help and exit |

---

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | Success — run completed (even if some items failed; failures are reported in summary) |
| `1` | Fatal error — auth failure, destination not writable, config not found, or unrecoverable API error |
| `2` | Invalid arguments — bad date format, missing required flag |

---

## Standard Output

### Normal run (summary line per run)

```
gphotos-sync: 2026-03-21 → 2026-03-22
  Found:      47 photos
  Downloaded: 44
  Skipped:    3 (already exist)
  Failed:     0
  Saved to:   /home/user/photos/
```

### With `--verbose`

Each photo prints as it is processed:

```
  ✓ 2026-03-22/IMG_0001.jpg
  ✓ 2026-03-22/IMG_0002.jpg
  - 2026-03-22/IMG_0003.jpg (skipped: already exists)
  ✗ 2026-03-22/IMG_0004.jpg (failed: connection timeout)
  ...
```

### With `--dry-run`

```
gphotos-sync: DRY RUN — 2026-03-21 → 2026-03-22
  Would download: 44 photos
  Would skip:     3 (already exist)
  No files written.
```

---

## Standard Error

Errors that prevent the run from completing are written to stderr:

```
ERROR: Destination directory does not exist: /path/to/dest
ERROR: credentials.json not found in config dir: /home/user/.gphotos-sync/
ERROR: Authentication failed. Re-run to complete browser authorization.
```

---

## Configuration Files (not CLI args)

These files must be present in `--config-dir` before first run:

| File | Purpose | Provided by |
|---|---|---|
| `credentials.json` | OAuth2 client secrets | User (downloaded from Google Cloud Console) |
| `token.json` | OAuth2 access/refresh tokens | Created automatically after first auth |
| `synced_ids.json` | Local sync state | Created automatically on first run |

---

## Multi-Account Usage Pattern

```bash
# Account 1
gphotos-sync --dest ~/photos/alice --config-dir ~/.gphotos-sync/alice

# Account 2
gphotos-sync --dest ~/photos/bob --config-dir ~/.gphotos-sync/bob
```

Each config directory is independent with its own `credentials.json`, `token.json`, and `synced_ids.json`.

---

## Download Folder Structure

Photos are saved in a three-level hierarchy under `--dest`:

```
<dest>/
└── YYYY/
    └── MM/
        └── DD/
            └── filename.jpg
```

Example: a photo taken on 2026-03-22 →  `<dest>/2026/03/22/IMG_0001.jpg`

Folder paths are constructed using the platform-appropriate separator (`\` on Windows, `/` on Unix/macOS).
