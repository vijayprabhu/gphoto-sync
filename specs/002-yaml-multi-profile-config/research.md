# Research: YAML Multi-Profile Configuration (Playwright Approach)

**Branch**: `002-yaml-multi-profile-config` | **Updated**: 2026-03-25

---

## Decision 1: YAML Parsing Library

**Decision**: Use `PyYAML` (`pyyaml`) for reading the configuration file.

**Rationale**: `PyYAML` is the standard library for read-only YAML parsing in Python. `ruamel.yaml`
is only warranted when the tool must round-trip YAML while preserving comments and formatting.
This tool reads the config file but never modifies it, so `PyYAML` is simpler, has wider
documentation, and is already a common transitive dependency.

**Alternatives considered**:
- `ruamel.yaml` → **Rejected**: Only needed for round-trip writes; unnecessary complexity.
- `tomllib` (TOML) → **Rejected**: Spec explicitly calls for YAML format.
- `configparser` (INI) → **Rejected**: Does not support nested structures required for per-profile settings.

---

## Decision 2: YAML Config File Schema

**Decision**: Profile names are top-level keys in the config file. No `profiles:` wrapper key.
`credentials_path` is removed (Playwright replaces OAuth). Required fields are now `destination`
and `token_dir` only.

**Rationale**: Mirrors AWS CLI profile pattern (`~/.aws/credentials`) and dbt's `profiles.yml`.
Profile names as top-level keys are immediately visible and scannable.

**Updated schema**:
```yaml
personal:
  destination: C:/Users/User/photos/personal
  token_dir: C:/Users/User/.gphotos-sync/personal
  # Optional fields:
  date_offset: -1       # integer days from today; -1 = yesterday (default for --date)
  verbose: false

work:
  destination: C:/Users/User/photos/work
  token_dir: C:/Users/User/.gphotos-sync/work

default:
  destination: C:/Users/User/photos/default
  token_dir: C:/Users/User/.gphotos-sync/default
```

**Reserved profile name**: `all` is reserved and must be rejected as a profile name.

**Alternatives considered**:
- `profiles:` wrapper key → **Rejected**: Extra indentation, less idiomatic.
- List of objects with a `name:` field → **Rejected**: More verbose, harder to look up by name.

---

## Decision 3: CLI Override Precedence

**Decision**: Use vanilla `argparse` with `set_defaults()` to layer profile settings under CLI flags.

**Rationale**: Precedence model: (1) CLI flags (highest), (2) profile settings, (3) built-in defaults (lowest).
`parser.set_defaults(**profile_optional_settings)` before `parse_args()` achieves this without extra libraries.

**Alternatives considered**:
- `ConfigArgParse` library → **Not selected**: Adds a dependency; `set_defaults()` achieves the same result.
- Manual dict merge after `parse_args()` → **Rejected**: Error-prone.

---

## Decision 4: `--profile all` Error Isolation

**Decision**: try/except per profile iteration with error aggregation; continue to next profile on
failure; report all failures at end.

**Rationale**: Python 3.9 compatibility rules out `ExceptionGroup` (3.11+). Manual error collection
list is the standard, robust pattern.

**Exit code for `--profile all`**: Exit `0` if all profiles succeeded; exit `1` if one or more failed.

**Alternatives considered**:
- Stop on first failure → **Rejected**: FR-005a requires continuing on failure.
- `ExceptionGroup` → **Not available**: Python 3.9+ target.

---

## Decision 5: Config File Location

**Decision**: Default config path is `~/.gphotos-sync/config.yml`. Overridable via `--config <path>`.
`--config-dir` flag is removed entirely.

---

## Decision 6: Download Mechanism — Playwright Browser Automation

**Decision**: Replace the Google Photos Library API with Playwright Python browser automation.

**Rationale**: Google Photos Library API (2024/2025 policy) restricts access to media items
created by the registering app only. Phone-uploaded photos — the primary use case — are
inaccessible via any Library API scope. Google's own documentation states: *"You can now only
list, search, and retrieve albums and media items that were created by your app."* Playwright
automates the full Google Photos web UI as a logged-in user, bypassing all API scope restrictions.

