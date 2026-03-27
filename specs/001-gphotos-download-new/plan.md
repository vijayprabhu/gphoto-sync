# Implementation Plan: Download New Photos from Google Photos

**Branch**: `001-gphotos-download-new` | **Date**: 2026-03-22 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-gphotos-download-new/spec.md`

## Summary

Enhance the existing `src/photo_sync.py` prototype into a production-quality CLI tool that downloads photos from Google Photos where either the capture date or upload date falls within a configurable range (defaulting to yesterday and today). Photos are saved into a `YYYY/MM/DD` three-level folder hierarchy using platform-appropriate separators (`pathlib.Path`). Key improvements over the prototype: safe JSON-based credential storage, configurable config directory for multi-account support, three-level date folder organization, full API pagination (no photo cap), exponential backoff on rate limits, resilient per-item error handling, and a structured run summary. Uses `google-api-python-client` (replacing the non-standard `google.apps.photoslibrary_v1` import) and a local `synced_ids.json` sync-state file to approximate upload-date filtering, which the Google Photos API does not expose natively.

## Technical Context

**Language/Version**: Python 3.9+
**Primary Dependencies**: `google-api-python-client`, `google-auth`, `google-auth-oauthlib`, `google-api-core` (for `Retry`), `requests`
**Storage**: Local filesystem — credential JSON files in config dir; downloaded photos in `YYYY/MM/DD` subfolders; `synced_ids.json` sync state in config dir
**Testing**: `pytest`
**Target Platform**: Cross-platform CLI (Windows, macOS, Linux)
**Project Type**: CLI tool
**Performance Goals**: ≤5 minutes per 100 photos on standard broadband; unlimited total photos per run
**Constraints**: No photo cap per run; configurable config dir; safe credential storage (JSON, not pickle); no shell injection (no `os.system`); platform-appropriate path separators via `pathlib.Path`
**Scale/Scope**: Single user per invocation; multiple accounts supported via separate config dirs

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The project constitution (`constitution.md`) contains only unfilled template placeholders — no binding principles have been ratified. **No gates apply.** Proceeding without restrictions.

*Post-design re-check*: No violations introduced. Design follows standard Python CLI patterns (single module entry point, `pytest`, filesystem-only storage, `pathlib.Path` for cross-platform paths).

## Project Structure

### Documentation (this feature)

```text
specs/001-gphotos-download-new/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── cli-contract.md  # CLI interface contract
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/
├── photo_sync.py        # CLI entry point (refactored from prototype)
├── auth.py              # OAuth2 authentication + token JSON storage
├── client.py            # Google Photos API wrapper (search + list + pagination + retry)
├── downloader.py        # Per-item download logic (pathlib paths, subfolder creation, skip logic)
└── config.py            # SyncConfig dataclass; CLI argument parsing

tests/
├── unit/
│   ├── test_auth.py
│   ├── test_client.py
│   ├── test_downloader.py
│   └── test_config.py
└── integration/
    └── test_sync.py
```

**Structure Decision**: Single project layout. The existing prototype is a single file; the refactored version splits into four focused modules plus a CLI entry point. No backend/frontend split needed — this is a pure CLI tool. All file path construction uses `pathlib.Path` for cross-platform compatibility.

## Complexity Tracking

No constitution violations to justify. Design is intentionally simple.
