"""SyncConfig dataclass and CLI argument parsing for gphotos-sync."""
import argparse
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional


@dataclass
class SyncConfig:
    token_dir: Path
    destination: Path
    date: Optional[date] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    date_offset: int = -1
    verbose: bool = False


def _parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid date '{value}'. Expected format: YYYY-MM-DD"
        )


def parse_args(argv=None) -> SyncConfig:
    from . import config_loader

    default_config = Path.home() / ".gphotos-sync" / "config.yml"

    # Step 1: Pre-parse to get --config and --profile before loading the YAML.
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument("--config", type=Path, default=default_config)
    pre_parser.add_argument("--profile", "-p", default="default")
    pre_args, _ = pre_parser.parse_known_args(argv)

    # Step 2: Load and validate the selected profile.
    config_data = config_loader.load_config(pre_args.config)
    profile = config_loader.get_profile(config_data, pre_args.profile)

    # Step 3: Build main parser.
    parser = argparse.ArgumentParser(
        prog="gphotos-sync",
        description="Download photos from Google Photos into a local YYYY/MM/DD folder hierarchy.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=default_config,
        help=f"Path to YAML config file (default: {default_config})",
    )
    parser.add_argument(
        "--profile", "-p",
        default="default",
        metavar="NAME",
        help='Profile name to use, or "all" to run every profile (default: default)',
    )
    parser.add_argument(
        "--dest", "-d",
        type=Path,
        default=None,
        metavar="PATH",
        help="Override the profile's destination folder for this run",
    )
    parser.add_argument(
        "--date",
        type=_parse_date,
        default=None,
        metavar="YYYY-MM-DD",
        help="Single capture date to download; mutually exclusive with --start-date/--end-date",
    )
    parser.add_argument(
        "--start-date",
        type=_parse_date,
        default=None,
        dest="start_date",
        metavar="YYYY-MM-DD",
        help="Range start (inclusive); must be paired with --end-date",
    )
    parser.add_argument(
        "--end-date",
        type=_parse_date,
        default=None,
        dest="end_date",
        metavar="YYYY-MM-DD",
        help="Range end (inclusive); must be paired with --start-date",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        default=False,
        help="Print per-photo progress in addition to the run summary",
    )

    # Step 4: Apply profile optional fields as defaults so CLI flags override them.
    profile_defaults: dict = {
        "dest": Path(profile["destination"]),
        "date_offset": profile.get("date_offset", -1),
        "verbose": profile.get("verbose", False),
    }
    parser.set_defaults(**profile_defaults)

    # Step 5: Full parse — CLI flags override the profile defaults set above.
    args = parser.parse_args(argv)

    # Step 6: Validate date flag mutual exclusion.
    if args.date is not None and (args.start_date is not None or args.end_date is not None):
        print(
            "ERROR: Cannot use --date together with --start-date/--end-date",
            file=sys.stderr,
        )
        sys.exit(2)

    if (args.start_date is None) != (args.end_date is None):
        print(
            "ERROR: --start-date and --end-date must be used together",
            file=sys.stderr,
        )
        sys.exit(2)

    if args.start_date is not None and args.start_date > args.end_date:
        print(
            "ERROR: --start-date must be on or before --end-date",
            file=sys.stderr,
        )
        sys.exit(2)

    return SyncConfig(
        token_dir=Path(profile["token_dir"]),
        destination=args.dest,
        date=args.date,
        start_date=args.start_date,
        end_date=args.end_date,
        date_offset=args.date_offset,
        verbose=args.verbose,
    )
