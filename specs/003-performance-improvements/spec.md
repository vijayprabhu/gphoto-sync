# Feature Specification: Performance Improvements

**Feature Branch**: `003-performance-improvements`
**Created**: 2026-03-26
**Status**: Draft
**Input**: User description: "Performance Improvements."

## Clarifications

### Session 2026-03-26

- Q: Should stages that don't require network access run before Google Photos is contacted? → A: Yes — folder existence checks and creation must complete before any Google Photos network access begins.
- Q: Should elapsed time be logged for each stage? → A: Yes — each stage must log its elapsed time.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Skip Already-Downloaded Photos (Priority: P1)

A user who runs the sync daily (or re-runs after a partial failure) currently re-downloads every photo for the date, even if the file already exists on disk. The tool should detect existing files and skip them, making repeated runs for the same date nearly instant.

**Why this priority**: This is the most impactful improvement for regular users — cron-based daily syncs often re-run due to transient failures. Skipping existing files saves bandwidth and time proportional to how many photos have already been synced.

**Independent Test**: Run a sync for a date that has already been fully synced. Verify that 0 photos are downloaded, the run completes in seconds, and no existing files are overwritten.

**Acceptance Scenarios**:

1. **Given** a destination folder already contains `IMG_0001.jpg` for a date, **When** the tool syncs that same date, **Then** `IMG_0001.jpg` is skipped and the summary shows it as skipped (not downloaded, not failed).
2. **Given** a destination folder contains some but not all photos for a date, **When** the tool syncs that date, **Then** only the missing photos are downloaded and existing ones are skipped.
3. **Given** a destination folder is empty, **When** the tool syncs a date, **Then** all photos are downloaded as normal (no regression).
4. **Given** `--force` flag is provided, **When** the tool syncs a date, **Then** all photos are re-downloaded regardless of existing files.

---

### User Story 2 - Parallel Photo Downloads Within a Date (Priority: P2)

Currently photos for a single date are downloaded one at a time. A user syncing a date with 50+ photos waits for each download to complete sequentially. Downloading multiple photos concurrently would significantly reduce total sync time.

**Why this priority**: Reduces wall-clock time for large date syncs. Particularly valuable for catch-up runs covering multiple days or dates with many photos (e.g., vacation days).

**Independent Test**: Run a sync for a date with at least 10 photos. Verify total time is measurably less than sequential download time, all photos are saved correctly, and the summary counts are accurate.

**Acceptance Scenarios**:

1. **Given** a date has 20 photos, **When** the tool syncs with `--workers 4`, **Then** all 20 photos are saved correctly and total time is less than sequential time.
2. **Given** some parallel downloads fail, **When** the sync completes, **Then** failed photos are counted correctly and successful ones are not affected.
3. **Given** no `--workers` flag is specified, **When** the tool syncs, **Then** behaviour is identical to the current sequential mode (no regression).

---

### User Story 3 - Smarter Photo Grid Scroll Detection (Priority: P3)

The scraper scrolls the photo grid with a fixed pause between each scroll and up to 60 attempts, even when the grid has loaded all photos. A user with 5 photos on a date waits through unnecessary scroll cycles. Detection should stop as soon as the grid is stable.

**Why this priority**: Reduces the time spent on the collection phase, especially for dates with few photos. The fixed-pause approach is conservative; early-exit on stability is a quality-of-life improvement.

**Independent Test**: Run a sync for a date with fewer than 5 photos. Verify that the scraper exits the scroll loop well before the 60-attempt maximum and completes faster than the current worst-case scroll time.

**Acceptance Scenarios**:

1. **Given** a date has 3 photos and all load on the first scroll, **When** the tool syncs, **Then** the scraper exits the scroll loop within 3 stable-check cycles (not 60).
2. **Given** a date has 200 photos requiring many scrolls, **When** the tool syncs, **Then** all photos are found and the scraper does not exit prematurely.

---

