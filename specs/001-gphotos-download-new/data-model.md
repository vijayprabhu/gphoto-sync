# Data Model: Download New Photos from Google Photos

**Branch**: `001-gphotos-download-new` | **Date**: 2026-03-22

## Entities

### MediaItem (from Google Photos API)

Represents a photo or video retrieved from the Google Photos Library API.

| Field | Type | Source | Notes |
|---|---|---|---|
| `id` | string | API | Unique stable identifier for the media item |
| `filename` | string | API | Original filename as stored in Google Photos |
| `mimeType` | string | API | e.g., `image/jpeg`, `video/mp4` |
| `baseUrl` | string | API | Short-lived URL for downloading; append `=d` for original quality |
| `productUrl` | string | API | Link to item in Google Photos UI |
| `mediaMetadata.creationTime` | RFC3339 string | API | Original capture timestamp (used for date filtering and subfolder naming) |
| `mediaMetadata.width` | string | API | Width in pixels |
| `mediaMetadata.height` | string | API | Height in pixels |

**Identity rule**: Items are uniquely identified by `id`. Two items with the same `filename` but different `id` values are distinct photos.

**Note**: No `uploadTime` field exists in the API response. Upload-date filtering is approximated via local sync state (see `SyncState`).

---

### SyncConfig

User-provided configuration for a single sync run. Resolved from CLI arguments with defaults applied.

| Field | Type | Default | Notes |
|---|---|---|---|
| `config_dir` | path | `~/.gphotos-sync/` | Directory containing `credentials.json` and `token.json` |
| `destination` | path | (required) | Root folder where photos are downloaded |
| `date_from` | date | yesterday (local TZ) | Start of target date range (inclusive), based on capture date |
| `date_to` | date | today (local TZ) | End of target date range (inclusive), based on capture date |
| `max_backoff_seconds` | int | 300 | Maximum total wait time during exponential backoff retries |
| `lookback_pages` | int | 5 | Number of pages to scan in `mediaItems.list` for upload-date proxy |

---

### SyncState

Persisted state file stored at `<config_dir>/synced_ids.json`. Tracks which items have been downloaded to support idempotent re-runs and the upload-date proxy.

| Field | Type | Notes |
|---|---|---|
| `synced_ids` | list[string] | Media item IDs that have been successfully downloaded |
| `last_run` | RFC3339 string | Timestamp of the last successful sync run |

**Lifecycle**:
1. Loaded at the start of each run (empty if file doesn't exist).
2. Updated incrementally as each item is successfully downloaded.
3. Written to disk after each successful download (durable against mid-run failures).

**Growth management**: The list grows unboundedly in v1. Pruning old IDs is a future concern.

---

### SyncRun

In-memory record of a single sync run's results. Written to stdout as a summary on completion.

| Field | Type | Notes |
|---|---|---|
| `started_at` | datetime | When the run began |
| `date_from` | date | Target range start |
| `date_to` | date | Target range end |
| `found` | int | Total unique media items found in range |
| `downloaded` | int | Successfully downloaded this run |
| `skipped` | int | Already existed locally or in sync state |
| `failed` | list[FailedItem] | Items that failed to download after retries |

---

### FailedItem

Represents a single photo/video that could not be downloaded during a run.

| Field | Type | Notes |
|---|---|---|
| `item_id` | string | Media item ID |
| `filename` | string | Original filename |
| `error` | string | Human-readable error description |

---

### Credentials (file: `token.json`)

Persisted OAuth2 credential state, stored as JSON in the config directory.

Serialized using `google.oauth2.credentials.Credentials.to_json()` / `from_authorized_user_info()`.

| Field | Notes |
|---|---|
| `token` | Current access token |
| `refresh_token` | Long-lived refresh token |
| `token_uri` | Google token endpoint |
| `client_id` | From `credentials.json` |
| `client_secret` | From `credentials.json` |
| `scopes` | `["https://www.googleapis.com/auth/photoslibrary.readonly"]` |

---

## State Transitions

### MediaItem Download Lifecycle

```
NOT_SEEN → FOUND → DOWNLOADED
                 → SKIPPED (already exists on disk or in synced_ids)
                 → FAILED (download error after retries exhausted)
```

### Auth Token Lifecycle

```
MISSING → AUTHORIZE (browser flow) → VALID
VALID   → AUTO_REFRESH (on expiry)  → VALID
VALID   → EXPIRED (refresh failed)  → AUTHORIZE (browser flow)
```

---

## File Layout on Disk

```
<config_dir>/
├── credentials.json      # OAuth client secrets (user-provided, never modified)
├── token.json            # OAuth tokens (written/updated by tool)
└── synced_ids.json       # Sync state (written/updated by tool)

<destination>/
└── 2026/
    └── 03/
        ├── 21/
        │   ├── IMG_0001.jpg
        │   └── IMG_0002.jpg
        └── 22/
            ├── IMG_0003.jpg
            └── VID_0001.mp4
```

**Note**: Folder paths are constructed using `pathlib.Path` (or `os.path.join`) to ensure platform-appropriate separators (`\` on Windows, `/` on Unix). Year, month, and day components are zero-padded (e.g., `03`, `22`).
