# Data Model: Performance Improvements

**Branch**: `003-performance-improvements` | **Created**: 2026-03-26

---

## SyncRun (extended)

Represents the result of one complete sync run for a single profile.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `profile_name` | `str` | required | Profile name as specified by `--profile` |
| `dates` | `List[date]` | required | Ordered list of dates processed in this run |
| `downloaded` | `int` | `0` | Count of photos successfully downloaded |
| `skipped` | `int` | `0` | Count of photos skipped (file already exists, non-zero) |
| `failed` | `int` | `0` | Count of photos that failed to download |
| `per_day` | `dict[date, tuple[int,int,int]]` | `{}` | Per-date (downloaded, skipped, failed) counts |
| `stage_times` | `dict[str, float]` | `{}` | Elapsed seconds per stage name (pre-flight, collection, download) |

**Change from spec 002**: `per_day` values expand from `(downloaded, failed)` to `(downloaded, skipped, failed)`. `skipped` and `stage_times` are new fields.

---

## SyncConfig (extended)

CLI-parsed configuration for one sync run.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `token_dir` | `Path` | required | Absolute path to profile's session directory |
| `destination` | `Path` | required | Absolute path to profile's photo destination root |
| `date` | `Optional[date]` | `None` | Single target date (mutually exclusive with range) |
| `start_date` | `Optional[date]` | `None` | Range start (inclusive) |
| `end_date` | `Optional[date]` | `None` | Range end (inclusive) |
| `date_offset` | `int` | `-1` | Days offset from today when no date flag given |
| `verbose` | `bool` | `False` | Print per-photo progress lines |
| `force` | `bool` | `False` | Re-download all photos even if they already exist on disk |
| `workers` | `int` | `1` | Number of parallel download workers (1 = sequential) |

**New fields**: `force`, `workers`.

---

## Stage

A named, timed unit of work within a sync run. Not a persistent entity — exists only during runtime and is recorded in `SyncRun.stage_times`.

| Stage name | When it runs | What it does |
|------------|-------------|--------------|
| `pre-flight` | Before browser open | Creates `YYYY/MM/DD/` folders; inventories existing files per date |
| `collection` | After browser session established | Navigates to date URL; scrolls grid; collects all photo URLs |
| `download` | After collection | Downloads (or skips) each photo; runs parallel if `workers > 1` |

---

## Photo File (conceptual)

Not a persisted entity — represents a single photo on disk, identified for skip-detection purposes.

| Attribute | Source | Description |
|-----------|--------|-------------|
| `filename` | `page.title()` (stripped) or `download.suggested_filename` | e.g., `IMG_0001.jpg` |
| `dest_path` | `destination / YYYY / MM / DD / filename` | Full absolute path on disk |
| `exists` | `dest_path.exists()` | True if file is present on disk |
| `size_bytes` | `dest_path.stat().st_size` | 0 for incomplete downloads |
| `skip_eligible` | `exists and size_bytes > 0 and not force` | True = skip this photo |
