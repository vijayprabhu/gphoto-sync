# gphotos-sync Architecture

> Stable reference for the current module design. Update this when a feature changes a
> module's stated responsibility, adds a new module, or changes the data flow.
> Last updated: 2026-03-22 (after feature 002-yaml-multi-profile-config)

---

## Module Map

| Module | Single Responsibility | Can import | Cannot import |
|---|---|---|---|
| `photo_sync.py` | CLI entry point, argument dispatch, output formatting, run orchestration | all src modules | nothing outside src |
| `config.py` | CLI argument parsing (`argparse`), `SyncConfig` dataclass construction | `config_loader` | `auth`, `client`, `downloader` |
| `config_loader.py` | YAML file loading, profile validation, profile selection | stdlib only | no other src modules |
| `auth.py` | OAuth2 credential load/refresh/save | stdlib, `google-auth` libs | no other src modules |
| `client.py` | Google Photos API wrapper (search, list, pagination, retry) | `google-api-python-client`, `google-api-core` | no other src modules |
| `downloader.py` | Sync state persistence, per-item download, `run_sync` orchestration | `client`, `config`, `requests` | `auth`, `config_loader`, `photo_sync` |

**Rule**: The dependency arrows only flow one way — `photo_sync` → everything else.
No circular imports. `config_loader` and `auth` have no src-internal imports.

---

## Data Flow

```
CLI args (sys.argv)
    │
    ▼
photo_sync.main()
    │
    ├── pre-parse --config / --profile
    │       │
    │       └── [profile == "all"] ──► run_all_profiles()
    │                                       │ (iterates profiles)
    │                                       └── (same flow below, per profile)
    │
    ▼
config.parse_args()
    │
    ├── config_loader.load_config(config_path)     ← reads config.yml
    ├── config_loader.get_profile(data, name)      ← validates required fields + abs paths
    ├── parser.set_defaults(**optional_profile_fields)
    └── parser.parse_args(argv)  ← CLI flags override profile defaults
            │
            └── returns SyncConfig(credentials_path, token_dir, destination, ...)
                    │
                    ▼
            auth.authenticate(credentials_path, token_dir)
                    │
                    ├── reads <token_dir>/token.json  (refresh if expired)
                    ├── reads <credentials_path>       (browser flow if no token)
                    └── writes <token_dir>/token.json  (JSON, never pickle)
                            │
                            ▼
                    GooglePhotosClient(credentials)
                            │
                            ├── search_by_capture_date(date_from, date_to)
                            │       └── mediaItems.search + dateFilter + pagination
                            ├── list_recent_items(lookback_pages)
                            │       └── mediaItems.list + pagination (upload-date proxy)
                            └── get_items_for_range(...)
                                    └── merges + deduplicates both result sets by id
                                            │
                                            ▼
                            downloader.run_sync(config, client, state)
                                    │
                                    ├── for each item:
                                    │       ├── skip if id in synced_ids.json
                                    │       ├── skip if file exists at dest/YYYY/MM/DD/
                                    │       ├── download via requests.get(baseUrl + "=d")
                                    │       └── write synced_ids.json after each success
                                    └── returns SyncRun(found, downloaded, skipped, failed)
                                            │
                                            ▼
                            photo_sync.print_summary(run, config)
                                    ├── stdout: summary table + verbose lines
                                    └── stderr: per-item failures
```

---

## Key Data Structures

### `SyncConfig` (`src/config.py`)
Resolved configuration for one sync run. Built by `parse_args()`.

```python
credentials_path: Path   # absolute — OAuth client secrets file
token_dir: Path          # absolute — where token.json and synced_ids.json live
destination: Path        # absolute — local root for downloaded photos
date_from: date          # capture-date range start (inclusive)
date_to: date            # capture-date range end (inclusive)
max_backoff_seconds: int # retry deadline (default 300)
lookback_pages: int      # recent-list pages for upload-date proxy (default 5)
dry_run: bool
verbose: bool
```

