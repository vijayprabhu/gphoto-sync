"""Logging setup for gphotos-sync.

Configures a named logger with three handlers:
  - TimedRotatingFileHandler  → <log_dir>/gphotos-sync.log (daily, 7 days)
  - StreamHandler(stderr)     → WARNING and above
  - StreamHandler(stdout)     → INFO only

All handlers carry a RedactingFilter that masks token_dir paths and
playwright_state.json file paths so they never appear in log output.
"""
import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import List

_LOGGER_NAME = "gphotos_sync"
_LOG_FILENAME = "gphotos-sync.log"
_LOG_FORMAT = "%(asctime)s [%(levelname)-7s] %(message)s"
_SESSION_FILENAME = "playwright_state.json"


class RedactingFilter(logging.Filter):
    """Replace sensitive filesystem paths in log records before emission.

    Replaces:
      <token_dir>                              → <token_dir>
      <token_dir>/playwright_state.json        → <session_file>
      <token_dir>\\playwright_state.json       → <session_file>  (Windows)
    """

    def __init__(self, token_dirs: List[str]) -> None:
        super().__init__()
        self._token_dirs = token_dirs

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self._redact(str(record.msg))
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self._redact(str(v)) for k, v in record.args.items()}
            else:
                record.args = tuple(self._redact(str(a)) for a in record.args)
        return True

    def _redact(self, text: str) -> str:
        for td in self._token_dirs:
            # Redact session file first (more specific) then the directory.
            text = text.replace(td + os.sep + _SESSION_FILENAME, "<session_file>")
            text = text.replace(td + "/" + _SESSION_FILENAME, "<session_file>")
            text = text.replace(td, "<token_dir>")
        return text


class _InfoOnlyFilter(logging.Filter):
    """Pass only INFO-level records (block WARNING and above from stdout)."""

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno == logging.INFO


def setup_logging(
    verbose: bool,
    log_dir: Path,
    token_dirs: List[Path],
) -> logging.Logger:
    """Configure and return the gphotos_sync logger.

    Parameters
    ----------
    verbose:
        When True, the file handler emits DEBUG records and DEBUG messages
        are passed through. When False, the minimum level is INFO.
    log_dir:
        Directory where ``gphotos-sync.log`` is written.
        Typically the parent of the active config file (~/.gphotos-sync/).
    token_dirs:
        Absolute paths to each profile's token_dir. Used to build the
        RedactingFilter so sensitive paths never appear in log output.

    Returns
    -------
    logging.Logger
        The configured ``gphotos_sync`` logger. Callers in other modules
        should obtain their own reference via
        ``logging.getLogger("gphotos_sync")`` rather than storing the
        return value.
    """
    logger = logging.getLogger(_LOGGER_NAME)
    # Avoid adding duplicate handlers on repeated calls (e.g., in tests).
    if logger.handlers:
        return logger

    file_level = logging.DEBUG if verbose else logging.INFO
    logger.setLevel(logging.DEBUG)  # Master level — handlers filter further.

    token_dir_strs = [str(td) for td in token_dirs]
    redacting_filter = RedactingFilter(token_dir_strs)
    formatter = logging.Formatter(_LOG_FORMAT)

    # ------------------------------------------------------------------
    # 1. File handler — daily rotation, 7-day retention
    # ------------------------------------------------------------------
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / _LOG_FILENAME
    try:
        file_handler = logging.handlers.TimedRotatingFileHandler(
            filename=str(log_path),
            when="midnight",
            backupCount=7,
            encoding="utf-8",
        )
        file_handler.setLevel(file_level)
        file_handler.setFormatter(formatter)
        file_handler.addFilter(redacting_filter)
        logger.addHandler(file_handler)
    except OSError as exc:
        # Non-fatal — warn and continue with console-only output.
        logging.warning(
            "Log file unavailable: %s — continuing with console output only", exc
        )

    # ------------------------------------------------------------------
    # 2. stderr handler — WARNING and above
    # ------------------------------------------------------------------
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.WARNING)
    stderr_handler.setFormatter(formatter)
    stderr_handler.addFilter(redacting_filter)
    logger.addHandler(stderr_handler)

    # ------------------------------------------------------------------
    # 3. stdout handler — INFO only (run summaries; WARNING/ERROR go to stderr)
    # ------------------------------------------------------------------
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.INFO)
    stdout_handler.setFormatter(formatter)
    stdout_handler.addFilter(redacting_filter)
    stdout_handler.addFilter(_InfoOnlyFilter())
    logger.addHandler(stdout_handler)

    return logger
