"""Google Photos web scraper for gphotos-sync.

Navigates to a date-filtered view, scrolls to reveal all photos, and downloads
each one using the Shift+D keyboard shortcut with Playwright's download interception.
"""
import logging
import sys
from datetime import date
from pathlib import Path

from playwright.sync_api import BrowserContext, Download

_logger = logging.getLogger("gphotos_sync")

_PHOTOS_SEARCH_URL = "https://photos.google.com/search/{query}"
_DOWNLOAD_TIMEOUT_MS = 60_000
_SCROLL_PAUSE_MS = 1_500
_MAX_SCROLL_ATTEMPTS = 60


def download_photos_for_date(
    context: BrowserContext,
    target_date: date,
    destination: Path,
    verbose: bool = False,
) -> tuple[int, int]:
    """Download all photos for ``target_date`` into ``destination/YYYY/MM/DD/``.

    Returns ``(downloaded_count, failed_count)``.
    """
    date_str = target_date.strftime("%Y-%m-%d")
    url = f"https://photos.google.com/search/date%3A{date_str}"

    dest_dir = destination / target_date.strftime("%Y") / target_date.strftime("%m") / target_date.strftime("%d")
    dest_dir.mkdir(parents=True, exist_ok=True)

    page = context.new_page()
    downloaded = 0
    failed = 0

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        try:
            page.wait_for_load_state("networkidle", timeout=15_000)
        except Exception:
            pass

        photo_urls = _collect_photo_urls(page)
        total = len(photo_urls)
        _logger.info("[%s] Found %s photo(s) for %s", "scraper", total, target_date)

        for idx, photo_url in enumerate(photo_urls):
            _logger.info("[%s] Downloading photo %d/%d", "scraper", idx + 1, total)
            filename, ok = _download_one(context, photo_url, dest_dir, idx, verbose)
            if ok:
                _logger.info("[%s] Saved %s (%s/%s)", "scraper", filename, int(idx) + 1, total)
                downloaded += 1
            else:
                failed += 1
    finally:
        page.close()

    return downloaded, failed


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _collect_photo_urls(page) -> list:
    """Scroll the virtualized photo grid and collect all photo detail-view URLs."""
    seen: set = set()
    urls: list = []
    no_new_count = 0

    for _ in range(_MAX_SCROLL_ATTEMPTS):
        anchors = page.query_selector_all("a[href*='/photo/']")
        new_found = False
        for anchor in anchors:
            href = anchor.get_attribute("href")
            if href and href not in seen:
                seen.add(href)
                # Normalise to absolute URL.
                if href.startswith("/"):
                    href = "https://photos.google.com" + href
                elif not href.startswith("http"):
                    href = "https://photos.google.com/" + href.lstrip("./")
                urls.append(href)
                new_found = True

        if not new_found:
            no_new_count += 1
            if no_new_count >= 3:
                break
        else:
            no_new_count = 0

        page.evaluate("window.scrollBy(0, window.innerHeight * 2)")
        page.wait_for_timeout(_SCROLL_PAUSE_MS)

    return urls


def _download_one(
    context: BrowserContext,
    photo_url: str,
    dest_dir: Path,
    idx: int,
    verbose: bool,
) -> tuple[str, bool]:
    """Open photo detail view, trigger Shift+D download, save to dest_dir.

    Returns ``(filename, success)``.
    """
    page = context.new_page()
    try:
        page.goto(photo_url, wait_until="domcontentloaded", timeout=30_000)

        with page.expect_download(timeout=_DOWNLOAD_TIMEOUT_MS) as dl_info:
            page.keyboard.press("Shift+D")

        download: Download = dl_info.value
        filename = download.suggested_filename or f"photo_{idx:04d}.jpg"
        save_path = dest_dir / filename
        download.save_as(str(save_path))

        if verbose:
            rel = save_path.relative_to(save_path.parents[3]) if save_path.parents[3].exists() else save_path
            print(f"  + {rel}")

        return filename, True

    except Exception as exc:
        filename = f"photo_{idx:04d}.jpg"
        print(f"FAILED: {filename} — {exc}", file=sys.stderr)
        if verbose:
            print(f"  x {filename} (failed: {exc})")
        return filename, False

    finally:
        page.close()
