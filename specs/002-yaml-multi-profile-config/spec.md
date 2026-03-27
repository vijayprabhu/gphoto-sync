# Feature Specification: YAML Multi-Profile Configuration

**Feature Branch**: `002-yaml-multi-profile-config`
**Created**: 2026-03-22
**Status**: Draft
**Input**: User description: "Ensure that all configurations are stored in a yml file, and the file can hold multiple profile. Each profile would host diff google account"

## Clarifications

### Session 2026-03-26

- Q: Where should log output be written? → A: Both — structured file log at `~/.gphotos-sync/gphotos-sync.log` AND stderr/stdout streams simultaneously (errors/warnings → stderr, run summaries → stdout).
- Q: What log levels should the tool support? → A: Four levels: DEBUG, INFO, WARNING, ERROR; DEBUG is enabled when `--verbose` is passed.
- Q: Where should the log file be written? → A: Fixed path at `~/.gphotos-sync/gphotos-sync.log`; no configuration needed.
- Q: How should the log file be rotated? → A: Time-based rotation — one file per day, retaining 7 days of history.
- Q: Should any data be redacted from log output? → A: Yes — `token_dir` paths and session file paths (`playwright_state.json` locations) must be redacted in all log output to avoid leaking sensitive filesystem locations.

### Session 2026-03-25

- Q: Given that the Google Photos Library API only exposes app-created media items (not phone-uploaded photos), what mechanism should the tool use to access the user's full library? → A: Playwright browser automation — drive the Google Photos web UI filtered by date, download photos individually, and save them in a YYYY/MM/DD local folder hierarchy; the Google Photos Library API (`photoslibrary.readonly`) is replaced as the primary download mechanism.
- Q: How should browser session authentication be managed per profile for Playwright? → A: Persistent session — on first run open a visible browser for manual Google login; save Playwright browser storage state (cookies + localStorage) to `token_dir`; reuse saved state on subsequent runs; re-open browser automatically when the session expires.
- Q: What date selection strategy should the tool use? → A: Both `--date YYYY-MM-DD` (single day, for daily runs with an optional per-profile `date_offset` default) and `--start-date` / `--end-date` (date range, for catch-up re-runs when a prior run failed); the two modes are mutually exclusive on a single invocation.
- Q: Which date governs photo selection and YYYY/MM/DD folder placement? → A: Capture date (when the photo was taken, from EXIF/metadata); matches Google Photos timeline order; upload date is ignored.
- Q: When re-running over a date range, should already-downloaded photos be skipped? → A: No — always re-download; every run downloads all photos in the specified date range, overwriting existing local files; no `synced_ids.json` deduplication state is maintained.

### Session 2026-03-22

- Q: Does the YAML config file replace the `--config-dir` approach or coexist with it? → A: Replace entirely — YAML config becomes the only supported approach; `--config-dir` is removed.
- Q: Where should per-profile OAuth tokens and sync state files be stored? → A: Specified explicitly in each profile via a `token_dir` field pointing to a directory on disk.
- Q: Should the tool support running all profiles in sequence with a single command? → A: Yes — `--profile all` runs every profile in the config file sequentially, printing each profile's summary separately.
- Q: Should path fields in the config file support relative paths or absolute only? → A: Absolute paths only — simpler and unambiguous; relative paths are not resolved.
- Q: What happens when the tool is run with no `--profile` flag and no `default` profile exists? → A: Error — report that no `default` profile was found and list all available profile names so the user can pick one explicitly.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Configure Multiple Google Accounts in One File (Priority: P1)

A user who wants to sync photos from multiple Google accounts creates a single configuration file that defines a named profile for each account. Each profile contains the account-specific settings (download destination, browser session directory, date range preferences). The user selects which profile to use when running the sync tool.

**Why this priority**: This is the core stated goal — replace scattered per-directory config with a single, readable file that supports multiple named profiles. Without this, managing multiple accounts is error-prone and undiscoverable.

**Independent Test**: Can be fully tested by creating a config file with two profiles and running the sync with each profile name; the tool loads the correct settings for each without the other profile interfering.

