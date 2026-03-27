# Research: Download New Photos from Google Photos

**Branch**: `001-gphotos-download-new` | **Date**: 2026-03-22

## Decision 1: Date Filtering Strategy

**Decision**: Use `mediaItems.search` with `dateFilter` (capture date) as the primary filter. Supplement with `mediaItems.list` + local sync-state tracking to catch late-synced items.

**Rationale**: The Google Photos Library API v1 does **not** expose an upload timestamp field (`uploadTime` does not exist in the API response). The `dateFilter` in `searchMediaItems` filters exclusively by the media item's `mediaMetadata.creationTime` (original capture date). There is no server-side upload-date filter. Therefore:

- **Capture date** → Covered via `searchMediaItems` with `dateFilter` for the target date range.
- **Upload date proxy** → Covered by maintaining a local sync-state file (`synced_ids.json`) that tracks already-downloaded item IDs. On each run, `mediaItems.list` is also queried (up to a configurable lookback window) and any item ID **not yet in the local state** is treated as newly uploaded, regardless of capture date. This is the closest practical approximation of "uploaded recently" given API constraints.

**Alternatives considered**:
- Filter by upload date server-side → **Not possible**: API exposes no upload timestamp.
- Use capture date only and ignore upload date → **Rejected**: Violates spec FR-002 and user clarification; late device syncs would be missed.
- Scrape `productUrl` timestamps → **Rejected**: Fragile, unofficial, and violates ToS.

---

## Decision 2: Python Client Library

**Decision**: Use `google-api-python-client` (`googleapiclient`) with direct REST calls to the Google Photos Library API v1.

**Rationale**: `google.apps.photoslibrary_v1` (used in the existing prototype) is not a standard Google-maintained package and has no reliable pip distribution. The stable, officially supported approach is `google-api-python-client` with `google-auth` and `google-auth-oauthlib`. This matches the standard pattern for all Google APIs in Python.

**Key packages**:
- `google-api-python-client` — HTTP client + service discovery
- `google-auth` — credential management and token refresh
- `google-auth-oauthlib` — OAuth 2.0 browser/device flow
- `google-api-core` — includes `Retry` for exponential backoff

**Alternatives considered**:
- `google-photos-library-api` (PyPI third-party) → **Rejected**: Community-maintained, no guarantee of stability or continued support.
- Direct `requests` calls to REST API → **Rejected**: Reinvents auth and retry logic already provided by `google-api-python-client`.

---

## Decision 3: Authentication Token Storage

**Decision**: Store OAuth2 credentials as a **JSON file** (`token.json`) inside a user-configurable config directory. The client secrets file (`credentials.json`) must also reside in the config directory.

**Rationale**: The existing prototype uses `pickle` (binary), which is a security risk — malicious pickle data can execute arbitrary code on deserialization. JSON is safe, human-readable, and portable. The `google-auth` library provides `Credentials.to_json()` and `Credentials.from_authorized_user_info()` methods that make JSON round-tripping straightforward.

**Multi-account support**: Each Google account gets its own config directory (e.g., `~/.gphotos-sync/account1/`, `~/.gphotos-sync/account2/`). The user selects the active account by passing `--config-dir` at runtime.

**Default config dir**: `~/.gphotos-sync/` (single account, no `--config-dir` needed).

**Alternatives considered**:
- System keychain (`python-keyring`) → **Not selected for v1**: Adds a dependency and complicates multi-account directory-based isolation; deferred to a future hardening phase.
- Pickle files → **Rejected**: Security risk; deprecated pattern.
- Re-authorize on every run → **Rejected**: Breaks scheduled/unattended operation.

---

## Decision 4: Exponential Backoff for Rate Limits

**Decision**: Use `google.api_core.retry.Retry` (from `google-api-core`) to wrap API calls with exponential backoff.

**Rationale**: `google-api-core` is already a transitive dependency of `google-api-python-client`. `Retry` provides configurable initial delay, multiplier, maximum delay, and total deadline. Applying it to the `searchMediaItems` and `mediaItems.list` calls handles HTTP 429 (rate limit) and 500/503 (transient server errors) transparently.

**Configuration**:
- Initial delay: 1s
- Multiplier: 2x
- Maximum delay: 60s
- Total deadline: configurable via `--max-backoff-seconds` (default: 300s / 5 minutes)

**Alternatives considered**:
- `tenacity` library → **Not selected**: Adds a dependency; `google-api-core` is already present.
- Manual `time.sleep` retry loop → **Rejected**: Error-prone, no jitter, harder to test.

---

## Decision 5: Pagination

**Decision**: Always paginate through all pages using `nextPageToken` from each API response. No client-side cap on total results.

**Rationale**: Spec FR-010 explicitly requires no per-run photo cap. The Google Photos API returns up to 100 items per page for `searchMediaItems` and `mediaItems.list`. The tool must loop until `nextPageToken` is absent.

---

## Decision 6: Local Sync State

**Decision**: Maintain a `synced_ids.json` file in the config directory that stores a set of already-downloaded media item IDs.

**Rationale**: Required to implement the upload-date proxy (Decision 1). Also enables idempotent re-runs — items already downloaded are skipped regardless of any duplicate filename edge cases.

**Format**: `{"synced_ids": ["id1", "id2", ...], "last_run": "2026-03-22T10:00:00Z"}`

---

## Decision 7: Download Organization

**Decision**: Save photos into a three-level `<destination>/YYYY/MM/DD/` hierarchy using `mediaMetadata.creationTime` (capture date). Construct paths using `pathlib.Path` to ensure platform-appropriate folder separators (`\` on Windows, `/` on Unix/macOS). Year, month, and day are zero-padded.

**Rationale**: Aligned with spec FR-003 and user clarification. A three-level hierarchy (year → month → day) scales better than a flat date folder for large libraries — browsing by month or year without opening every folder is natural. Using `pathlib.Path` ensures portability across Windows, macOS, and Linux without hardcoding a separator.

**Duplicate detection**: Skip download if `<destination>/<YYYY>/<MM>/<DD>/<filename>` already exists on disk (FR-004). Additionally skip if item ID is in `synced_ids.json`.

---

## Decision 8: Download Method

**Decision**: Use Python's `urllib.request` or `requests` library to download photo bytes from `baseUrl + "=d"`, replacing the existing `os.system("curl ...")` call.

**Rationale**: The existing code uses `os.system("curl ...")` which is a shell injection risk if filenames contain special characters. Using a Python HTTP library is safer, portable (no `curl` dependency), and compatible with the retry wrapper.
