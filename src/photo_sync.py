"""gphotos-sync — CLI entry point.

Downloads photos from Google Photos into a local YYYY/MM/DD folder hierarchy.
Supports multiple Google accounts via named profiles in a YAML config file.

Usage:
    python -m src.photo_sync --profile personal [options]
    python -m src.photo_sync --profile all [options]
"""
import argparse
import logging
import sys
from pathlib import Path
from typing import List

from .config import parse_args, SyncConfig
from .downloader import run_sync, SyncRun

_logger = logging.getLogger("gphotos_sync")


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def print_summary(run: SyncRun, config: SyncConfig, profile_name: str = "") -> None:
    """Print structured run summary to stdout."""
    label = profile_name or run.profile_name

    if len(run.dates) == 1:
        d = run.dates[0]
        print(f"gphotos-sync [{label}]: {d}")
        print(f"  Downloaded: {run.downloaded}")
        print(f"  Failed:     {run.failed}")
        dest_day = config.destination / d.strftime("%Y") / d.strftime("%m") / d.strftime("%d")
        print(f"  Saved to:   {dest_day}{_sep()}")
    else:
        start = run.dates[0]
        end = run.dates[-1]
        print(f"gphotos-sync [{label}]: {start} \u2192 {end}")
        for d, (dl, fail) in run.per_day.items():
            print(f"  {d}: Downloaded {dl:2d}  Failed {fail:2d}")
        print(f"  Total downloaded: {run.downloaded}")
        print(f"  Total failed:     {run.failed}")
        print(f"  Saved to:   {config.destination}{_sep()}")


def _sep() -> str:
    """Trailing path separator for display only."""
    import os
    return os.sep


def _collect_token_dirs(config_data: dict) -> List[Path]:
    """Extract token_dir values from all profiles in the config dict."""
    dirs: List[Path] = []
    for profile_data in config_data.values():
        if isinstance(profile_data, dict) and "token_dir" in profile_data:
            dirs.append(Path(str(profile_data["token_dir"])))
    return dirs


# ---------------------------------------------------------------------------
# Single-profile sync helper
# ---------------------------------------------------------------------------

def _sync_one_profile(config: SyncConfig, profile_name: str = "") -> SyncRun:
    """Run sync for one profile and print summary. Raises on failure."""
    run = run_sync(config, profile_name or "default")
    print_summary(run, config, profile_name=profile_name)
    return run


# ---------------------------------------------------------------------------
# --profile all: sequential multi-profile run
# ---------------------------------------------------------------------------

def _substitute_profile_argv(argv: list, profile_name: str) -> list:
    """Return a copy of argv with --profile all replaced by --profile <name>."""
    result = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("--profile", "-p"):
            result.extend(["--profile", profile_name])
            i += 2
        elif arg.startswith("--profile="):
            result.append(f"--profile={profile_name}")
            i += 1
        elif arg.startswith("-p="):
            result.append(f"-p={profile_name}")
            i += 1
        else:
            result.append(arg)
            i += 1
    return result


def run_all_profiles(config_path: Path, argv: list) -> None:
    """Run every profile in the config file sequentially.

    A failure in one profile is caught and does not abort the others.
    Exits 0 if all profiles succeeded; exits 1 if any profile failed.
    """
    from . import config_loader

    config_data = config_loader.load_config(config_path)
    profile_names = list(config_data.keys())

    failed_profiles: list = []
    completed_profiles: list = []

    for profile_name in profile_names:
        print(f"\n=== Profile: {profile_name} ===")
        profile_argv = _substitute_profile_argv(argv, profile_name)
        try:
            config = parse_args(profile_argv)
            _sync_one_profile(config, profile_name=profile_name)
            completed_profiles.append(profile_name)
        except SystemExit:
            _logger.error("Config validation failed for profile '%s'", profile_name)
            print(
                f'ERROR: Profile "{profile_name}" configuration is invalid — skipping.',
                file=sys.stderr,
            )
            failed_profiles.append(profile_name)
        except Exception as exc:
            _logger.error("Profile '%s' failed: %s", profile_name, exc)
            print(
                f'ERROR: Profile "{profile_name}" failed: {exc}',
                file=sys.stderr,
            )
            failed_profiles.append(profile_name)

    print(f"\n=== Summary: --profile all ===")
    completed_str = ", ".join(completed_profiles) if completed_profiles else "none"
    failed_str = ", ".join(failed_profiles) if failed_profiles else "none"
    print(f"  Completed: {completed_str}")
    print(f"  Failed:    {failed_str}")

    sys.exit(1 if failed_profiles else 0)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument(
        "--config", type=Path,
        default=Path.home() / ".gphotos-sync" / "config.yml",
    )
    pre_parser.add_argument("--profile", "-p", default="default")
    pre_parser.add_argument("--init", default=None, metavar="PROFILE_NAME")
    pre_args, _ = pre_parser.parse_known_args(argv)

    # Set up logging as early as possible — before any profile logic.
    from . import config_loader as _cl
    from .logger import setup_logging
    _config_data: dict = {}
    if pre_args.config.exists():
        try:
            _config_data = _cl.load_config(pre_args.config) or {}
        except SystemExit:
            pass  # Invalid config — logging still starts; error surfaces later.
    _verbose = "--verbose" in argv or "-v" in argv
    setup_logging(
        verbose=_verbose,
        log_dir=pre_args.config.parent,
        token_dirs=_collect_token_dirs(_config_data),
    )

    if pre_args.init is not None:
        from .init import init_profile
        init_profile(pre_args.init, pre_args.config)
        return

    if pre_args.profile == "all":
        run_all_profiles(pre_args.config, argv)
        return

    config = parse_args(argv)

    try:
        _sync_one_profile(config)
    except Exception as exc:
        _logger.error("Sync failed: %s", exc)
        print(f"ERROR: Sync failed: {exc}", file=sys.stderr)
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
