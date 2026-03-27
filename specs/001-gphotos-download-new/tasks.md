# Tasks: Download New Photos from Google Photos

**Input**: Design documents from `/specs/001-gphotos-download-new/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/cli-contract.md ✓, quickstart.md ✓

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story this task belongs to (US1, US2, US3)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Initialize project structure and tooling. The existing `src/photo_sync.py` prototype is being replaced — do not modify it until T013.

- [x] T001 Create test directories: `tests/unit/` and `tests/integration/` at repo root (add `__init__.py` to each)
- [x] T002 Create `requirements.txt` at repo root listing: `google-api-python-client`, `google-auth`, `google-auth-oauthlib`, `google-api-core`, `requests`, `pytest`
- [x] T003 [P] Create `pytest.ini` at repo root configuring `testpaths = tests`, `python_files = test_*.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that ALL user stories depend on. No user story work can begin until this phase is complete.

**⚠️ CRITICAL**: Complete Phase 2 before starting any Phase 3+ work.

- [x] T004 Create `src/config.py`: define `SyncConfig` dataclass with fields: `config_dir` (Path), `destination` (Path), `date_from` (date), `date_to` (date), `max_backoff_seconds` (int, default 300), `lookback_pages` (int, default 5), `dry_run` (bool, default False), `verbose` (bool, default False)
- [x] T005 Add `parse_args() -> SyncConfig` to `src/config.py` using `argparse`: `--dest` (required), `--config-dir` (default `~/.gphotos-sync/`), `--date-from` (default: yesterday local TZ, format YYYY-MM-DD), `--date-to` (default: yesterday local TZ, format YYYY-MM-DD), `--max-backoff` (default 300), `--lookback-pages` (default 5), `--dry-run` (flag), `--verbose`/`-v` (flag); validate YYYY-MM-DD format and that `date_from <= date_to`
- [x] T006 [P] Create `src/auth.py`: implement `authenticate(config_dir: Path) -> Credentials` that loads `<config_dir>/token.json` (JSON via `Credentials.from_authorized_user_info()`), refreshes if expired, triggers `InstalledAppFlow` browser auth from `<config_dir>/credentials.json` if token missing or refresh fails, and saves updated credentials back to `token.json` via `creds.to_json()`; raise `FileNotFoundError` with clear message if `credentials.json` absent
- [x] T007 [P] Create `src/client.py`: implement `GooglePhotosClient` class that accepts `Credentials`; add `search_by_capture_date(date_from, date_to) -> list[dict]` method using `googleapiclient.discovery.build("photoslibrary", "v1")` `mediaItems.search` with `dateFilter.ranges`, full pagination via `nextPageToken` loop, and `google.api_core.retry.Retry` wrapper (initial=1s, multiplier=2, maximum=60s, deadline=`max_backoff_seconds`)
- [x] T008 Add `list_recent_items(pages: int) -> list[dict]` method to `GooglePhotosClient` in `src/client.py`: call `mediaItems.list` with full pagination, stop after `pages` pages; wrap with same `Retry` config as T007

**Checkpoint**: `SyncConfig`, auth, and API client are ready. User story implementation can begin.

---

## Phase 3: User Story 1 — Download Yesterday's Newly Uploaded Photos (Priority: P1) 🎯 MVP

**Goal**: Authenticate with Google Photos, find all photos where capture date falls on yesterday (plus recently-listed items not yet synced), and download them into a `<destination>/YYYY/MM/DD/` three-level folder hierarchy. Skip items already downloaded.

**Independent Test**: Set `--date-from` and `--date-to` to yesterday; confirm photos taken yesterday appear in `<dest>/2026/03/21/` (or equivalent date). Run again; confirm no re-downloads (exit summary shows 0 downloaded, N skipped).

### Implementation for User Story 1