**Alternatives considered**:
- `photoslibrary.readonly` scope: Insufficient — restricted to app-created items only.
- Google Photos Picker API: Requires per-session interactive user selection (72 h window); unsuitable for automated cron-based sync.
- Google Drive API: Would require enabling Google Photos → Drive sync (deprecated/separated since 2019); not reliable across all accounts.

---

## Decision 7: New Dependency — `playwright` (Python)

**Decision**: Add `playwright` (`playwright>=1.40.0`) as a required project dependency.
Browser binaries installed separately via `playwright install chromium`.

**Rationale**: Playwright is the actively-maintained Microsoft browser automation library for Python.
It provides built-in storage state serialization, async and sync APIs, and reliable download
interception via `expect_download()`.

**Alternatives considered**:
- `selenium`: No built-in storage state API; requires external ChromeDriver; more brittle.
- `pyppeteer`: Python Puppeteer port; unmaintained since 2022.
- `requests` + direct URL extraction: Requires valid session cookies per-request; `lh3.googleusercontent.com`
  URLs are session-scoped (~60 min TTL); not self-sufficient without a live browser session.

---

## Decision 8: Date Navigation — `#date_range` Search Query

**Decision**: Use the Google Photos search bar with the `#date_range:YYYYMMDD-YYYYMMDD` query
to navigate to photos by capture date.

**Rationale**: Google Photos has no stable direct URL for capture-date filtering. The SPA does not
expose date parameters in the URL path. The `#date_range` token is community-validated and
confirmed working as of 2025. For `--date D`, both bounds equal `D`. For `--start-date S` /
`--end-date E`, the bounds span the full range (one search call per day in the range).

**Implementation pattern**:
```python
date_query = f"#date_range:{yyyymmdd}-{yyyymmdd}"
await page.keyboard.press("/")           # focus search bar
await page.keyboard.type(date_query)
await page.keyboard.press("Enter")
await page.wait_for_load_state("networkidle")
```

---

## Decision 9: Individual Photo Download — `Shift+D` + `expect_download()`

**Decision**: Open each photo in detail view, press `Shift+D`, and intercept the download with
Playwright's `expect_download()` context manager. Save file to computed `destination/YYYY/MM/DD/`
using `download.save_as()`.

**Rationale**: `Shift+D` downloads the original full-resolution file (not a ZIP) for a single photo.
`expect_download()` intercepts it before it reaches the default downloads folder, allowing the script
to redirect to the correct YYYY/MM/DD directory. More stable than `lh3.googleusercontent.com` URL
parameter manipulation (`=s0-d`), which has changed format historically.

**Note on photo enumeration**: Google Photos uses a virtualized scroll list — photos off screen are
not in the DOM. The scraper must scroll the grid to reveal all items before clicking into detail view.

---

## Decision 10: Session Management — `storage_state()` + Headed First Login

**Decision**: Persist Playwright browser context as `playwright_state.json` in each profile's
`token_dir`. First-time login runs headed (visible browser, `headless=False`). All subsequent
runs load saved state and run headless.

**Rationale**: Google blocks headless Chromium during the login flow (detects `navigator.webdriver`
automation flags). After saving state from a headed login, headless runs with loaded cookies are
accepted by Google Photos without re-challenge.

**Session persistence pattern**:
```python
# Save after login
await context.storage_state(path=str(token_dir / "playwright_state.json"))

# Load on next run
context = await browser.new_context(
    storage_state=str(token_dir / "playwright_state.json")
)
```

**Session expiry detection**: After `page.goto("https://photos.google.com")`, check if
`"accounts.google.com" in page.url`. If so: delete stale state file, re-launch headed for
re-auth, save new state, then continue.

**Anti-detection flags for headed login**:
```python
browser = await p.chromium.launch(
    headless=False,
    args=["--disable-blink-features=AutomationControlled"],
)
context = await browser.new_context(
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) ..."
)
```

