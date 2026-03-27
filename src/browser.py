"""Playwright browser session lifecycle for gphotos-sync.

Manages per-profile browser sessions: launching headed for first-time login,
restoring saved state for subsequent headless runs, and detecting expiry.
"""
import logging
from pathlib import Path

_logger = logging.getLogger("gphotos_sync")

from playwright.sync_api import BrowserContext, Playwright, sync_playwright

_STATE_FILE = "playwright_state.json"
_PHOTOS_URL = "https://photos.google.com"
_PHOTOS_HOST = "photos.google.com"
_LOGIN_HOST = "accounts.google.com"


def ensure_session(token_dir: Path, profile_name: str) -> tuple[Playwright, BrowserContext]:
    """Return an authenticated BrowserContext for the given profile.

    If a saved session exists and is still valid, launches headless and restores
    it. If missing or expired, launches a headed browser and waits for the user
    to complete Google sign-in, then saves the session.

    Returns ``(playwright, context)``; call :func:`close_session` when done.
    """
    token_dir.mkdir(parents=True, exist_ok=True)
    state_file = token_dir / _STATE_FILE

    pw = sync_playwright().start()

    if state_file.exists():
        context = _load_headless(pw, state_file)
        if _is_authenticated(context):
            return pw, context
        # Session expired — close and re-authenticate.
        context.close()
        _logger.warning("[%s] Session expired — re-authenticating", profile_name)

    # No valid session — open headed browser for manual login.
    _logger.info("[%s] No saved session — opening browser for login", profile_name)
    context = _login_headed(pw, state_file)
    return pw, context


def close_session(pw: Playwright, context: BrowserContext) -> None:
    """Close the browser context and Playwright instance."""
    context.close()
    pw.stop()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_headless(pw: Playwright, state_file: Path) -> BrowserContext:
    browser = pw.chromium.launch(headless=True)
    return browser.new_context(storage_state=str(state_file))


def _is_authenticated(context: BrowserContext) -> bool:
    """Navigate to Google Photos and return True if not redirected to login."""
    page = context.new_page()
    try:
        page.goto(_PHOTOS_URL, wait_until="domcontentloaded", timeout=30_000)
        # Allow JS redirect to fire before evaluating the URL.
        try:
            page.wait_for_load_state("networkidle", timeout=10_000)
        except Exception:
            pass
        return _LOGIN_HOST not in page.url
    finally:
        page.close()


def _login_headed(pw: Playwright, state_file: Path) -> BrowserContext:
    """Open a visible browser, wait for the user to reach Google Photos, save state."""
    browser = pw.chromium.launch(
        headless=False,
        args=["--disable-blink-features=AutomationControlled"],
    )
    context = browser.new_context()
    page = context.new_page()
    page.goto(_PHOTOS_URL, wait_until="domcontentloaded", timeout=30_000)

    # Google's login redirect is a JS redirect that fires after domcontentloaded.
    # Wait for network to settle so the redirect has landed on accounts.google.com
    # before we start polling — otherwise the while condition evaluates too early
    # while still on photos.google.com and exits without waiting for login.
    try:
        page.wait_for_load_state("networkidle", timeout=10_000)
    except Exception:
        pass  # networkidle timeout is acceptable — proceed to poll loop

    # Poll until the user has completed login and landed back on Google Photos.
    while _LOGIN_HOST in page.url or _PHOTOS_HOST not in page.url:
        page.wait_for_timeout(1_000)

    # Wait for Google Photos to fully load after sign-in redirect.
    page.wait_for_load_state("domcontentloaded", timeout=30_000)
    page.close()

    context.storage_state(path=str(state_file))
    _logger.info("Login successful, session saved")
    return context
