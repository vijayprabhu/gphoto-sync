"""Unit tests for src/logger.py — RedactingFilter and setup_logging()."""
import logging
import os
import sys
from pathlib import Path

import pytest

from src.logger import RedactingFilter, _InfoOnlyFilter, setup_logging


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_record(msg: str, args=None, level=logging.INFO) -> logging.LogRecord:
    record = logging.LogRecord(
        name="gphotos_sync",
        level=level,
        pathname="",
        lineno=0,
        msg=msg,
        args=args or (),
        exc_info=None,
    )
    return record


# ---------------------------------------------------------------------------
# RedactingFilter
# ---------------------------------------------------------------------------

class TestRedactingFilter:
    def test_redacts_token_dir(self, tmp_path):
        td = str(tmp_path / "sessions" / "personal")
        f = RedactingFilter([td])
        record = _make_record(f"Session at {td} is ready")
        f.filter(record)
        assert "<token_dir>" in record.msg
        assert td not in record.msg

    def test_redacts_session_file_path(self, tmp_path):
        td = str(tmp_path / "sessions" / "personal")
        session_file = td + os.sep + "playwright_state.json"
        f = RedactingFilter([td])
        record = _make_record(f"Saved to {session_file}")
        f.filter(record)
        assert "<session_file>" in record.msg
        assert "playwright_state.json" not in record.msg
        assert td not in record.msg

    def test_session_file_redacted_before_dir(self, tmp_path):
        """Ensure the session file placeholder is used, not just <token_dir>/playwright_state.json."""
        td = str(tmp_path / "sessions" / "work")
        session_file = td + os.sep + "playwright_state.json"
        f = RedactingFilter([td])
        record = _make_record(session_file)
        f.filter(record)
        assert record.msg == "<session_file>"

    def test_unrelated_strings_pass_through(self, tmp_path):
        td = str(tmp_path / "sessions" / "personal")
        f = RedactingFilter([td])
        record = _make_record("Sync started: 2026-03-26")
        f.filter(record)
        assert record.msg == "Sync started: 2026-03-26"

    def test_redacts_args_tuple(self, tmp_path):
        td = str(tmp_path / "sessions" / "personal")
        f = RedactingFilter([td])
        record = _make_record("Path: %s", args=(td,))
        f.filter(record)
        assert "<token_dir>" in record.args[0]
        assert td not in record.args[0]

    def test_redacts_multiple_token_dirs(self, tmp_path):
        td1 = str(tmp_path / "personal")
        td2 = str(tmp_path / "work")
        f = RedactingFilter([td1, td2])
        record = _make_record(f"personal={td1} work={td2}")
        f.filter(record)
        assert td1 not in record.msg
        assert td2 not in record.msg
        assert record.msg.count("<token_dir>") == 2

    def test_empty_token_dirs(self):
        f = RedactingFilter([])
        record = _make_record("nothing to redact")
        result = f.filter(record)
        assert result is True
        assert record.msg == "nothing to redact"


# ---------------------------------------------------------------------------
# _InfoOnlyFilter
# ---------------------------------------------------------------------------

class TestInfoOnlyFilter:
    def test_passes_info(self):
        f = _InfoOnlyFilter()
        assert f.filter(_make_record("msg", level=logging.INFO)) is True

    def test_blocks_warning(self):
        f = _InfoOnlyFilter()
        assert f.filter(_make_record("msg", level=logging.WARNING)) is False

    def test_blocks_error(self):
        f = _InfoOnlyFilter()
        assert f.filter(_make_record("msg", level=logging.ERROR)) is False

    def test_blocks_debug(self):
        f = _InfoOnlyFilter()
        assert f.filter(_make_record("msg", level=logging.DEBUG)) is False


# ---------------------------------------------------------------------------
# setup_logging()
# ---------------------------------------------------------------------------