- [x] T009 [US1] Create `src/downloader.py`: define `SyncState` dataclass with `synced_ids: set[str]` and `last_run: str`; implement `load_state(config_dir) -> SyncState` (reads `synced_ids.json`, returns empty state if absent) and `save_state(state, config_dir)` (writes atomically to `synced_ids.json`)
- [x] T010 [US1] Add `download_item(item: dict, destination: Path, state: SyncState, dry_run: bool) -> str` to `src/downloader.py`: parse `item["mediaMetadata"]["creationTime"]` to extract year/month/day; construct subfolder path as `destination / year / month / day` using `pathlib.Path` (platform-appropriate separator, zero-padded month and day); return `"skipped"` if filename already exists in that subfolder or item `id` is in `state.synced_ids`; otherwise download bytes from `item["baseUrl"] + "=d"` via `requests.get()` (no `os.system`/`curl`), save file, add ID to `state.synced_ids`; return `"downloaded"` on success or `"failed"` with logged error on exception; never abort for single-item errors
- [x] T011 [US1] Add `get_items_for_range(date_from, date_to) -> list[dict]` to `GooglePhotosClient` in `src/client.py`: call `search_by_capture_date(date_from, date_to)` (T007), call `list_recent_items(config.lookback_pages)` (T008), merge both result lists and deduplicate by `id` field; return combined unique list (upload-date proxy per research.md Decision 1)
- [x] T012 [US1] Add `run_sync(config: SyncConfig, client: GooglePhotosClient, state: SyncState) -> tuple[list, list, list]` to `src/downloader.py`: call `client.get_items_for_range(config.date_from, config.date_to)`, iterate items calling `download_item()` for each, collect downloaded/skipped/failed lists; update and save state after each successful download for durability
- [x] T013 [US1] Replace the prototype body of `src/photo_sync.py` with a new `main()`: call `parse_args()` → validate destination is writable and config_dir exists (raise `SystemExit(1)` with stderr message if not) → `authenticate()` → build `GooglePhotosClient` → `load_state()` → `run_sync()` → print minimal run summary to stdout; add `if __name__ == "__main__": main()`

**Checkpoint**: `python -m src.photo_sync --dest <path>` downloads yesterday's photos into `<dest>/YYYY/MM/DD/` subfolders using the platform separator. Re-run skips all. User Story 1 independently functional.

---

## Phase 4: User Story 2 — Download Today's Newly Uploaded Photos (Priority: P2)

**Goal**: Extend the default date range to include today so a single run covers both yesterday and today without extra flags. Confirm idempotent re-run behavior (already-downloaded items skipped).

**Independent Test**: Upload a photo to Google Photos today; run `python -m src.photo_sync --dest <path>` (no extra flags); confirm today's photo is downloaded. Run again; confirm it is skipped.

### Implementation for User Story 2

- [x] T014 [US2] Change `date_to` default in `parse_args()` in `src/config.py` from yesterday to today's local date, so the default range is `[yesterday, today]` inclusive
- [x] T015 [US2] Verify both skip conditions in `download_item()` in `src/downloader.py` are exercised: (a) file already on disk at `<dest>/<date>/<filename>` → `"skipped"`; (b) item `id` already in `state.synced_ids` (state persisted from prior run) → `"skipped"`; ensure neither path raises an exception

**Checkpoint**: Default run covers yesterday and today. Re-running any prior run produces zero downloads, all skipped. User Stories 1 and 2 both independently functional.

---

## Phase 5: User Story 3 — Sync Reporting & Visibility (Priority: P3)

**Goal**: Print a structured run summary (found / downloaded / skipped / failed counts + destination path) and per-item verbose output. Tool must exit with correct exit codes per `contracts/cli-contract.md`.

**Independent Test**: Run sync with `--verbose`; confirm each item shows `✓`/`-`/`✗` prefix. Confirm summary counts match actual files on disk. Force a download error (e.g., bad `baseUrl`); confirm `✗` line and non-zero failed count appear without aborting the run.

### Implementation for User Story 3

- [x] T016 [US3] Add `SyncRun` dataclass to `src/downloader.py`: fields `started_at` (datetime), `date_from` (date), `date_to` (date), `found` (int), `downloaded` (int), `skipped` (int), `failed` (list of `{"id": str, "filename": str, "error": str}`)
- [x] T017 [US3] Update `run_sync()` in `src/downloader.py` to populate and return a `SyncRun` instance instead of raw lists; increment `found`, `downloaded`, `skipped`, `failed` as each item is processed
- [x] T018 [US3] Implement `print_summary(run: SyncRun, destination: Path)` in `src/photo_sync.py`: write structured summary to stdout matching the format in `contracts/cli-contract.md` (date range header, Found/Downloaded/Skipped/Failed counts, Saved to path); write each failed item filename + error to stderr
- [x] T019 [US3] Implement per-item verbose output in `src/photo_sync.py`: when `config.verbose` is True, print `✓ <date>/<filename>` (downloaded), `- <date>/<filename> (skipped: already exists)`, or `✗ <date>/<filename> (failed: <error>)` as each item completes
- [x] T020 [US3] Implement `--dry-run` behavior in `src/photo_sync.py` and `src/downloader.py`: when `config.dry_run` is True, `download_item()` returns `"would-download"` without writing any file; `print_summary` prints dry-run header and "Would download: N" line per `contracts/cli-contract.md`; set exit code `0`
- [x] T021 [US3] Set exit codes in `src/photo_sync.py` per `contracts/cli-contract.md`: `sys.exit(0)` on success (even with failures in summary), `sys.exit(1)` on fatal errors (auth failure, destination not writable, unrecoverable API error), `sys.exit(2)` on invalid arguments (argparse handles this automatically)