### Edge Cases

- What happens if a file exists on disk but is zero bytes (incomplete previous download)? → Zero-byte files are treated as missing and re-downloaded.
- What happens if parallel downloads hit rate limits? → Failed downloads are retried once; persistent failures are counted as failed and logged.
- What happens if `--workers 1` is specified? → Behaviour is identical to the current sequential mode.
- What happens if the destination folder has files with the same name but different content? → Existing non-zero-byte files are always skipped unless `--force` is provided.
- What happens if destination folder creation fails during pre-flight? → The run aborts immediately with a clear error before any Google Photos network access is attempted.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The tool MUST skip downloading a photo if a file with the same name already exists in the destination folder and is non-zero bytes.
- **FR-002**: The tool MUST report skipped photos in the run summary with a dedicated "Skipped" count separate from "Downloaded" and "Failed".
- **FR-003**: The tool MUST provide a `--force` flag that disables skip behaviour and re-downloads all photos unconditionally.
- **FR-004**: Zero-byte files in the destination MUST be treated as missing and re-downloaded even without `--force`.
- **FR-005**: The tool MUST support concurrent photo downloads within a single date via a `--workers N` flag (default: 1, preserving current sequential behaviour).
- **FR-006**: When `--workers` is greater than 1, all photos for a date MUST be accurately accounted for in the downloaded/failed/skipped counts.
- **FR-007**: The scroll loop MUST exit early when no new photos are discovered across 3 consecutive stable scroll attempts (same threshold as current `no_new_count >= 3` logic, but with adaptive timing).
- **FR-008**: The log MUST report how many photos were found, downloaded, skipped, and failed for each date.
- **FR-009**: All stages that do not require Google Photos network access (destination folder check, folder creation, existing-file inventory) MUST execute and complete before the browser session is opened or any Google Photos URL is contacted.
- **FR-010**: The tool MUST log the elapsed time of each distinct stage: pre-flight (folder check/creation), photo collection (scroll), and download. Elapsed time MUST appear in the log file for every sync run.

### Key Entities

- **Photo file**: Identified by filename within a `YYYY/MM/DD/` destination subfolder; presence and non-zero size determine skip eligibility.
- **SyncRun**: Extended to include a `skipped` count alongside the existing `downloaded` and `failed` counts, plus per-stage elapsed times.
- **Stage**: A named, timed unit of work within a sync run — pre-flight, collection, and download are the three stages.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A repeat sync of a fully-downloaded date completes in under 10 seconds regardless of how many photos that date contains.
- **SC-002**: A first-time sync of a date with 30 photos completes at least 2× faster with `--workers 4` than with the default sequential mode.
- **SC-003**: The "Skipped" count in the run summary is always accurate — no photo is miscounted as downloaded or failed when it was skipped.
- **SC-004**: Zero photos are lost or corrupted when parallel downloads are used — file count and integrity match a sequential run of the same date.
- **SC-005**: The scroll collection phase exits within 3 stable-check cycles after the last new photo is found, not at the fixed 60-attempt maximum.
- **SC-006**: No Google Photos network request is made until all pre-flight stages (folder checks, folder creation) have completed successfully.
- **SC-007**: Each stage's elapsed time appears in the log file for every run, enabling users to identify which stage is slowest.

## Assumptions

- Parallel downloads are scoped to photos within a single date; cross-date parallelism is out of scope.
- "Same filename" is sufficient for skip detection — content hashing is not required.
- Omitting `--workers` preserves current sequential behaviour exactly (no breaking change).
- Rate limiting by Google Photos is handled by retrying failed downloads once before marking them as failed; exponential backoff is out of scope.
- Windows filesystem restrictions on concurrent file writes to the same directory are assumed safe for the expected concurrency levels (≤ 8 workers).
- Pre-flight includes: verify destination path is absolute, create `YYYY/MM/DD/` folder if absent, and inventory existing files for skip detection.