**Security**: `playwright_state.json` contains auth cookies. Added to `.gitignore` at any directory depth.

---

## Decision 11: No Deduplication State (`synced_ids.json` removed)

**Decision**: Remove all `synced_ids.json` logic. Every run re-downloads all photos in the
specified date/range, overwriting existing local files.

**Rationale**: User explicitly chose always-re-download behavior (clarification Q5, Option A).
For date-bounded daily runs (typically tens to hundreds of photos per day), re-downloading is
acceptable. Tracking stable photo IDs via Playwright would require opening each photo individually
to extract its ID — significant latency with no benefit for the intended daily-cron use pattern.

**Constitution deviation**: Violates Principle III (Idempotent Sync). Justified in `plan.md`
Complexity Tracking.

---

## Decision 13: Logging Library — stdlib `logging` with `TimedRotatingFileHandler`

**Decision**: Use Python's stdlib `logging` module exclusively. No third-party logging library.

**Rationale**: `logging.handlers.TimedRotatingFileHandler` natively supports daily rotation with a
configurable backup count. `logging.StreamHandler` covers both stdout and stderr simultaneously.
A custom `logging.Filter` subclass handles path redaction. All requirements (NFR-LOG-001 through
NFR-LOG-005) are satisfiable with zero new dependencies.

**Alternatives considered**:
- `loguru` → **Rejected**: Third-party; requires a `research.md` decision and `requirements.txt` entry; adds no capability the stdlib doesn't cover for this use case.
- `structlog` → **Rejected**: Structured JSON logging unnecessary for a CLI sync tool; plain text log is sufficient.

---

## Decision 14: Log Redaction — Custom `logging.Filter` Subclass

**Decision**: Implement `RedactingFilter(logging.Filter)` that intercepts each `LogRecord` before
emission and replaces `token_dir` absolute path strings with `<token_dir>` and
`playwright_state.json` full paths with `<session_file>`.

**Rationale**: Attaching a `Filter` to all handlers in one place ensures redaction applies to both
the file handler and the stream handlers without duplicating logic. The filter receives the set of
registered `token_dir` values at construction time; it performs a simple `str.replace()` on
`record.msg` and `record.args` before formatting.

**Alternatives considered**:
- Redact at call site in each module → **Rejected**: Fragile; easy to miss; violates single-responsibility for caller modules.
- Custom `logging.Formatter` subclass → **Rejected**: Formatters run after `Filter`; redaction in a `Filter` acts earlier, closer to the source record, and is simpler to test.

---

## Decision 15: New Module — `src/logger.py`

**Decision**: All logging setup lives in a new `src/logger.py` module exposing a single public
function: `setup_logging(verbose: bool, log_dir: Path, token_dirs: list[Path]) -> logging.Logger`.

**Rationale**: Principle I mandates new concerns as new modules. Logging setup is a distinct
concern (not config parsing, not download orchestration). Centralising handler construction and
filter attachment in one function makes the logging contract testable in isolation.

**Handler routing** (matches Constitution Principle IV and NFR-LOG-001):
- `TimedRotatingFileHandler` → `~/.gphotos-sync/gphotos-sync.log`, daily, 7 backups, level `DEBUG`
- `StreamHandler(sys.stderr)` → level `WARNING` and above
- `StreamHandler(sys.stdout)` → level `INFO` only (filtered to avoid duplicating WARNING/ERROR on stdout)

**Log format**: `%(asctime)s [%(levelname)-7s] %(message)s`

**Integration point**: `photo_sync.main()` calls `setup_logging()` once, before any profile logic runs.

---

## Decision 12: `playwright_state.json` Added to `.gitignore`

**Decision**: Add `playwright_state.json` to `.gitignore` at any directory depth alongside
existing exclusions for `credentials.json`, `token.json`, and `synced_ids.json`.

**Rationale**: The state file contains Google account auth cookies — equivalent sensitivity to `token.json`.
