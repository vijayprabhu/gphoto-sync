# CLI Contract: gphotos-sync (v2 — YAML Multi-Profile + Playwright)

**Branch**: `002-yaml-multi-profile-config` | **Updated**: 2026-03-25

> **Breaking changes from feature 001**: `--config-dir` removed. `--date-from`/`--date-to` replaced
> by `--date`/`--start-date`/`--end-date`. `--max-backoff` and `--lookback-pages` removed (API no longer used).

## Invocation

```
python -m src.photo_sync [OPTIONS]
```

---

## Arguments & Options

| Flag | Short | Type | Default | Description |
|---|---|---|---|---|
| `--config` | | path | `~/.gphotos-sync/config.yml` | Path to the YAML configuration file |
| `--profile` | `-p` | string | `default` | Profile name; use `all` to run every profile sequentially |
| `--dest` | `-d` | path | (from profile) | Override the profile's `destination` folder for this run |
| `--date` | | date (YYYY-MM-DD) | today + `date_offset` | Single capture date to download; mutually exclusive with `--start-date`/`--end-date` |
| `--start-date` | | date (YYYY-MM-DD) | — | Range start (inclusive); must be paired with `--end-date` |
| `--end-date` | | date (YYYY-MM-DD) | — | Range end (inclusive); must be paired with `--start-date` |
| `--verbose` | `-v` | flag | (from profile or false) | Print per-item progress |
| `--help` | `-h` | flag | | Show help and exit |

**Removed flags** (from feature 001 / original 002 design):
- `--config-dir` — replaced by `--config` + `--profile`
- `--date-from` / `--date-to` — replaced by `--date` and `--start-date`/`--end-date`
- `--max-backoff` — API no longer used
- `--lookback-pages` — API no longer used
- `--dry-run` — removed; always-re-download makes it less meaningful; may be re-added in a future feature

**Mutual exclusion**: `--date` cannot be combined with `--start-date` or `--end-date` → exit code 2.

---

## Profile Selection Behavior

| Invocation | Behavior |
|---|---|
| `--profile personal` | Load and run the `personal` profile |
| `--profile all` | Run every profile in config file order; continue on per-profile failure |
| `--profile default` | Explicit: same as using the `default` profile |
| *(no `--profile`)* | Implicitly use `default` profile; error if `default` not found |

---

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | Success — all profiles completed (per-item failures appear in summary, not fatal) |
| `1` | Fatal error — config file missing/invalid, required field absent, browser session failure, destination not writable, or one or more profiles failed in `--profile all` |
| `2` | Invalid arguments — bad date format, `--date` + `--start-date`/`--end-date` combined, `--start-date` after `--end-date`, unrecognized flag |

---

## Standard Output

### Single-profile run (normal)

```
gphotos-sync [personal]: 2026-03-24
  Downloaded: 44
  Failed:     0
  Saved to:   C:/Users/User/photos/personal/2026/03/24/
```

### Single-profile run with `--verbose`

```
gphotos-sync [personal]: 2026-03-24
  + 2026/03/24/IMG_0001.jpg
  + 2026/03/24/IMG_0002.jpg
  x 2026/03/24/IMG_0003.jpg (failed: download timeout)
  ...
  Downloaded: 43
  Failed:     1
  Saved to:   C:/Users/User/photos/personal/2026/03/24/
```

### Date-range run (`--start-date` / `--end-date`)

```
gphotos-sync [personal]: 2026-03-20 → 2026-03-24
  2026-03-20: Downloaded 12
  2026-03-21: Downloaded  8
  2026-03-22: Downloaded 31
  2026-03-23: Downloaded  0
  2026-03-24: Downloaded 19
  Total downloaded: 70
  Total failed:      0
  Saved to:   C:/Users/User/photos/personal/
```

### `--profile all` run

```
=== Profile: personal ===
gphotos-sync [personal]: 2026-03-24
  Downloaded: 44
  Failed:     0
  Saved to:   C:/Users/User/photos/personal/2026/03/24/

=== Profile: work ===
gphotos-sync [work]: 2026-03-24
  Downloaded: 12
  Failed:     0
  Saved to:   C:/Users/User/photos/work/2026/03/24/

=== Profile: default ===
ERROR: Browser session expired for profile "default". Re-authentication required.

=== Summary: --profile all ===
  Completed: personal, work
  Failed:    default
```