**Acceptance Scenarios**:

1. **Given** a config file with two profiles named `personal` and `work`, **When** the user runs the sync with `--profile personal`, **Then** the tool uses the settings defined under the `personal` profile and ignores the `work` profile.
2. **Given** a config file with a `default` profile, **When** the user runs the sync without specifying `--profile`, **Then** the tool uses the `default` profile automatically.
3. **Given** a config file that is missing or empty, **When** the user runs the sync, **Then** the tool reports a clear error describing what is missing and how to create the file.

---

### User Story 2 - Centralize All Sync Settings per Profile (Priority: P2)

Each profile in the configuration file holds all settings relevant to that account's sync behavior: the local download destination, the browser session directory, preferred date defaults, and verbosity. Users no longer need to pass multiple flags on every run.

**Why this priority**: Centralizing all configuration per profile reduces the chance of misconfiguration and makes scheduled/automated runs simpler — a single `--profile` argument replaces a long list of CLI flags.

**Independent Test**: Can be fully tested by setting all options in a profile (destination, date range, verbosity) and running the sync with only `--profile <name>`; the tool behaves exactly as if all flags had been passed manually.

**Acceptance Scenarios**:

1. **Given** a profile that specifies a destination folder and a date range, **When** the user runs the sync with `--profile <name>` and no other flags, **Then** the tool downloads to the specified destination covering the specified date range.
2. **Given** a profile setting that conflicts with an explicit CLI flag on the same run, **When** the user runs the sync, **Then** the explicit CLI flag takes precedence over the profile setting (CLI overrides config).
3. **Given** a profile that omits an optional setting, **When** the user runs the sync, **Then** the tool applies the built-in default for that setting without error.

---

### User Story 3 - Validate Configuration on Load (Priority: P3)

When the tool starts, it validates the configuration file structure and the selected profile's required fields. If the file is malformed or a required field is missing, the tool reports exactly which profile and field is problematic before attempting any network activity.

**Why this priority**: Early validation prevents confusing mid-run errors when, for example, a destination path is missing. It reduces troubleshooting time significantly.

**Independent Test**: Can be fully tested by deliberately omitting a required field and running the sync; the tool exits with a clear error message naming the missing field before downloading anything.

**Acceptance Scenarios**:

1. **Given** a config file with a profile that is missing a required field (e.g., no `destination`), **When** the user runs the sync with that profile, **Then** the tool reports the missing field by name and exits before opening any browser.
2. **Given** a config file with invalid structure (e.g., unparseable content), **When** the user runs the sync, **Then** the tool reports a parse error with the file path and exits with a non-zero code.
3. **Given** a profile name that does not exist in the config file, **When** the user runs the sync with `--profile <name>`, **Then** the tool lists available profile names in the error message.
4. **Given** a config file with no profile named `default`, **When** the user runs the sync with no `--profile` flag, **Then** the tool exits with an error listing all available profile names.

---

### User Story 4 - Sync All Profiles with One Command (Priority: P2)

A user running a nightly cron job or scheduled task invokes the sync tool with `--profile all`, which runs every profile defined in the config file sequentially. Each profile's summary is printed separately. If one profile fails, the tool continues with the remaining profiles and reports the failure at the end.

**Why this priority**: Directly serves the multi-account use case — a single scheduler entry covers all accounts without per-profile job entries.

**Independent Test**: Can be fully tested by creating a config file with two profiles and running `--profile all`; both profiles' summaries appear in output and files are downloaded to each profile's destination.

**Acceptance Scenarios**:

1. **Given** a config file with three profiles, **When** the user runs the sync with `--profile all`, **Then** each profile is synced in the order it appears in the config file and each profile's summary is printed.
2. **Given** one profile fails (e.g., auth error), **When** running `--profile all`, **Then** the tool logs the failure for that profile and continues syncing the remaining profiles.
3. **Given** `--profile all` combined with a CLI flag (e.g., `--dry-run`), **When** the user runs the sync, **Then** the CLI flag applies to every profile in the run.

