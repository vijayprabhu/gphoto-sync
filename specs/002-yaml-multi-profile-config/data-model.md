# Data Model: YAML Multi-Profile Configuration (Playwright Approach)

**Branch**: `002-yaml-multi-profile-config` | **Updated**: 2026-03-25

## Entities

### ConfigFile

The single YAML file that holds all named profiles. Located at `~/.gphotos-sync/config.yml`
by default, or at a user-specified path passed via `--config`.

| Field | Type | Notes |
|---|---|---|
| `path` | absolute path | File system location of the YAML config file |
| `profiles` | map[string → Profile] | All named profiles; keys are profile names (case-sensitive) |

**Constraints**:
- Must be readable as valid YAML (`yaml.safe_load()` only).
- Must contain at least one profile.
- Profile names must be unique within the file (enforced by YAML key uniqueness).
- The reserved name `all` MUST NOT be used as a profile name.
- Empty-key profiles (blank profile name) are rejected at validation time.

**File location resolution**:
1. If `--config <path>` is provided, use that path.
2. Otherwise, use `~/.gphotos-sync/config.yml`.
3. If the file does not exist, exit with a clear error before opening any browser.

---

### Profile

A named set of configuration values for one Google account's sync. Each profile is a
top-level key in the YAML config file.

#### Required Fields

| Field | Type | Validation | Notes |
|---|---|---|---|
| `destination` | absolute path (string) | Must be absolute | Root folder where photos are downloaded for this account |
| `token_dir` | absolute path (string) | Must be absolute | Directory where `playwright_state.json` is stored for this account |

#### Optional Fields

| Field | Type | Default | Notes |
|---|---|---|---|
| `date_offset` | int | `-1` | Days from today used as default date when `--date` is omitted (e.g., `-1` = yesterday) |
| `verbose` | bool | `false` | Per-item progress output |

**Removed fields** (compared to original API-based design):
- `credentials_path` — removed; OAuth client secrets no longer used; Playwright session replaces them.

**Path validation rules**:
- `destination` and `token_dir` MUST be absolute paths.
- Relative paths are rejected at validation time with an error naming the field and profile.
- Validation is performed before any browser is opened (FR-008).

**Identity rule**: Profile names are case-sensitive. `Personal` and `personal` are distinct profiles.

---

### ProfileSettings

The resolved configuration for a single sync run — the merge of profile values and CLI flag overrides.

| Field | Type | Source Priority | Notes |
|---|---|---|---|
| `destination` | path | CLI `--dest` > profile (required) | Root download folder |
| `token_dir` | path | profile (required) | Cannot be overridden via CLI |
| `date` | date \| None | CLI `--date` > None | Single-day target (YYYY-MM-DD); exclusive with start/end |
| `start_date` | date \| None | CLI `--start-date` > None | Range start (inclusive); exclusive with `date` |
| `end_date` | date \| None | CLI `--end-date` > None | Range end (inclusive); exclusive with `date` |
| `date_offset` | int | profile > `-1` | Default offset when `--date` is omitted |
| `verbose` | bool | CLI `-v` > profile > `false` | |

**Effective date resolution** (applied at run time, not at validation):
1. If `--date D` given → single day `D`.
2. If `--start-date S` and `--end-date E` given → iterate each day from `S` to `E` inclusive.
3. If neither given → use `today + date_offset` as a single day.

**Mutually exclusive validation**: `--date` and `--start-date`/`--end-date` on the same
invocation → exit with validation error before opening any browser.

**Precedence**: CLI flags (highest) → profile settings → built-in defaults (lowest).

---

### BrowserSession

Persisted Playwright browser context state stored at `<token_dir>/playwright_state.json`.

| Field | Type | Notes |
|---|---|---|
| `path` | absolute path | `<token_dir>/playwright_state.json` |
| `cookies` | JSON array | Google account auth cookies (serialized by Playwright) |
| `origins` | JSON array | localStorage / sessionStorage snapshot (serialized by Playwright) |

**Lifecycle**:
1. **First run**: File does not exist → launch headed browser → user completes Google login manually → `context.storage_state(path=...)` saves cookies+localStorage → continue with download.
2. **Subsequent runs**: Load file via `browser.new_context(storage_state=...)` → go to `photos.google.com` → if redirected to `accounts.google.com` (session expired) → delete file → re-run step 1.
3. **`--profile all`**: Each profile has its own `playwright_state.json` in its own `token_dir`.

**Security**: Contains Google auth cookies. Must be in `.gitignore` at any directory depth.
Must never be committed to version control.

---

### MultiRunResult

In-memory result of a `--profile all` execution. Not persisted; written to stdout on completion.

| Field | Type | Notes |
|---|---|---|
| `profiles_run` | list[string] | Profile names in the order they were processed |
| `results` | map[string → SyncRun] | Per-profile SyncRun result (or error record) |
| `failed_profiles` | list[string] | Names of profiles that raised an unhandled error |

**Exit code for `--profile all`**: `0` if all profiles succeeded; `1` if one or more failed.