### First-time login / session expiry (stderr)

```
[gphotos-sync] No saved session found for profile "personal".
[gphotos-sync] Opening browser for Google login. Complete sign-in, then return here.
```

```
[gphotos-sync] Session expired for profile "personal". Re-opening browser for re-authentication.
```

---

## Standard Error

```
ERROR: Config file not found: C:/Users/User/.gphotos-sync/config.yml
ERROR: Profile "personal" is missing required field: destination
ERROR: Profile "personal": field "token_dir" must be an absolute path, got: ./personal
ERROR: Profile "staging" not found. Available profiles: personal, work, default
ERROR: No "default" profile found. Available profiles: personal, work
ERROR: Profile name "all" is reserved and cannot be used
ERROR: Cannot use --date together with --start-date/--end-date
ERROR: --start-date must be on or before --end-date
```

Per-item download failures (non-fatal) go to stderr:

```
FAILED: IMG_0004.jpg — download timeout
```

---

## Configuration Files

### Config file (`~/.gphotos-sync/config.yml` or `--config <path>`)

See [config-schema.md](config-schema.md) for full format.

### Per-profile session file (in each profile's `token_dir`)

| File | Purpose | Provided by |
|---|---|---|
| `playwright_state.json` | Browser session state (cookies + localStorage) | Created automatically after first Google login per profile |

**Removed files** (compared to original design): `credentials.json`, `token.json`, `synced_ids.json`.

---

## Common Usage Patterns

```bash
# Download yesterday's photos (date_offset: -1 default)
python -m src.photo_sync --profile personal

# Download a specific day
python -m src.photo_sync --profile personal --date 2026-03-24

# Re-run a missed date range (catch-up)
python -m src.photo_sync --profile personal --start-date 2026-03-20 --end-date 2026-03-24

# Run all profiles sequentially
python -m src.photo_sync --profile all

# Use a non-default config file
python -m src.photo_sync --config C:/shared/gphotos.yml --profile work

# Verbose output
python -m src.photo_sync --profile personal --verbose
```

---

## Logging Behaviour

### Log file

| Property | Value |
|---|---|
| Path | `~/.gphotos-sync/gphotos-sync.log` (same directory as default config) |
| Rotation | Daily at midnight — one file per calendar day |
| Retention | Current day + 6 prior days (7 total); older files deleted automatically |
| Format | `2026-03-26 08:00:00,123 [INFO   ] [personal] Sync started: 2026-03-25` |

### Level routing

| Level | Appears in log file | Appears on stderr | Appears on stdout |
|---|---|---|---|
| DEBUG | Yes (only with `--verbose`) | No | No |
| INFO | Yes | No | Yes (run summaries) |
| WARNING | Yes | Yes | No |
| ERROR | Yes | Yes | No |

### Redaction

`token_dir` absolute paths and `playwright_state.json` full file paths are replaced with
`<token_dir>` and `<session_file>` respectively in **all log output** (both file and console).

```
# Before redaction (never emitted)
Session saved to C:\Users\Alice\.gphotos-sync\sessions\personal\playwright_state.json

# After redaction (what is emitted)
[personal] Login successful, session saved to <session_file>
```

### Log write failure

If `~/.gphotos-sync/` is not writable, the tool emits a single warning to stderr and continues
with console-only output. A log file failure never aborts a sync run.

```
WARNING: Log file unavailable: [Errno 13] Permission denied — continuing with console output only
```

---

## Download Folder Structure

Photos saved in three-level hierarchy under profile's `destination`, organised by **capture date**:

```
<destination>/
└── YYYY/
    └── MM/
        └── DD/
            └── filename.jpg
```

Example: photo taken 2026-03-24 → `<destination>/2026/03/24/IMG_0001.jpg`

Paths use platform-appropriate separator (`\` on Windows, `/` on Unix/macOS) via `pathlib.Path`.