---

### Edge Cases

- What happens when both `--date` and `--start-date`/`--end-date` are provided together? The tool exits with a validation error before opening any browser.
- What happens when `--start-date` is later than `--end-date`? The tool exits with a validation error.
- What happens when the saved Playwright browser session in `token_dir` has expired or been invalidated? The tool detects the expired session, deletes the stale state file, opens a visible browser for the user to log in again, and saves the new session before continuing.
- What happens when two profiles share the same destination folder?
- How does the tool handle a config file with a profile whose `destination` or `token_dir` path does not exist on disk? The tool creates missing directories automatically before downloading.
- What happens when the config file contains a profile with no name (empty key)?
- How are default values applied when a profile omits optional settings?
- What happens when the log file directory (`~/.gphotos-sync/`) is not writable? The tool MUST warn on stderr and continue operating using console-only output — a log file write failure must never abort a sync run.
- What happens when a log rotation deletes a file that another process has open? Handled by `TimedRotatingFileHandler` at the OS level; no special handling required.
- What happens when the config file is readable but contains no profiles at all? The tool exits with an error stating the file contains no profiles.
- If the user omits `--profile` and no `default` profile exists, the tool exits with an error listing all available profile names.
- If a path field in a profile contains a relative path, the tool rejects it at validation time with an error naming the field and profile, before any network activity.
- What happens when a CLI flag and a profile setting both specify the destination — which wins?
- When `--profile all` is used and one profile's auth requires a browser flow, how is the user notified without blocking the remaining profiles?

## Requirements *(mandatory)*

### Non-Functional Requirements — Observability

- **NFR-LOG-001**: The tool MUST write log output to two destinations simultaneously: (1) the console (`stderr` for WARNING/ERROR, `stdout` for INFO run summaries) and (2) a structured log file at `~/.gphotos-sync/gphotos-sync.log`.
- **NFR-LOG-002**: The tool MUST support four log levels: DEBUG, INFO, WARNING, ERROR. DEBUG-level messages are emitted only when `--verbose` is passed; INFO and above are always emitted.
- **NFR-LOG-003**: The log file MUST use time-based daily rotation, retaining the current day's file plus 6 prior days (7 days total). Older files are deleted automatically.
- **NFR-LOG-004**: `token_dir` absolute paths and `playwright_state.json` file paths MUST be redacted from all log output (both console and file). Display as `<token_dir>` and `<session_file>` respectively.
- **NFR-LOG-005**: Every sync run MUST log at minimum: profile name, date(s) processed, count of photos downloaded, count of failures, and final exit status.

### Functional Requirements

- **FR-001**: System MUST support a configuration file (in a human-readable structured format) that contains one or more named profiles.
- **FR-002**: Each profile MUST define at minimum: a name, a local download destination (`destination`), and a directory for storing Playwright browser session state (`token_dir`). The `credentials_path` field (OAuth client secrets) is removed; browser session cookies stored in `token_dir` replace OAuth token storage. No `synced_ids.json` deduplication file is used; every run overwrites existing files in the destination.
- **FR-003**: Each profile MAY define optional sync settings: `date_offset` (integer, e.g., `-1` for yesterday; used as the default when `--date` is omitted), verbosity preference. `--date YYYY-MM-DD` and `--start-date` / `--end-date` are mutually exclusive; passing both is a validation error.
- **FR-004**: System MUST load the configuration file from a well-known default location (`~/.gphotos-sync/config.yml`) and also accept an explicit path via a CLI flag (`--config`). The previous `--config-dir` flag is removed; the YAML config file is the sole configuration mechanism.
- **FR-005**: System MUST accept a `--profile <name>` CLI flag to select which profile to use for a given sync run.
- **FR-005a**: System MUST support `--profile all` to run every profile defined in the config file sequentially, printing each profile's summary separately; a failure in one profile must not abort the remaining profiles.
- **FR-006**: System MUST use a profile named `default` automatically when no `--profile` flag is provided and a `default` profile exists in the config file. If no `default` profile exists and no `--profile` flag is given, the tool MUST exit with an error listing all available profile names.
- **FR-007**: System MUST allow CLI flags to override individual profile settings on a per-run basis (CLI takes precedence over config file values).
- **FR-008**: System MUST validate the configuration file on startup and report specific, actionable errors (missing required fields `destination` or `token_dir`; unrecognized profile name; parse failure; `--date` and `--start-date`/`--end-date` used together; `--start-date` later than `--end-date`) before opening any browser. All path fields (`destination`, `token_dir`) must be absolute paths; the tool must reject relative paths with a clear error.
- **FR-009**: System MUST list available profile names in the error message when a requested profile is not found.
- **FR-010**: System MUST support at least 10 profiles in a single configuration file without degraded behavior.