**Checkpoint**: All three user stories fully functional. Summary output matches contract. Failures reported without aborting run.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Hardening, usability, and end-to-end validation.

- [x] T022 [P] Add `--max-backoff` value from `SyncConfig` to the `Retry` deadline parameter in `GooglePhotosClient` in `src/client.py` (currently hardcoded in T007; make it instance-configurable)
- [x] T023 [P] Add `src/__init__.py` and `tests/__init__.py` so `python -m src.photo_sync` module invocation works correctly
- [x] T024 [P] Add `tests/unit/test_config.py`: unit tests for `parse_args()` covering required `--dest`, default dates (yesterday/today), invalid date format rejection, and `date_from > date_to` rejection
- [x] T025 [P] Add `tests/unit/test_downloader.py`: unit tests for `download_item()` covering skip-by-filename, skip-by-synced-id, and failed-download-continues-run scenarios (mock `requests.get`)
- [ ] T026 Validate `quickstart.md` end-to-end: perform a manual run against a real Google account following the quickstart steps; confirm photos appear in dated subfolders and summary output matches expected format

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 completion — **BLOCKS all user stories**
- **US1 (Phase 3)**: Depends on Phase 2 — no dependency on US2 or US3
- **US2 (Phase 4)**: Depends on Phase 2 and Phase 3 (extends downloader.py from US1)
- **US3 (Phase 5)**: Depends on Phase 2 and Phase 3 (extends run_sync() and photo_sync.py from US1)
- **Polish (Phase 6)**: Depends on all story phases complete

### User Story Dependencies

- **US1 (P1)**: Depends on Foundational only — fully independent core
- **US2 (P2)**: Builds on US1 (same downloader, extended default date range)
- **US3 (P3)**: Builds on US1 (extends SyncRun reporting in run_sync() and main())

### Within Each Phase

- T004 before T005 (dataclass before parser references it)
- T006, T007, T008 are parallel (different files: auth.py, client.py)
- T007 before T008 (list method added to client class skeleton)
- T009 before T010 before T012 (SyncState → download_item → run_sync, all in downloader.py)
- T011 before T012 (get_items_for_range used by run_sync)
- T013 last in Phase 3 (wires all Phase 2 + Phase 3 components together)
- T016 before T017 (SyncRun dataclass before run_sync uses it)
- T018, T019, T020, T021 can follow T017 sequentially in photo_sync.py

### Parallel Opportunities Within Phase 2

```
T004 → T005       (config.py — sequential)
T006              (auth.py — parallel with T007/T008)
T007 → T008       (client.py — sequential within file)
```

### Parallel Opportunities Within Phase 3

```
T009 → T010 → T012    (downloader.py — sequential)
T011                   (client.py addition — parallel with T009/T010)
T012 → T013            (run_sync done, then wire main)
```

---

## Parallel Example: Foundational Phase

```
# These can run in parallel (different files):
T006: "Implement authenticate() in src/auth.py"
T007: "Implement GooglePhotosClient.search_by_capture_date() in src/client.py"

# After T007:
T008: "Add list_recent_items() to GooglePhotosClient in src/client.py"
```

## Parallel Example: Polish Phase

```
# These can all run in parallel (different files):
T022: "Make Retry deadline configurable in src/client.py"
T023: "Add __init__.py files"
T024: "Add tests/unit/test_config.py"
T025: "Add tests/unit/test_downloader.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T003)
2. Complete Phase 2: Foundational (T004–T008) — **CRITICAL: blocks all stories**
3. Complete Phase 3: User Story 1 (T009–T013)
4. **STOP and VALIDATE**: Run `python -m src.photo_sync --dest ~/photos` — photos download into dated subfolders; re-run shows all skipped
5. Ship MVP

### Incremental Delivery

1. Setup + Foundational → auth and API client ready
2. Add US1 (T009–T013) → core download working, dated subfolders, idempotent → **MVP**
3. Add US2 (T014–T015) → today's photos included by default
4. Add US3 (T016–T021) → full structured reporting, dry-run, exit codes
5. Polish (T022–T026) → hardened, tested, validated

### Parallel Team Strategy

With two developers after Foundational completes:
- **Developer A**: US1 (T009–T013) → US2 (T014–T015) → Unit tests (T024–T025)
- **Developer B**: US3 (T016–T021) → Polish (T022–T023, T026)

---

## Notes

- [P] tasks = different files or clearly non-conflicting additions; no dependencies on in-progress tasks
- [Story] label maps each task to a specific user story for traceability
- Each user story phase is independently completable and testable (validated at each Checkpoint)
- Do not touch `src/photo_sync.py` until T013 — prototype stays intact until new wiring is ready
- `os.system("curl ...")` and `pickle` from the prototype are explicitly replaced in T010 (requests) and T006 (JSON) respectively
- Commit after each phase checkpoint or logical task group
