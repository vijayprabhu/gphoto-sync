"""Unit tests for src/config.py — parse_args() with YAML profile loading."""
import pytest
import yaml
from datetime import date, timedelta
from pathlib import Path

from src.config import parse_args, SyncConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(tmp_path, profiles: dict) -> Path:
    """Write a config.yml with the given profiles dict and return its path."""
    config_file = tmp_path / "config.yml"
    config_file.write_text(yaml.dump(profiles))
    return config_file


def _minimal_profile(dest: Path, tmp_path: Path) -> dict:
    """Return a minimal valid profile dict with absolute paths."""
    return {
        "destination": str(dest),
        "token_dir": str(tmp_path / "token"),
    }


def _default_config(tmp_path: Path, dest: Path, extra: dict = None) -> Path:
    """Create a config.yml with a single 'default' profile."""
    profile = _minimal_profile(dest, tmp_path)
    if extra:
        profile.update(extra)
    return _make_config(tmp_path, {"default": profile})


# ---------------------------------------------------------------------------
# Basic parsing
# ---------------------------------------------------------------------------

def test_minimal_args_uses_profile_destination(tmp_path):
    dest = tmp_path / "photos"
    dest.mkdir()
    config_file = _default_config(tmp_path, dest)
    config = parse_args(["--config", str(config_file)])
    assert config.destination == dest
    assert config.date is None
    assert config.start_date is None
    assert config.end_date is None
    assert config.date_offset == -1
    assert config.verbose is False


def test_token_dir_comes_from_profile(tmp_path):
    dest = tmp_path / "photos"
    dest.mkdir()
    config_file = _default_config(tmp_path, dest)
    config = parse_args(["--config", str(config_file)])
    assert config.token_dir == tmp_path / "token"


def test_explicit_date_sets_single_date(tmp_path):
    dest = tmp_path / "photos"
    dest.mkdir()
    config_file = _default_config(tmp_path, dest)
    config = parse_args(["--config", str(config_file), "--date", "2026-01-15"])
    assert config.date == date(2026, 1, 15)
    assert config.start_date is None
    assert config.end_date is None


def test_start_end_date_sets_range(tmp_path):
    dest = tmp_path / "photos"
    dest.mkdir()
    config_file = _default_config(tmp_path, dest)
    config = parse_args([
        "--config", str(config_file),
        "--start-date", "2026-01-01",
        "--end-date", "2026-01-07",
    ])
    assert config.start_date == date(2026, 1, 1)
    assert config.end_date == date(2026, 1, 7)
    assert config.date is None


def test_dest_cli_flag_overrides_profile_destination(tmp_path):
    dest = tmp_path / "photos"
    dest.mkdir()
    override = tmp_path / "override"
    override.mkdir()
    config_file = _default_config(tmp_path, dest)
    config = parse_args(["--config", str(config_file), "--dest", str(override)])
    assert config.destination == override


# ---------------------------------------------------------------------------
# Argument validation
# ---------------------------------------------------------------------------

def test_invalid_date_format_exits(tmp_path):
    dest = tmp_path / "photos"
    dest.mkdir()
    config_file = _default_config(tmp_path, dest)
    with pytest.raises(SystemExit) as exc:
        parse_args(["--config", str(config_file), "--date", "01-15-2026"])
    assert exc.value.code == 2


def test_date_and_start_date_mutually_exclusive(tmp_path):
    dest = tmp_path / "photos"
    dest.mkdir()
    config_file = _default_config(tmp_path, dest)
    with pytest.raises(SystemExit) as exc:
        parse_args([
            "--config", str(config_file),
            "--date", "2026-03-22",
            "--start-date", "2026-03-01",
            "--end-date", "2026-03-22",
        ])
    assert exc.value.code == 2