---

### LogFile

The rotating daily log file written to `~/.gphotos-sync/gphotos-sync.log`.

| Field | Type | Notes |
|---|---|---|
| `path` | absolute path | Always `<config_dir>/gphotos-sync.log` where `config_dir` is the parent of the active config file (defaults to `~/.gphotos-sync/`) |
| `rotation` | daily | One file per calendar day; `TimedRotatingFileHandler(when="midnight", backupCount=7)` |
| `retention` | 7 days | Files older than 7 days are deleted automatically by the handler |
| `format` | string | `%(asctime)s [%(levelname)-7s] %(message)s` |

**Constraints**:
- If the log directory is not writable, the tool MUST emit a warning to stderr and continue with console-only output (log write failure is non-fatal).
- `token_dir` absolute paths MUST be replaced with `<token_dir>` in all log records.
- `playwright_state.json` full paths MUST be replaced with `<session_file>` in all log records.

---

### LogEntry

A single structured line written to the log file and/or console per event.

| Field | Type | Notes |
|---|---|---|
| `timestamp` | ISO 8601 datetime | `%(asctime)s` — e.g., `2026-03-26 08:00:00,123` |
| `level` | string | One of: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `message` | string | Human-readable event description; sensitive paths already redacted |

**Log level routing**:

| Level | File handler | stderr handler | stdout handler |
|---|---|---|---|
| DEBUG | ✅ (only when `--verbose`) | ❌ | ❌ |
| INFO | ✅ | ❌ | ✅ |
| WARNING | ✅ | ✅ | ❌ |
| ERROR | ✅ | ✅ | ❌ |

**Mandatory log events** (NFR-LOG-005):

| Event | Level | Message template |
|---|---|---|
| Sync run start | INFO | `[{profile}] Sync started: {date}` |
| Sync run complete | INFO | `[{profile}] Sync complete: downloaded={n}, failed={n}` |
| Per-photo download failure | ERROR | `[{profile}] FAILED: {filename} — {reason}` |
| Session not found | INFO | `[{profile}] No saved session — opening browser for login` |
| Session expired | WARNING | `[{profile}] Session expired — re-authenticating` |
| Login success | INFO | `[{profile}] Login successful, session saved` |
| Chromium install triggered | INFO | `Chromium not found — installing via playwright install chromium` |
| Log file not writable | WARNING | `Log file unavailable: {reason} — continuing with console output only` |

---

## State Transitions

### Profile Selection Lifecycle

```
CLI invoked
  │
  ├─ --profile <name> → load named profile → validate → run
  ├─ --profile all    → load all profiles  → iterate with try/except per profile
  └─ (no --profile)   → look for "default" profile
                           ├─ found → load "default" → validate → run
                           └─ missing → EXIT(1) with list of available profile names
```

### Browser Session Lifecycle

```
run_sync(profile) called
  │
  ├─ playwright_state.json exists?
  │    ├─ YES → load_context(state_file)
  │    │          → goto photos.google.com
  │    │          → redirected to accounts.google.com?
  │    │               ├─ YES (expired) → delete state file → headed login flow
  │    │               └─ NO  (valid)   → proceed to date navigation
  │    └─ NO  → headed login flow
  │                → user completes login in browser
  │                → save storage_state to playwright_state.json
  │                → proceed to date navigation
  │
  └─ for each date in [date | start_date..end_date]:
       → navigate with #date_range search
       → scroll to reveal all photos
       → for each photo: open detail → Shift+D → save to YYYY/MM/DD/

```

### `--profile all` Error Isolation

```
For each profile (in file order):
  try:
    validate profile → resolve settings → run_sync(profile)
  except:
    append error to failed_profiles → continue to next profile

After all profiles:
  print summary for each profile
  print failed_profiles list (if any)
  exit(0) if failed_profiles is empty else exit(1)
```

---

## File Layout on Disk

```
~/.gphotos-sync/
├── config.yml                    # Single YAML config file with all profiles
├── gphotos-sync.log              # Current day's log file (auto-created)
└── gphotos-sync.log.2026-03-25  # Prior day's rotated log (up to 7 retained)

<token_dir>/                      # Specified per-profile; one per Google account
└── playwright_state.json         # Browser session state (cookies + localStorage)
                                  # Auto-created after first login. Never modify.

<destination>/                    # Specified per-profile; one per Google account
└── YYYY/
    └── MM/
        └── DD/
            └── filename.jpg      # Photos organised by capture date
```

**Example multi-account layout**:

```
~/.gphotos-sync/
├── config.yml
├── personal/
│   └── playwright_state.json
└── work/
    └── playwright_state.json

C:/Users/User/photos/
├── personal/
│   └── 2026/03/24/IMG_0001.jpg
└── work/
    └── 2026/03/24/IMG_0002.jpg
```

**Removed files** (compared to original API-based design):
- `credentials.json` — no longer used; OAuth client secrets not required.
- `token.json` — replaced by `playwright_state.json`.
- `synced_ids.json` — removed; no deduplication state is maintained.
