# CLI Contract: gphotos-sync (v3 — Performance Improvements)

**Branch**: `003-performance-improvements` | **Updated**: 2026-03-26

> **Changes from v2 (feature 002)**:
> - Added `--force` flag (re-download even if file exists)
> - Added `--workers N` flag (parallel downloads within a date)
> - Run summary gains a "Skipped" line
> - Stage timing lines added to log output

---

## New Arguments & Options

Added to existing flag set from v2:

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| `--force` | | flag | `false` | Re-download all photos even if they exist on disk |
| `--workers` | | int | `1` | Number of parallel download workers (1 = sequential, current behaviour) |

**Validation**: `--workers` must be ≥ 1; exit code 2 if < 1.

---

## Standard Output (updated)

### Single-profile run (normal, with skips)

```
gphotos-sync [personal]: 2026-03-24
  Downloaded: 12
  Skipped:    32
  Failed:      0
  Saved to:   C:/Users/User/photos/personal/2026/03/24/
```

### Single-profile run with `--verbose`

```
gphotos-sync [personal]: 2026-03-24
  + 2026/03/24/IMG_0001.jpg
  ~ 2026/03/24/IMG_0002.jpg (skipped — already exists)
  x 2026/03/24/IMG_0003.jpg (failed: download timeout)
  ...
  Downloaded: 11
  Skipped:    32
  Failed:      1
  Saved to:   C:/Users/User/photos/personal/2026/03/24/
```

**Verbose line prefixes**:
- `+` = downloaded
- `~` = skipped (file exists)
- `x` = failed

### Date-range run with skips

```
gphotos-sync [personal]: 2026-03-20 → 2026-03-24
  2026-03-20: Downloaded 12  Skipped  0  Failed 0
  2026-03-21: Downloaded  0  Skipped  8  Failed 0
  2026-03-22: Downloaded 31  Skipped  0  Failed 0
  2026-03-23: Downloaded  0  Skipped  0  Failed 0
  2026-03-24: Downloaded 19  Skipped  0  Failed 0
  Total downloaded: 62
  Total skipped:     8
  Total failed:      0
  Saved to:   C:/Users/User/photos/personal/
```

---

## Logging (new stage timing entries)

Stage elapsed times are emitted at INFO level to the log file (and stdout):

```
2026-03-26 08:00:01,000 [INFO   ] [personal] Stage 'pre-flight' completed in 0.2s
2026-03-26 08:00:12,000 [INFO   ] [personal] Stage 'collection' completed in 11.3s
2026-03-26 08:00:45,000 [INFO   ] [personal] Stage 'download' completed in 33.1s
```

---

## Standard Error (new entries)

```
ERROR: --workers must be at least 1
```
