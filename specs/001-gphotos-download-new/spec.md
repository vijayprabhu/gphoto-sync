# Feature Specification: Download New Photos from Google Photos

**Feature Branch**: `001-gphotos-download-new`
**Created**: 2026-03-22
**Status**: Draft
**Input**: User description: "Download New Photos from Google Photos. Goal is to download photos that were uploaded yesterday today"

## Clarifications

### Session 2026-03-22

- Q: Should the date filter be based on upload date or capture date? → A: Both — include a photo if either its upload date or original capture date falls within the target range (device syncs can be delayed).
- Q: Where should authentication tokens be stored after initial authorization? → A: Local config file; the config directory must be user-configurable to support running syncs for multiple Google accounts.
- Q: What should the tool do when it hits a Google API rate limit? → A: Wait and retry automatically with exponential backoff (up to a configurable maximum wait), so unattended/scheduled runs can complete without user intervention.
- Q: When two different photos would download to the same filename, what should happen? → A: Place photos in date-based subfolders (by capture date) under the local destination, so filename collisions across different dates are naturally avoided.
- Q: Should the tool enforce a per-run photo limit or process all matching photos? → A: No limit — paginate through all API results and download every photo in the target date range, regardless of count.
- Q: How should the local folder hierarchy be structured for downloaded photos? → A: Use a three-level hierarchy — `YYYY/MM/DD` — based on the photo's capture date. Use the platform-appropriate folder separator character (not hardcoded `/`).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Download Yesterday's Newly Uploaded Photos (Priority: P1)

A user runs the sync tool and it automatically identifies all photos uploaded to Google Photos on the previous calendar day, then downloads any that do not already exist locally.

**Why this priority**: This is the core stated goal — fetch photos uploaded "yesterday" to keep a local archive up to date on a daily cadence.

**Independent Test**: Can be fully tested by running the sync command after ensuring at least one photo was uploaded to Google Photos the previous day; the tool downloads exactly those photos and no others.

**Acceptance Scenarios**:

1. **Given** photos were uploaded to Google Photos yesterday and do not exist locally, **When** the user runs the sync command, **Then** all photos uploaded yesterday are downloaded to the configured local folder.
2. **Given** a photo uploaded yesterday already exists locally (same filename), **When** the user runs the sync command, **Then** that photo is skipped and not re-downloaded.
3. **Given** no photos were uploaded to Google Photos yesterday, **When** the user runs the sync command, **Then** the tool reports zero new photos found and exits successfully.

---

### User Story 2 - Download Today's Newly Uploaded Photos (Priority: P2)

A user runs the sync tool mid-day and it downloads all photos uploaded to Google Photos so far today that are not yet present locally.

**Why this priority**: The description explicitly mentions "yesterday today", meaning the tool should also support downloading photos uploaded on the current calendar day, enabling intra-day syncing.

**Independent Test**: Can be fully tested by uploading a photo to Google Photos today and running the sync; the photo appears locally without requiring a full library scan.

**Acceptance Scenarios**:

1. **Given** photos were uploaded to Google Photos today and do not exist locally, **When** the user runs the sync command, **Then** all photos uploaded today are downloaded to the configured local folder.
2. **Given** the same photo has already been downloaded from an earlier run today, **When** the user runs the sync command again, **Then** the photo is skipped (idempotent behavior).

---

### User Story 3 - Sync Reporting & Visibility (Priority: P3)

The user receives a clear summary of what was downloaded, skipped, and whether any errors occurred during the sync run.

**Why this priority**: Observability of sync results lets users confirm the tool is working correctly and diagnose issues without debugging logs.

**Independent Test**: Can be tested independently by running the sync and verifying the printed summary matches the actual files downloaded.

**Acceptance Scenarios**:

1. **Given** a completed sync run, **When** the run finishes, **Then** the tool outputs a summary showing: total photos found, total downloaded, total skipped (already exist), and any errors.
2. **Given** a photo fails to download (e.g., network error), **When** the run finishes, **Then** the tool reports that photo as failed without halting the entire sync.

---

### Edge Cases

