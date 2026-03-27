"""Profile initialisation for gphotos-sync.

Creates the config entry and session directories for a new profile, then
opens a headed browser so the user can complete Google sign-in.
"""
import logging
import subprocess
import sys
from pathlib import Path

import yaml

_logger = logging.getLogger("gphotos_sync")


def _ensure_chromium() -> None:
    """Install Playwright's Chromium browser if it is not already present."""
    try:
        from playwright.sync_api import sync_playwright
        pw = sync_playwright().start()
        try:
            # launch with no viewport just to probe — exits immediately
            browser = pw.chromium.launch(headless=True)
            browser.close()
        finally:
            pw.stop()
    except Exception as exc:
        if "Executable doesn't exist" in str(exc):
            _logger.info("Chromium not found — installing via playwright install chromium")
            result = subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                check=False,
            )
            if result.returncode != 0:
                _logger.error("'playwright install chromium' failed — run it manually and retry")
                print(
                    "ERROR: 'playwright install chromium' failed."
                    " Run it manually and retry.",
                    file=sys.stderr,
                )
                sys.exit(1)
            _logger.info("Chromium installed successfully")
        else:
            raise


def init_profile(profile_name: str, config_path: Path) -> None:
    """Create a profile in *config_path* and authenticate via browser.

    Steps:
    1. Derive conventional default paths for ``token_dir`` and ``destination``.
    2. Write the profile block into the YAML config (create file if absent;
       skip if the profile already exists and ask the user to confirm overwrite).
    3. Create the directories on disk.
    4. Open a headed Chromium window so the user can log in to Google.
    5. Save the Playwright session to ``token_dir/playwright_state.json``.
    """
    # ------------------------------------------------------------------
    # 1. Derive default paths
    # ------------------------------------------------------------------
    home = Path.home()
    token_dir = home / ".gphotos-sync" / "sessions" / profile_name
    destination = home / "Photos" / profile_name

    # ------------------------------------------------------------------
    # 2. Load existing config or start fresh
    # ------------------------------------------------------------------
    config_path.parent.mkdir(parents=True, exist_ok=True)

    config_data: dict = {}
    if config_path.exists():
        with open(config_path, "r") as f:
            loaded = yaml.safe_load(f)
        if loaded and isinstance(loaded, dict):
            config_data = loaded

    if profile_name in config_data:
        _logger.warning("Profile '%s' already exists in config — prompting for overwrite", profile_name)
        print(
            f'[gphotos-sync] Profile "{profile_name}" already exists in {config_path}.',
            file=sys.stderr,
        )
        answer = input("Overwrite and re-authenticate? [y/N] ").strip().lower()
        if answer != "y":
            _logger.info("Init cancelled by user for profile '%s'", profile_name)
            print("[gphotos-sync] Init cancelled.", file=sys.stderr)
            sys.exit(0)

    # ------------------------------------------------------------------
    # 3. Write profile block into config
    # ------------------------------------------------------------------
    config_data[profile_name] = {
        "token_dir": str(token_dir),
        "destination": str(destination),
        "date_offset": -1,
        "verbose": False,
    }

    with open(config_path, "w") as f:
        yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    _logger.info("Profile '%s' written to config", profile_name)
    print(f'[gphotos-sync] Profile "{profile_name}" written to {config_path}')
    print(f"  token_dir:   {token_dir}")
    print(f"  destination: {destination}")

    # ------------------------------------------------------------------
    # 4. Create directories
    # ------------------------------------------------------------------
    token_dir.mkdir(parents=True, exist_ok=True)
    destination.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 5. Ensure Chromium is installed
    # ------------------------------------------------------------------
    _ensure_chromium()

    # ------------------------------------------------------------------
    # 6. Open browser for Google login
    # ------------------------------------------------------------------
    # Always delete any existing session file before init — a stale or
    # unauthenticated playwright_state.json would cause ensure_session to
    # skip the headed login flow and return silently without showing a browser.
    stale_state = token_dir / "playwright_state.json"
    if stale_state.exists():
        stale_state.unlink()
        _logger.info("Removed stale session file for profile '%s'", profile_name)

    _logger.info("Opening browser for Google login for profile '%s'", profile_name)
    print(
        "\n[gphotos-sync] Opening browser — sign in to Google, then return here.",
        file=sys.stderr,
    )

    from . import browser as _browser

    pw, context = _browser.ensure_session(token_dir, profile_name)
    _browser.close_session(pw, context)

    state_file = token_dir / "playwright_state.json"
    if state_file.exists():
        _logger.info("Login successful, session saved for profile '%s'", profile_name)
        print(
            f'\n[gphotos-sync] Login successful. Session saved to {state_file}'
        )
        print(
            f'[gphotos-sync] Run your first sync with:\n'
            f'  python -m src.photo_sync --profile {profile_name}'
        )
    else:
        _logger.error("Session file not created for profile '%s' — login may not have completed", profile_name)
        print(
            "[gphotos-sync] WARNING: Session file was not created."
            " Login may not have completed.",
            file=sys.stderr,
        )
        sys.exit(1)
