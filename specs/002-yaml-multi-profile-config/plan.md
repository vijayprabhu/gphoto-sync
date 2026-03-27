# Implementation Plan: Logging for gphotos-sync

**Branch**: `002-yaml-multi-profile-config` | **Date**: 2026-03-26 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification — NFR-LOG-001 through NFR-LOG-005 (observability clarifications, Session 2026-03-26)

---

## Summary

Add structured logging to gphotos-sync. Every sync run writes to a daily-rotating log file at
`~/.gphotos-sync/gphotos-sync.log` (7-day retention) **and** continues emitting to stderr/stdout
as before. Four log levels are supported (DEBUG/INFO/WARNING/ERROR); DEBUG is activated by
`--verbose`. Sensitive path values (`token_dir`, `playwright_state.json` locations) are redacted
from all log output via a custom `logging.Filter`. Zero new dependencies — stdlib `logging` only.

---

## Technical Context

**Language/Version**: Python 3.9+
**Primary Dependencies**: `pyyaml>=6.0`, `playwright>=1.40.0` — logging uses stdlib only (no new dep)
**Storage**: Local filesystem — `~/.gphotos-sync/gphotos-sync.log` (daily rotation, 7 days)
**Testing**: `pytest` — unit tests for `logger.py` in `tests/unit/test_logger.py`
**Target Platform**: Windows 11 + Linux/macOS
**Project Type**: CLI tool
**Performance Goals**: Log write latency negligible (buffered I/O); no impact on sync throughput
**Constraints**: No new `requirements.txt` entries; Python 3.9 compatible; `TimedRotatingFileHandler` is stdlib since 2.4
**Scale/Scope**: Single user, typically 1–3 profiles, daily runs

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Single-Responsibility Modules | ✅ PASS | New `src/logger.py` for logging concern only; no existing module gains logging setup responsibility |
| II. Security-First Credential Handling | ✅ PASS | `token_dir` paths and `playwright_state.json` paths redacted from all log output (NFR-LOG-004); log file itself not a credential file |
| III. Idempotent Sync Operations | N/A | Logging does not affect download logic |
| IV. CLI Contract Compliance | ✅ PASS | File logging supplements — never replaces — stdout/stderr routing; INFO summaries still go to stdout, WARNING/ERROR still to stderr |
| V. Simplicity and YAGNI | ✅ PASS | stdlib `logging` only; no third-party library; `TimedRotatingFileHandler` handles all rotation requirements |

**Constitution deviation noted in research.md (Decision 11)**: Principle III (idempotent sync) is
waived by user choice — not affected by this logging feature.

---

## Project Structure

### Documentation (this feature)

```text
specs/002-yaml-multi-profile-config/
├── plan.md              # This file
├── research.md          # Decisions 13–15 added (logging library, redaction, module)
├── data-model.md        # LogFile + LogEntry entities added
├── quickstart.md        # Updated with log file location
├── contracts/
│   └── cli-contract.md  # Logging Behaviour section added
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code

```text
src/
├── logger.py            # NEW — logging setup, RedactingFilter, setup_logging()
├── photo_sync.py        # MODIFIED — call setup_logging() at start of main()
├── browser.py           # MODIFIED — replace print(stderr) with logger calls; redact paths
├── downloader.py        # MODIFIED — add INFO log at run start/end; ERROR on per-item failure
├── init.py              # MODIFIED — replace print(stderr) with logger calls
├── config.py            # No change
├── config_loader.py     # No change
└── scraper.py           # No change (scraper logs via downloader)

tests/
└── unit/
    ├── test_logger.py   # NEW — unit tests for setup_logging() and RedactingFilter
    └── (existing tests unchanged)
```

---

## Complexity Tracking

> No constitution violations requiring justification in this feature.

---

## Phase 0: Research

All unknowns resolved. See `research.md` Decisions 13–15.

| Unknown | Resolution |
|---|---|
| Logging library | stdlib `logging` — no new dependency (Decision 13) |
| Redaction approach | Custom `logging.Filter` subclass (Decision 14) |
| Module placement | New `src/logger.py` (Decision 15) |

---

## Phase 1: Design

### `src/logger.py` — public API

```python
def setup_logging(
    verbose: bool,
    log_dir: Path,
    token_dirs: list[Path],
) -> logging.Logger:
    """Configure and return the root gphotos-sync logger.

    Sets up:
    - TimedRotatingFileHandler: log_dir/gphotos-sync.log, daily, 7 backups
    - StreamHandler(stderr): WARNING and above
    - StreamHandler(stdout): INFO only
    - RedactingFilter on all handlers: masks token_dir paths and session file paths
    """