- What happens when the local destination folder does not exist or is not writable?
- How does the system handle photos uploaded exactly at midnight (ambiguous day boundary)?
- What happens when the Google Photos service is temporarily unavailable mid-sync?
- Photos are organized into a `YYYY/MM/DD` three-level folder hierarchy by capture date using the platform-appropriate separator, so filename collisions across different dates are naturally avoided. Within the same day folder, duplicate filenames are skipped.
- What happens when available disk space is insufficient to complete the download?
- The tool paginates through all API results with no per-run photo cap; large batches (hundreds of photos) are fully processed in a single run.
- If the Google API rate limit is hit and the maximum backoff wait is exhausted, the in-progress request is treated as failed and reported in the run summary; remaining photos are still attempted.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST authenticate with Google Photos on behalf of the user before accessing any photo data.
- **FR-001a**: System MUST store authentication tokens in a local config file within a user-configurable config directory, enabling independent credentials for multiple Google accounts on the same machine.
- **FR-001b**: System MUST support specifying a config directory at runtime (e.g., via a command-line argument or environment variable) so that different accounts can be targeted by separate sync runs.
- **FR-002**: System MUST retrieve all photos from Google Photos where either the upload date or the original capture date falls within the target date range (defaulting to yesterday and today), so that photos synced late from a device are not missed.
- **FR-003**: System MUST download each retrieved photo into a three-level date hierarchy under the local destination (`<destination>/YYYY/MM/DD/`), derived from the photo's original capture date, using the platform-appropriate folder separator character.
- **FR-004**: System MUST skip downloading a photo if a file with the same name already exists within the same date subfolder (duplicate prevention).
- **FR-005**: System MUST report a summary at the end of each run including: count of photos found, downloaded, skipped, and failed.
- **FR-006**: System MUST continue downloading remaining photos if a single photo download fails, and report the failure without aborting the run.
- **FR-009**: System MUST detect Google API rate limit responses and automatically retry the request using exponential backoff, up to a configurable maximum total wait time, before treating the request as failed.
- **FR-010**: System MUST paginate through all API result pages to retrieve every matching photo in the target date range, with no per-run cap on the number of photos processed.
- **FR-007**: System MUST preserve original filenames as provided by Google Photos when saving locally.
- **FR-008**: System MUST support running as a scheduled or on-demand command-line operation.

### Key Entities

- **Photo**: A media item (image or video) stored in Google Photos; identified by a unique media ID, filename, original capture timestamp, and upload timestamp. A photo is included in a sync run if either timestamp falls within the target date range.
- **Sync Run**: A single execution of the download process; tracks date range targeted, photos found, downloaded, skipped, and failed counts.
- **Local Destination**: The root folder path where downloaded photos are saved; configured by the user. Photos are organized within it into a `YYYY/MM/DD` three-level hierarchy using the photo's original capture date and the platform-appropriate folder separator.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All photos in the target date range are downloaded within 5 minutes per 100 photos on a standard broadband connection, with no upper bound on total photos processed per run.
- **SC-002**: Zero duplicate downloads occur across repeated sync runs for the same date range — previously downloaded photos are always skipped.
- **SC-003**: The sync tool completes successfully even when one or more individual photo downloads fail; failures are reported but do not abort the run.
- **SC-004**: Users can determine the outcome of a sync run (what was downloaded, skipped, or failed) from the tool's output alone, without inspecting log files or source code.

## Assumptions

- The user has one or more valid Google accounts with Google Photos access and is able to complete an authorization flow (e.g., browser-based consent) for each account. Each account uses its own config directory containing its credentials file.
- Multiple accounts on the same machine are supported by pointing each sync run at a different config directory.
- "Yesterday" and "today" are interpreted in the local system timezone of the machine running the tool.
- The local destination folder is expected to exist and be writable; the tool reports an error if it is not, rather than creating the folder automatically.
- Duplicate detection is based on filename matching only; content-based deduplication (hash comparison) is out of scope for the initial version.
- The feature targets photos and videos only; shared content from other users and archived items are out of scope unless explicitly included.
- There is no per-run photo cap; the tool processes all matching photos regardless of count by paginating through all API results.
