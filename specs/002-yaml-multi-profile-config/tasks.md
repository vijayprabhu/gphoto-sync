# Tasks: Logging for gphotos-sync

**Input**: Design documents from `specs/002-yaml-multi-profile-config/`
**Branch**: `002-yaml-multi-profile-config` | **Generated**: 2026-03-26
**Prerequisites**: plan.md ✅ | spec.md ✅ | research.md ✅ | data-model.md ✅ | contracts/cli-contract.md ✅

**Tests**: Unit tests included for `src/logger.py` (core logic is pure and directly testable).

**Organization**: Logging is a cross-cutting NFR. Tasks are grouped by integration surface
mapped to the user story each surface primarily serves.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no shared dependencies)
- **[Story]**: User story this task serves — [US1] configure accounts, [US2] centralize settings, [US3] validate config, [US4] sync all profiles

---

## Phase 1: Setup

**Purpose**: No new dependencies or project structure changes needed.
stdlib `logging` is available in Python 3.9+. One new source file and one new test file are created.

- [x] T001 Create `src/logger.py` as an empty module (placeholder for Phase 2)
- [x] T002 Create `tests/unit/test_logger.py` as an empty test file (placeholder for Phase 2)

---

## Phase 2: Foundational — `src/logger.py` Core

**Purpose**: The logger module must be fully functional before any other module can import it.
All user story integration tasks in Phases 3–6 depend on this phase completing.

**⚠️ CRITICAL**: No integration work can begin until T005 is complete.

- [x] T003 Implement `RedactingFilter(logging.Filter)` in `src/logger.py` — replaces `token_dir` strings with `<token_dir>` and full `playwright_state.json` paths with `<session_file>` in `record.msg` and `record.args` (NFR-LOG-004)
- [x] T004 Implement `setup_logging(verbose: bool, log_dir: Path, token_dirs: list[Path]) -> logging.Logger` in `src/logger.py` with three handlers: `TimedRotatingFileHandler(when="midnight", backupCount=7)` writing to `log_dir/gphotos-sync.log`; `StreamHandler(sys.stderr)` for WARNING+; `StreamHandler(sys.stdout)` for INFO only (NFR-LOG-001, NFR-LOG-002, NFR-LOG-003)
- [x] T005 Add log-file write failure handling in `setup_logging()` in `src/logger.py` — wrap `TimedRotatingFileHandler` construction in try/except OSError; on failure emit a stderr warning and continue with console-only handlers without raising (NFR-LOG-004 edge case)
- [x] T006 [P] Write unit tests for `RedactingFilter` in `tests/unit/test_logger.py` — verify: token_dir path replaced with `<token_dir>`, session file path replaced with `<session_file>`, unrelated strings pass through unchanged
- [x] T007 [P] Write unit tests for `setup_logging()` in `tests/unit/test_logger.py` — verify: INFO routes to stdout handler, WARNING routes to stderr handler, DEBUG suppressed without `verbose=True`, `RedactingFilter` attached to all handlers

**Checkpoint**: `python -m pytest tests/unit/test_logger.py` — all tests pass before proceeding.

---

## Phase 3: User Story 1 — Configure Multiple Accounts (P1) 🎯 MVP

**Goal**: Every sync run for every profile emits structured log output (file + console) with
sensitive paths redacted, giving users a per-account audit trail in `gphotos-sync.log`.

**Independent test**: Run `python -m src.photo_sync --profile personal` (valid config).
Verify `~/.gphotos-sync/gphotos-sync.log` is created and contains `[personal] Sync started`
and `[personal] Sync complete` entries. Confirm no raw `token_dir` absolute path appears.