class TestSetupLogging:
    @pytest.fixture(autouse=True)
    def reset_logger(self):
        """Remove all handlers from the gphotos_sync logger between tests."""
        logger = logging.getLogger("gphotos_sync")
        yield
        for h in list(logger.handlers):
            logger.removeHandler(h)
            h.close()

    def test_returns_logger(self, tmp_path):
        logger = setup_logging(verbose=False, log_dir=tmp_path, token_dirs=[])
        assert logger.name == "gphotos_sync"

    def test_log_file_created(self, tmp_path):
        setup_logging(verbose=False, log_dir=tmp_path, token_dirs=[])
        assert (tmp_path / "gphotos-sync.log").exists()

    def test_info_handler_is_stdout(self, tmp_path):
        setup_logging(verbose=False, log_dir=tmp_path, token_dirs=[])
        logger = logging.getLogger("gphotos_sync")
        stdout_handlers = [
            h for h in logger.handlers
            if isinstance(h, logging.StreamHandler) and h.stream is sys.stdout
        ]
        assert len(stdout_handlers) == 1

    def test_warning_handler_is_stderr(self, tmp_path):
        setup_logging(verbose=False, log_dir=tmp_path, token_dirs=[])
        logger = logging.getLogger("gphotos_sync")
        stderr_handlers = [
            h for h in logger.handlers
            if isinstance(h, logging.StreamHandler) and h.stream is sys.stderr
        ]
        assert len(stderr_handlers) == 1
        assert stderr_handlers[0].level == logging.WARNING

    def test_stdout_handler_has_info_only_filter(self, tmp_path):
        setup_logging(verbose=False, log_dir=tmp_path, token_dirs=[])
        logger = logging.getLogger("gphotos_sync")
        stdout_handlers = [
            h for h in logger.handlers
            if isinstance(h, logging.StreamHandler) and h.stream is sys.stdout
        ]
        assert any(isinstance(f, _InfoOnlyFilter) for f in stdout_handlers[0].filters)

    def test_all_handlers_have_redacting_filter(self, tmp_path):
        token_dir = tmp_path / "sessions" / "personal"
        setup_logging(verbose=False, log_dir=tmp_path, token_dirs=[token_dir])
        logger = logging.getLogger("gphotos_sync")
        for handler in logger.handlers:
            assert any(isinstance(f, RedactingFilter) for f in handler.filters), (
                f"Handler {handler} is missing RedactingFilter"
            )

    def test_debug_suppressed_without_verbose(self, tmp_path):
        setup_logging(verbose=False, log_dir=tmp_path, token_dirs=[])
        logger = logging.getLogger("gphotos_sync")
        file_handlers = [
            h for h in logger.handlers
            if isinstance(h, logging.handlers.TimedRotatingFileHandler)
        ]
        assert file_handlers[0].level == logging.INFO

    def test_debug_enabled_with_verbose(self, tmp_path):
        setup_logging(verbose=True, log_dir=tmp_path, token_dirs=[])
        logger = logging.getLogger("gphotos_sync")
        file_handlers = [
            h for h in logger.handlers
            if isinstance(h, logging.handlers.TimedRotatingFileHandler)
        ]
        assert file_handlers[0].level == logging.DEBUG

    def test_idempotent_no_duplicate_handlers(self, tmp_path):
        setup_logging(verbose=False, log_dir=tmp_path, token_dirs=[])
        setup_logging(verbose=False, log_dir=tmp_path, token_dirs=[])
        logger = logging.getLogger("gphotos_sync")
        assert len(logger.handlers) == 3  # file + stderr + stdout — not 6

    def test_log_dir_created_if_missing(self, tmp_path):
        log_dir = tmp_path / "new" / "nested" / "dir"
        setup_logging(verbose=False, log_dir=log_dir, token_dirs=[])
        assert log_dir.exists()

    def test_unwritable_log_dir_is_nonfatal(self, tmp_path, monkeypatch):
        """If the file handler cannot be created, setup_logging must not raise."""
        import logging.handlers as lh

        def bad_init(*args, **kwargs):
            raise OSError("permission denied")

        monkeypatch.setattr(lh, "TimedRotatingFileHandler", bad_init)
        # Should not raise — falls back to console-only.
        logger = setup_logging(verbose=False, log_dir=tmp_path, token_dirs=[])
        assert logger is not None
