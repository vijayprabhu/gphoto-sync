"""Download orchestration for gphotos-sync using Playwright browser automation."""
import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List

from .config import SyncConfig
from . import browser, scraper

_logger = logging.getLogger("gphotos_sync")


@dataclass
class SyncRun:
    profile_name: str
    dates: List[date]
    downloaded: int = 0
    failed: int = 0
    per_day: dict = field(default_factory=dict)  # date -> (downloaded, failed)


def run_sync(config: SyncConfig, profile_name: str) -> SyncRun:
    """Orchestrate a full sync for one profile: resolve dates, open browser, download."""
    effective_dates = _resolve_dates(config)
    run = SyncRun(profile_name=profile_name, dates=effective_dates)

    _logger.info("[%s] Sync started: %s", profile_name, effective_dates)

    pw, context = browser.ensure_session(config.token_dir, profile_name)
    try:
        for d in effective_dates:
            dl, fail = scraper.download_photos_for_date(
                context, d, config.destination, config.verbose
            )
            run.per_day[d] = (dl, fail)
            run.downloaded += dl
            run.failed += fail
            if fail:
                _logger.error(
                    "[%s] %d photo(s) failed to download for %s", profile_name, int(fail), d
                )
    finally:
        _logger.info(
            "[%s] Sync complete: downloaded=%s, failed=%s",
            profile_name, int(run.downloaded), int(run.failed),
        )
        browser.close_session(pw, context)

    return run


def _resolve_dates(config: SyncConfig) -> List[date]:
    """Return the ordered list of dates to process."""
    if config.date is not None:
        return [config.date]

    if config.start_date is not None and config.end_date is not None:
        dates = []
        current = config.start_date
        while current <= config.end_date:
            dates.append(current)
            current += timedelta(days=1)
        return dates

    # Default: apply date_offset from today.
    effective = date.today() + timedelta(days=config.date_offset)
    return [effective]