```

### `RedactingFilter` — internal

```python
class RedactingFilter(logging.Filter):
    """Replace sensitive paths in log records before emission."""

    def __init__(self, token_dirs: list[str]):
        self._token_dirs = token_dirs

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self._redact(str(record.msg))
        record.args = tuple(self._redact(str(a)) for a in record.args) if record.args else record.args
        return True

    def _redact(self, text: str) -> str:
        for td in self._token_dirs:
            text = text.replace(td + os.sep + "playwright_state.json", "<session_file>")
            text = text.replace(td, "<token_dir>")
        return text
```

### Handler routing

| Handler | Level filter | Destination |
|---|---|---|
| `TimedRotatingFileHandler` | `DEBUG` if `--verbose`, else `INFO` | `~/.gphotos-sync/gphotos-sync.log` |
| `StreamHandler` | `WARNING` | `sys.stderr` |
| `StreamHandler` | `INFO` only (custom filter to block WARNING+) | `sys.stdout` |

### Integration — `photo_sync.main()`

```python
# After pre-parsing --config and --profile, before any profile logic:
log_dir = pre_args.config.parent          # e.g., ~/.gphotos-sync/
token_dirs = _collect_token_dirs(config_data)   # list[Path] from all profiles
logger = setup_logging(
    verbose=("--verbose" in argv or "-v" in argv),
    log_dir=log_dir,
    token_dirs=token_dirs,
)
```

`_collect_token_dirs()` reads all profiles from `config_data` and extracts `token_dir` values —
called only after `load_config()` succeeds, so `config_data` is always a valid dict.

### Log write failure handling

`setup_logging()` wraps `TimedRotatingFileHandler` construction in a try/except. On `OSError`,
it emits `logging.warning("Log file unavailable: %s — continuing with console output only", exc)`
to stderr only (file handler not added) and returns without raising.

### Mandatory log events

Every call site uses the module-level logger `logging.getLogger("gphotos_sync")`:

| Where | Event | Call |
|---|---|---|
| `downloader.run_sync()` | Run start | `logger.info("[%s] Sync started: %s", profile, date)` |
| `downloader.run_sync()` | Run complete | `logger.info("[%s] Sync complete: downloaded=%d, failed=%d", profile, dl, fail)` |
| `downloader.run_sync()` | Per-photo failure | `logger.error("[%s] FAILED: %s — %s", profile, filename, reason)` |
| `browser.ensure_session()` | No session | `logger.info("[%s] No saved session — opening browser for login", profile)` |
| `browser.ensure_session()` | Session expired | `logger.warning("[%s] Session expired — re-authenticating", profile)` |
| `browser._login_headed()` | Login success | `logger.info("[%s] Login successful, session saved", profile)` |
| `init._ensure_chromium()` | Install triggered | `logger.info("Chromium not found — installing via playwright install chromium")` |

Existing `print(..., file=sys.stderr)` calls in `browser.py` and `init.py` are **replaced** with
logger calls. `print()` to stdout in `photo_sync.py` (run summaries) is **kept** — those are
user-facing output, not log events.

---

## Phase 1: Contracts & Artifacts Updated

| Artifact | Change |
|---|---|
| `research.md` | Decisions 13, 14, 15 added |
| `data-model.md` | `LogFile` and `LogEntry` entities added; file layout updated |
| `contracts/cli-contract.md` | `## Logging Behaviour` section added |
| `specs/002-yaml-multi-profile-config/quickstart.md` | Log file location noted in setup section |

---

## Post-Design Constitution Re-Check

All gates remain PASS. No new violations introduced by the design.

- `src/logger.py` has exactly one concern: logging setup and redaction.
- `photo_sync.py` gains one call to `setup_logging()` — within its existing CLI orchestration responsibility.
- `browser.py` and `downloader.py` gain logger calls — replacing existing `print(stderr)` patterns, not new responsibilities.
- No new entries in `requirements.txt`.