### `SyncState` (`src/downloader.py`)
Persisted to `<token_dir>/synced_ids.json`. Loaded at run start, updated after each download.

```python
synced_ids: set[str]   # item IDs successfully downloaded
last_run: str | None   # ISO timestamp of last successful run
```

### `SyncRun` (`src/downloader.py`)
In-memory record of one run. Returned by `run_sync()`, consumed by `print_summary()`.

```python
started_at: datetime
date_from: date
date_to: date
found: int
downloaded: int
skipped: int
failed: list[{id, filename, error}]
```

### `MediaItem` (Google Photos API response)
Key fields used by the tool:

```python
id: str                              # stable unique identifier (used in synced_ids)
filename: str                        # saved as-is on disk
baseUrl: str                         # short-lived download URL; append "=d" for original
mediaMetadata.creationTime: str      # RFC3339 — used for YYYY/MM/DD subfolder naming
```

---

## CLI Contract Summary

```
python -m src.photo_sync [--config PATH] [--profile NAME|all] [OPTIONS]

--config    Path to config.yml          default: ~/.gphotos-sync/config.yml
--profile   Profile name or "all"       default: "default"
--dest      Override profile destination
--date-from / --date-to  YYYY-MM-DD    defaults: yesterday / today
--max-backoff  seconds                  default: 300
--lookback-pages  N                     default: 5
--dry-run   Preview without writing
--verbose   Per-item progress lines

Exit codes:  0 = success   1 = fatal error   2 = invalid args
stdout:      run summary + verbose lines
stderr:      all errors, validation failures, per-item failures
```

Full contract: [`specs/002-yaml-multi-profile-config/contracts/cli-contract.md`](specs/002-yaml-multi-profile-config/contracts/cli-contract.md)

---

## Design Decisions (permanent record)

These are decisions that future features must respect or explicitly supersede.

| Decision | Rationale | Spec |
|---|---|---|
| `google-api-python-client` over `google.apps.photoslibrary_v1` | Standard library; non-standard import path in the alternative caused import failures | 001 research.md D2 |
| JSON token storage (`to_json()`) — pickle banned | Security: pickle allows arbitrary code execution on load | 001 research.md D4 |
| Upload-date proxy: `mediaItems.search` + `mediaItems.list` + `synced_ids.json` | Google Photos API has no `uploadTime` field; this is the canonical workaround | 001 research.md D1 |
| `pathlib.Path` for all path construction | Platform-appropriate separators on Windows (`\`) and Unix (`/`) | 001 research.md D6 |
| `pyyaml` (`safe_load`) for YAML parsing | Read-only use case; `ruamel.yaml` only warranted for round-trip writes | 002 research.md D1 |
| Profile names as top-level YAML keys (no `profiles:` wrapper) | Mirrors AWS CLI and dbt `profiles.yml`; less indentation; more scannable | 002 research.md D2 |
| `argparse.set_defaults()` for profile→CLI precedence | Zero extra dependencies; natural two-layer override with no manual merge logic | 002 research.md D3 |
| `--profile all` is sequential, not concurrent | Python 3.9 target; `ExceptionGroup` requires 3.11; simplicity over throughput | 002 research.md D4 |

---

## Modules Under Active Change

> Update this table when a feature branch is opened that modifies a shared module.
> Remove the row when the branch is merged.

| Module | Feature branch | Engineer | Notes |
|---|---|---|---|
| *(none currently)* | | | |

---

## What Deliberately Does Not Exist Here

- **No database** — all state is local filesystem (`synced_ids.json`, `token.json`)
- **No server / daemon mode** — single invocation, exits when done
- **No concurrent profile execution** — `--profile all` is sequential by design
- **No photo upload** — read-only access to Google Photos (`photoslibrary.readonly` scope)
- **No relative path support** — all config paths must be absolute; rejected at validation time