- [x] T008 [US1] Add `_collect_token_dirs(config_data: dict) -> list[Path]` helper in `src/photo_sync.py` — extracts `token_dir` values from all profile dicts; skips profiles missing the field; returns `list[Path]`
- [x] T009 [US1] Wire `setup_logging()` into `photo_sync.main()` in `src/photo_sync.py` — call after pre-parsing `--config`/`--profile`/`--verbose`; derive `log_dir` from `pre_args.config.parent`; pass `token_dirs` from `_collect_token_dirs()`; import `logger` module
- [x] T010 [P] [US1] Replace `print(..., file=sys.stderr)` calls in `src/browser.py` `ensure_session()` with logger calls — "No saved session" → `logger.info`, "Session expired" → `logger.warning`, "Opening browser" → `logger.info`; use `logging.getLogger("gphotos_sync")`
- [x] T011 [P] [US1] Add login-success log event in `src/browser.py` `_login_headed()` — emit `logger.info("[%s] Login successful, session saved", profile_name)` after `context.storage_state()` completes

**Checkpoint**: Single-profile sync → `gphotos-sync.log` created; per-profile events logged; no raw paths visible.

---

## Phase 4: User Story 4 — Sync All Profiles (P2)

**Goal**: `--profile all` runs produce per-profile structured log entries so a cron operator
can review one log file to audit all accounts.

**Independent test**: Run `python -m src.photo_sync --profile all`. Verify `gphotos-sync.log`
contains `Sync started` and `Sync complete` entries for each profile in order. Confirm
`=== Profile: <name> ===` separators still appear on stdout (not in the log file).

- [x] T012 [US4] Add run-start log event in `src/downloader.py` `run_sync()` — emit `logger.info("[%s] Sync started: %s", profile_name, effective_dates)` after `_resolve_dates()` returns; import `logging`; use `logging.getLogger("gphotos_sync")` (NFR-LOG-005)
- [x] T013 [US4] Add run-complete log event in `src/downloader.py` `run_sync()` — emit `logger.info("[%s] Sync complete: downloaded=%d, failed=%d", profile_name, run.downloaded, run.failed)` in the `finally` block before `close_session()` (NFR-LOG-005)
- [x] T014 [US4] Add per-photo failure log event in `src/downloader.py` — emit `logger.error("[%s] FAILED: %s — %s", profile_name, filename, reason)` on each download failure (NFR-LOG-005)

**Checkpoint**: `--profile all` run → log contains sequential per-profile entries; failed profile failure reason logged at ERROR level.

---

## Phase 5: User Story 2 — Init Flow Logging (P2)

**Goal**: The `--init` profile flow participates in structured logging so a user setting up a
new account can verify what happened after the fact.

**Independent test**: Run `python -m src.photo_sync --init testprofile`. Verify the log
contains Chromium install notice (if applicable) and login success. Confirm `<token_dir>`
appears instead of the raw path in all log lines.

- [x] T015 [P] [US2] Replace `print(..., file=sys.stderr)` calls in `src/init.py` `init_profile()` with logger calls — profile-written confirmation → `logger.info`; login prompt → `logger.info`; login not completed → `logger.error`; use `logging.getLogger("gphotos_sync")`
- [x] T016 [P] [US2] Add Chromium install log events in `src/init.py` `_ensure_chromium()` — emit `logger.info("Chromium not found — installing via playwright install chromium")` before subprocess; emit `logger.error(...)` if returncode != 0

**Checkpoint**: `--init testprofile` → init events in log file; token_dir path redacted.

---

## Phase 6: User Story 3 — Config Validation Logging (P3)

**Goal**: Config validation errors are captured in the log file so automated cron runs
produce a traceable failure record even when the process exits with code 1.

**Independent test**: Run with a deliberately broken profile (missing `destination`).
Verify `gphotos-sync.log` contains an ERROR entry naming the missing field — even though
the process exits with code 1.

- [x] T017 [US3] Log config validation errors in `src/photo_sync.py` `main()` — catch `SystemExit` from `parse_args()`; before re-raising, emit `logger.error("Config validation failed — see stderr for details")` so the failure is captured in the log file alongside the existing stderr message

**Checkpoint**: Broken config run → ERROR in log file; process still exits 1; existing stderr error message unchanged.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Verify full test suite, update documentation, and confirm log output format
is consistent across all integration points.