### Key Entities

- **Config File**: The single structured file holding all profiles; located at a well-known path or specified via `--config`; human-readable and editable without special tooling.
- **Profile**: A named set of configuration values for one Google account sync; identified by a unique name within the file; contains required and optional fields.
- **Profile Settings**: The individual key-value pairs within a profile. Required: `destination` (absolute path to local download root), `token_dir` (absolute path to directory where Playwright browser storage state is stored). Optional: `date_offset` (integer default day offset for `--date`-less runs, e.g., `-1` for yesterday), verbosity. All path values must be absolute. `credentials_path` is removed — browser session cookies replace OAuth token storage. Photos are placed in `destination/YYYY/MM/DD/` based on capture date. No `synced_ids.json` deduplication state is maintained; every run overwrites existing files.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can configure and run syncs for 2 or more Google accounts using a single config file and a single `--profile` argument per run, with no other flags required.
- **SC-002**: Switching between profiles requires only changing the `--profile` argument — no other environment or directory changes are needed.
- **SC-003**: A misconfigured profile (missing required field or invalid file) produces an error message that names the exact field or problem within 1 second of launch, before any network call is made.
- **SC-004**: Adding a new profile to an existing config file takes under 2 minutes for a user familiar with the file format, without consulting documentation.
- **SC-005**: After any sync run, `~/.gphotos-sync/gphotos-sync.log` exists and contains an entry recording the profile name, dates processed, download count, and exit status. No `token_dir` or session file paths appear in the log content.
- **SC-006**: Log files older than 7 days are automatically absent from `~/.gphotos-sync/`.

## Assumptions

- The configuration file uses a human-readable structured text format (YAML); no binary or proprietary formats.
- Each profile corresponds to exactly one Google account; a single profile cannot aggregate multiple accounts.
- The Google Photos Library API (`photoslibrary.readonly`) is **not** the download mechanism; the API restricts access to app-created items only and cannot access phone-uploaded photos. The tool uses Playwright browser automation against the Google Photos web UI instead.
- Per-profile browser session state (cookies) is stored in `token_dir` per profile, replacing OAuth token storage for the download mechanism. The `credentials_path` field (OAuth client secrets) is removed from the profile schema.
- OAuth tokens (access/refresh tokens) for the Google Photos Library API are no longer used; browser session cookies stored per profile replace them.
- The previous `--config-dir` approach (feature 001) is fully replaced by this YAML config; no backward compatibility layer is provided.
- The tool is single-user per run; running two profiles simultaneously in the same process is out of scope.
- Profile names are case-sensitive and must be unique within the config file.

## Constraints & Tradeoffs

- **Playwright over API**: The Google Photos Library API is restricted to app-created media items only (per official 2024/2025 API policy change). Playwright browser automation is used instead to access the full library including phone-uploaded photos. Trade-off: the automation is brittle to Google Photos UI changes and may require maintenance if the web interface changes.
- **No `credentials_path` field**: The OAuth client secrets file (`credentials.json`) and `photoslibrary.readonly` scope are no longer needed per profile. Browser session cookies (stored in `token_dir`) replace this.
- **New dependency — Playwright**: `playwright` (Python) is added as a required dependency. This must be documented in `research.md` per the project constraint on new dependencies.
