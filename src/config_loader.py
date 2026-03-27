"""YAML config file loading, profile validation, and profile selection."""
import sys
from pathlib import Path

import yaml


def load_config(config_path: Path) -> dict:
    """Load and parse the YAML config file. Returns the parsed dict of profiles.

    Exits with code 1 and a clear stderr message if the file is missing,
    unparseable, or contains no profiles.
    """
    if not config_path.exists():
        print(f"ERROR: Config file not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(config_path, "r") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        print(
            f"ERROR: Config file parse error in {config_path}: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)

    if not data or not isinstance(data, dict):
        print(
            f"ERROR: Config file contains no profiles: {config_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    return data


def validate_profile(profile_name: str, profile_data: dict) -> None:
    """Validate required fields and path constraints for a profile.

    Exits with code 1 and an actionable stderr message on the first violation.
    All validation is performed before any network activity.
    """
    required_fields = ["destination", "token_dir"]
    for field_name in required_fields:
        if field_name not in profile_data:
            print(
                f'ERROR: Profile "{profile_name}" is missing required field: {field_name}',
                file=sys.stderr,
            )
            sys.exit(1)

        value = profile_data[field_name]
        if not Path(str(value)).is_absolute():
            print(
                f'ERROR: Profile "{profile_name}": field "{field_name}" must be an'
                f" absolute path, got: {value}",
                file=sys.stderr,
            )
            sys.exit(1)


def get_profile(config: dict, profile_name: str) -> dict:
    """Look up and validate a profile by name. Returns the profile dict.

    Exits with code 1 if the name is reserved, not found, or validation fails.
    When profile_name is "default" and not present, emits a distinct error message.
    """
    if profile_name == "all":
        print(
            'ERROR: Profile name "all" is reserved and cannot be used',
            file=sys.stderr,
        )
        sys.exit(1)

    available = ", ".join(config.keys())

    if profile_name not in config:
        if profile_name == "default":
            print(
                f'ERROR: No "default" profile found. Available profiles: {available}',
                file=sys.stderr,
            )
        else:
            print(
                f'ERROR: Profile "{profile_name}" not found.'
                f" Available profiles: {available}",
                file=sys.stderr,
            )
        sys.exit(1)

    validate_profile(profile_name, config[profile_name])
    return config[profile_name]