- [x] T018 [P] Update `README.md` — add log file location (`~/.gphotos-sync/gphotos-sync.log`), rotation policy (daily, 7 days), and redaction note to the Troubleshooting section
- [x] T019 [P] Update `specs/002-yaml-multi-profile-config/quickstart.md` — add log file (`gphotos-sync.log`) to the "File Layout After Setup" directory tree
- [x] T020 Run `python -m pytest` — all existing tests plus new `test_logger.py` tests must pass; fix any regressions before marking complete
- [x] T021 Verify log output manually — run a real sync with `--verbose`; open `gphotos-sync.log`; confirm: (a) no raw `token_dir` paths present, (b) INFO/WARNING/ERROR entries appear, (c) DEBUG entries present only under `--verbose`, (d) rotation creates dated backup files after midnight

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — **BLOCKS all integration phases**
- **Phase 3 (US1)**: Depends on Phase 2 (T005 complete) — no dependency on US2/US4
- **Phase 4 (US4)**: Depends on Phase 2 (T005 complete) — can run parallel with Phase 3
- **Phase 5 (US2)**: Depends on Phase 2 (T005 complete) — can run parallel with Phases 3 and 4
- **Phase 6 (US3)**: Depends on T009 (logger wired into `photo_sync.main()` in Phase 3)
- **Phase 7 (Polish)**: Depends on all phases complete

### User Story Dependencies

- **US1 (Phase 3)**: Independent after Phase 2
- **US4 (Phase 4)**: Independent after Phase 2
- **US2 (Phase 5)**: Independent after Phase 2
- **US3 (Phase 6)**: Requires T009 from Phase 3 (logger must be set up in `main()` before validation errors can be logged)

### Within Each Phase

- T008 before T009 (helper needed before call site)
- T012, T013, T014 are sequential (same function scope in `downloader.py`)
- T003 before T004 before T005 (sequential logger construction)
- T006, T007 can be written in parallel with T003–T005

### Parallel Opportunities

- T006 and T007 parallel with T003–T005 (tests written alongside implementation)
- T010 and T011 parallel within Phase 3 (different functions in `browser.py`)
- Phases 3, 4, 5 fully parallel after Phase 2 completes
- T018 and T019 parallel in Phase 7 (different files)

---

## Parallel Example: Phase 2 (Foundational)

```
Parallel stream A: T003 → T004 → T005  (implementation)
Parallel stream B: T006, T007           (unit tests, written alongside)
Sync point: all of T003–T007 done → proceed to Phases 3/4/5
```

## Parallel Example: Phases 3, 4, 5 (after Phase 2)

```
Once T005 passes:
  Stream A: T008 → T009 → T010/T011  (photo_sync + browser — US1)
  Stream B: T012 → T013 → T014       (downloader — US4)
  Stream C: T015, T016               (init — US2)
All three streams independent — different files throughout
```

---

## Implementation Strategy

### MVP (Phases 1–3 only)

1. Complete Phase 1: create empty files
2. Complete Phase 2: `src/logger.py` fully implemented and tested
3. Complete Phase 3: logger wired into `photo_sync.py` and `browser.py`
4. **STOP and VALIDATE**: run a real sync, check log file content and redaction
5. Remaining phases extend coverage — no regressions expected

### Incremental Delivery

1. Phase 1 + 2 → logger module ready, unit-tested ✅
2. Phase 3 → US1 profile sync events in log file ✅
3. Phase 4 → US4 `--profile all` run events logged ✅
4. Phase 5 → `--init` flow logged ✅
5. Phase 6 → config errors captured in log ✅
6. Phase 7 → full polish, README updated ✅

---

## Notes

- `logging.getLogger("gphotos_sync")` is the canonical logger name across all modules — never use `logging.getLogger(__name__)` so all output shares one named logger
- Existing `print()` calls to **stdout** in `photo_sync.py` (run summaries: "Downloaded:", "Saved to:", etc.) MUST NOT be replaced — they are user-facing output, not log events (Constitution Principle IV / cli-contract.md)
- Only `print(..., file=sys.stderr)` calls are candidates for replacement with logger calls
- `[P]` tasks operate on different files or different functions — safe to run concurrently
- Commit after each phase checkpoint — each phase is independently verifiable
