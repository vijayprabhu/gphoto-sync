# Research: Performance Improvements

**Branch**: `003-performance-improvements` | **Created**: 2026-03-26

---

## Decision 1: Skip Detection Mechanism — Page Title Extraction

**Decision**: Navigate to each photo's detail page, extract the filename from `page.title()` (format: `"IMG_0001.jpg - Google Photos"`), check disk, and skip pressing `Shift+D` if the file already exists and is non-zero bytes.

**Rationale**: The suggested filename is only available after triggering a Playwright download (`download.suggested_filename`). To skip without starting a download, we need the filename before pressing `Shift+D`. Google Photos photo detail pages consistently show the filename in `<title>` as `"<filename> - Google Photos"`. Stripping the ` - Google Photos` suffix gives a reliable filename for the pre-check. This avoids all state files and keeps skip detection purely file-system-based per the spec assumption.

**Fallback**: If `page.title()` does not contain ` - Google Photos` (unexpected format), treat as unknown and download normally.

**Alternatives considered**:
- State file (per-date JSON of downloaded URLs) → **Rejected**: Adds state persistence complexity; spec says filename-based check is sufficient.
- DOM element inspection (e.g., download button label) → **Rejected**: More fragile than `<title>`; changes with Google Photos UI redesigns.
- Download then skip `save_as()` → **Rejected**: Still consumes bandwidth and download slot.
- Content hashing → **Rejected**: Explicitly excluded in spec Assumptions.

---

## Decision 2: Parallel Photo Downloads — `concurrent.futures.ThreadPoolExecutor` with Per-Thread Playwright Instances

**Decision**: Use `concurrent.futures.ThreadPoolExecutor(max_workers=N)` for within-date parallel photo downloads. Each worker thread creates its own `sync_playwright()` instance and loads the profile's `storage_state` file. No new third-party dependency needed (`concurrent.futures` is stdlib since Python 3.2).

**Rationale**: Playwright's sync API is backed by a single event loop per `sync_playwright()` instance. Multiple independent `sync_playwright()` instances can coexist in separate threads. Each thread owns: `pw = sync_playwright().start()`, one `browser`, one `context` (loaded from shared read-only `storage_state`), one `page` per photo. Threads never share Playwright objects, eliminating thread-safety concerns.

**Constitution note**: Constitution Principle V prohibits threading for `--profile all` sequential runs. This feature applies threading WITHIN a single date's download phase, which is explicitly specified (FR-005). Justified in Complexity Tracking below.

**Default**: `--workers 1` (default) runs sequentially, identical to current behaviour.

**Alternatives considered**:
- `asyncio` + Playwright async API → **Rejected**: Requires converting entire sync codebase; high risk; `asyncio` is explicitly listed as banned for `--profile all` and the spirit extends to avoiding async complexity.
- `multiprocessing` → **Rejected**: Higher overhead (full process fork); no benefit over threading for I/O-bound Playwright operations.
- Shared `BrowserContext` across threads → **Rejected**: Playwright's `BrowserContext` is not thread-safe; per-thread instances are required.

---

## Decision 3: Stage Timing — `time.monotonic()`

**Decision**: Record stage elapsed times using `time.monotonic()` (stdlib). Start time captured at stage entry; elapsed = `time.monotonic() - start`. Log at INFO level: `"[profile] Stage '<name>' completed in {elapsed:.1f}s"`.

**Three stages per date**:
1. **pre-flight** — destination folder creation + existing-file inventory
2. **collection** — Google Photos page load + scroll to find all photo URLs
3. **download** — all photo downloads (sequential or parallel)

**Rationale**: `time.monotonic()` is unaffected by wall-clock adjustments, correct for duration measurement. No new dependency. Matches the existing `logging` infrastructure already in place.

**Alternatives considered**:
- `datetime.now()` → **Rejected**: Susceptible to DST/NTP adjustments during run.
- `timeit` module → **Rejected**: For benchmarking loops; not appropriate for production stage timing.

---

## Decision 4: Pre-Flight Stage Ordering

**Decision**: Execute the pre-flight stage (destination folder existence check, `mkdir`, existing-file inventory) in `downloader.run_sync()` before calling `browser.ensure_session()`. If pre-flight fails (e.g., folder not creatable), abort with a clear error before any Google Photos network access.

**Rationale**: FR-009 mandates that all non-network stages complete before browser open. Current code creates folders inside `scraper.download_photos_for_date()` after the browser is already running. Moving folder creation and file inventory to a dedicated pre-flight step in `downloader.run_sync()` satisfies FR-009 and SC-006.

**New helper**: `_preflight(dates: List[date], destination: Path, force: bool) -> dict[date, set[str]]` — creates folders for all target dates, returns `{date: set_of_existing_filenames}` per date.

---

## Decision 5: `--force` and `--workers` Flags in `SyncConfig`

**Decision**: Add two new fields to `SyncConfig` and `parse_args()`:
- `force: bool = False` — maps to `--force` (`store_true`); disables skip behaviour.
- `workers: int = 1` — maps to `--workers N` (`type=int`, `default=1`); controls parallelism.

**Validation**: `--workers` must be ≥ 1; reject with exit code 2 if < 1.

**No config-file field**: `force` and `workers` are run-time flags only; they do not appear in `config.yml`. Profile authors set performance defaults via `date_offset` and `verbose`; concurrency is a per-run decision.

---

## Decision 6: `SyncRun` Extended with `skipped` Count and Stage Timings

**Decision**: Add `skipped: int = 0` and `stage_times: dict = field(default_factory=dict)` to the `SyncRun` dataclass. `stage_times` maps stage name (str) to elapsed seconds (float).

**Rationale**: The run summary must report skipped count (FR-002, SC-003). Stage timings are logged at INFO level per run (FR-010, SC-007). Storing them on `SyncRun` allows `photo_sync.print_summary()` to display them and tests to assert them without reaching into internals.