def test_date_and_end_date_mutually_exclusive(tmp_path):
    dest = tmp_path / "photos"
    dest.mkdir()
    config_file = _default_config(tmp_path, dest)
    with pytest.raises(SystemExit) as exc:
        parse_args([
            "--config", str(config_file),
            "--date", "2026-03-22",
            "--end-date", "2026-03-22",
        ])
    assert exc.value.code == 2


def test_start_date_without_end_date_exits(tmp_path):
    dest = tmp_path / "photos"
    dest.mkdir()
    config_file = _default_config(tmp_path, dest)
    with pytest.raises(SystemExit) as exc:
        parse_args(["--config", str(config_file), "--start-date", "2026-03-01"])
    assert exc.value.code == 2


def test_end_date_without_start_date_exits(tmp_path):
    dest = tmp_path / "photos"
    dest.mkdir()
    config_file = _default_config(tmp_path, dest)
    with pytest.raises(SystemExit) as exc:
        parse_args(["--config", str(config_file), "--end-date", "2026-03-22"])
    assert exc.value.code == 2


def test_start_date_after_end_date_exits(tmp_path):
    dest = tmp_path / "photos"
    dest.mkdir()
    config_file = _default_config(tmp_path, dest)
    with pytest.raises(SystemExit) as exc:
        parse_args([
            "--config", str(config_file),
            "--start-date", "2026-03-22",
            "--end-date", "2026-03-01",
        ])
    assert exc.value.code == 2


def test_verbose_flag(tmp_path):
    dest = tmp_path / "photos"
    dest.mkdir()
    config_file = _default_config(tmp_path, dest)
    config = parse_args(["--config", str(config_file), "-v"])
    assert config.verbose is True


# ---------------------------------------------------------------------------
# Profile optional fields as CLI defaults (set_defaults layering)
# ---------------------------------------------------------------------------

def test_profile_verbose_true_is_default(tmp_path):
    """Profile verbose:true becomes the default without any CLI --verbose flag."""
    dest = tmp_path / "photos"
    dest.mkdir()
    config_file = _default_config(tmp_path, dest, extra={"verbose": True})
    config = parse_args(["--config", str(config_file)])
    assert config.verbose is True


def test_profile_date_offset_is_default(tmp_path):
    """Profile date_offset becomes the default when no date flags are passed."""
    dest = tmp_path / "photos"
    dest.mkdir()
    config_file = _default_config(tmp_path, dest, extra={"date_offset": -7})
    config = parse_args(["--config", str(config_file)])
    assert config.date_offset == -7


def test_profile_omits_date_offset_uses_minus_one(tmp_path):
    """When a profile omits date_offset, the built-in default (-1) applies."""
    dest = tmp_path / "photos"
    dest.mkdir()
    config_file = _default_config(tmp_path, dest)
    config = parse_args(["--config", str(config_file)])
    assert config.date_offset == -1


# ---------------------------------------------------------------------------
# Named profile selection
# ---------------------------------------------------------------------------

def test_named_profile_selected_via_flag(tmp_path):
    dest_personal = tmp_path / "personal"
    dest_personal.mkdir()
    dest_work = tmp_path / "work"
    dest_work.mkdir()
    config_file = _make_config(tmp_path, {
        "personal": _minimal_profile(dest_personal, tmp_path),
        "work": _minimal_profile(dest_work, tmp_path),
    })
    config = parse_args(["--config", str(config_file), "--profile", "work"])
    assert config.destination == dest_work


def test_missing_config_file_exits(tmp_path):
    missing = tmp_path / "nofile.yml"
    with pytest.raises(SystemExit) as exc:
        parse_args(["--config", str(missing)])
    assert exc.value.code == 1


def test_missing_profile_name_exits(tmp_path):
    dest = tmp_path / "photos"
    dest.mkdir()
    config_file = _default_config(tmp_path, dest)
    with pytest.raises(SystemExit) as exc:
        parse_args(["--config", str(config_file), "--profile", "nonexistent"])
    assert exc.value.code == 1
