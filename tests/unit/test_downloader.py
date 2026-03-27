"""Unit tests for src/downloader.py — _resolve_dates and run_sync."""
import pytest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.config import SyncConfig
from src.downloader import SyncRun, run_sync, _resolve_dates


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _config(tmp_path, **kwargs):
    defaults = {
        "token_dir": tmp_path / "token",
        "destination": tmp_path / "photos",
        "date": None,
        "start_date": None,
        "end_date": None,
        "date_offset": -1,
        "verbose": False,
    }
    defaults.update(kwargs)
    return SyncConfig(**defaults)


# ---------------------------------------------------------------------------
# _resolve_dates — single date
# ---------------------------------------------------------------------------

def test_resolve_dates_single_date(tmp_path):
    config = _config(tmp_path, date=date(2026, 3, 24))
    assert _resolve_dates(config) == [date(2026, 3, 24)]


# ---------------------------------------------------------------------------
# _resolve_dates — date range
# ---------------------------------------------------------------------------

def test_resolve_dates_range_inclusive(tmp_path):
    config = _config(
        tmp_path,
        start_date=date(2026, 3, 20),
        end_date=date(2026, 3, 22),
    )
    result = _resolve_dates(config)
    assert result == [date(2026, 3, 20), date(2026, 3, 21), date(2026, 3, 22)]


def test_resolve_dates_single_day_range(tmp_path):
    config = _config(
        tmp_path,
        start_date=date(2026, 3, 22),
        end_date=date(2026, 3, 22),
    )
    assert _resolve_dates(config) == [date(2026, 3, 22)]


# ---------------------------------------------------------------------------
# _resolve_dates — default via date_offset
# ---------------------------------------------------------------------------

def test_resolve_dates_default_uses_date_offset(tmp_path):
    config = _config(tmp_path, date_offset=-1)
    result = _resolve_dates(config)
    expected = [date.today() + timedelta(days=-1)]
    assert result == expected


def test_resolve_dates_date_offset_zero_is_today(tmp_path):
    config = _config(tmp_path, date_offset=0)
    assert _resolve_dates(config) == [date.today()]


# ---------------------------------------------------------------------------
# run_sync — successful single-day run
# ---------------------------------------------------------------------------

def test_run_sync_single_day_returns_syncrun(tmp_path):
    config = _config(tmp_path, date=date(2026, 3, 24))
    mock_pw = MagicMock()
    mock_context = MagicMock()

    with patch("src.downloader.browser.ensure_session", return_value=(mock_pw, mock_context)), \
         patch("src.downloader.scraper.download_photos_for_date", return_value=(5, 0)), \
         patch("src.downloader.browser.close_session"):

        run = run_sync(config, "personal")

    assert run.downloaded == 5
    assert run.failed == 0
    assert run.profile_name == "personal"
    assert run.dates == [date(2026, 3, 24)]


# ---------------------------------------------------------------------------
# run_sync — range accumulates per-day counts
# ---------------------------------------------------------------------------

def test_run_sync_range_accumulates_totals(tmp_path):
    config = _config(
        tmp_path,
        start_date=date(2026, 3, 20),
        end_date=date(2026, 3, 22),
    )
    mock_pw = MagicMock()
    mock_context = MagicMock()
    day_results = [(3, 0), (5, 1), (2, 0)]

    with patch("src.downloader.browser.ensure_session", return_value=(mock_pw, mock_context)), \
         patch("src.downloader.scraper.download_photos_for_date", side_effect=day_results), \
         patch("src.downloader.browser.close_session"):

        run = run_sync(config, "work")

    assert run.downloaded == 10
    assert run.failed == 1
    assert len(run.per_day) == 3


def test_run_sync_per_day_values_correct(tmp_path):
    config = _config(
        tmp_path,
        start_date=date(2026, 3, 20),
        end_date=date(2026, 3, 21),
    )
    mock_pw = MagicMock()
    mock_context = MagicMock()

    with patch("src.downloader.browser.ensure_session", return_value=(mock_pw, mock_context)), \
         patch("src.downloader.scraper.download_photos_for_date", side_effect=[(7, 0), (3, 2)]), \
         patch("src.downloader.browser.close_session"):

        run = run_sync(config, "personal")

    assert run.per_day[date(2026, 3, 20)] == (7, 0)
    assert run.per_day[date(2026, 3, 21)] == (3, 2)


# ---------------------------------------------------------------------------
# run_sync — session always closed on error
# ---------------------------------------------------------------------------

def test_run_sync_closes_session_on_scraper_error(tmp_path):
    config = _config(tmp_path, date=date(2026, 3, 24))
    mock_pw = MagicMock()
    mock_context = MagicMock()

    with patch("src.downloader.browser.ensure_session", return_value=(mock_pw, mock_context)), \
         patch("src.downloader.scraper.download_photos_for_date", side_effect=RuntimeError("crash")), \
         patch("src.downloader.browser.close_session") as mock_close:

        with pytest.raises(RuntimeError):
            run_sync(config, "personal")

    mock_close.assert_called_once_with(mock_pw, mock_context)
