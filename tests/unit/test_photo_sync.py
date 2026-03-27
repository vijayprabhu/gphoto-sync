"""Unit tests for src/photo_sync.py — run_all_profiles and --profile all."""
import yaml
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.photo_sync import run_all_profiles, _substitute_profile_argv


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(tmp_path, profiles: dict) -> Path:
    config_file = tmp_path / "config.yml"
    config_file.write_text(yaml.dump(profiles))
    return config_file


def _profile(tmp_path, name: str) -> dict:
    dest = tmp_path / name
    dest.mkdir(exist_ok=True)
    return {
        "destination": str(dest),
        "token_dir": str(tmp_path / f"{name}_token"),
    }


# ---------------------------------------------------------------------------
# _substitute_profile_argv
# ---------------------------------------------------------------------------

def test_substitute_profile_argv_replaces_all(tmp_path):
    argv = ["--config", "cfg.yml", "--profile", "all", "--verbose"]
    result = _substitute_profile_argv(argv, "personal")
    assert "--profile" in result
    assert "personal" in result
    assert "all" not in result
    assert "--verbose" in result


def test_substitute_profile_argv_equals_form(tmp_path):
    argv = ["--profile=all", "--verbose"]
    result = _substitute_profile_argv(argv, "work")
    assert "--profile=work" in result
    assert "--verbose" in result


def test_substitute_profile_argv_preserves_other_flags(tmp_path):
    argv = ["--config", "cfg.yml", "--profile", "all", "--date", "2026-03-01"]
    result = _substitute_profile_argv(argv, "work")
    assert "--date" in result
    assert "2026-03-01" in result


# ---------------------------------------------------------------------------
# run_all_profiles — all profiles succeed
# ---------------------------------------------------------------------------

def test_run_all_profiles_calls_sync_for_each_profile(tmp_path, capsys):
    config_file = _make_config(tmp_path, {
        "personal": _profile(tmp_path, "personal"),
        "work": _profile(tmp_path, "work"),
    })
    argv = ["--config", str(config_file), "--profile", "all"]

    with patch("src.photo_sync.parse_args") as mock_parse, \
         patch("src.photo_sync._sync_one_profile") as mock_sync:

        mock_parse.return_value = MagicMock()

        with pytest.raises(SystemExit) as exc:
            run_all_profiles(config_file, argv)

        assert exc.value.code == 0
        assert mock_sync.call_count == 2


def test_run_all_profiles_prints_profile_headers(tmp_path, capsys):
    config_file = _make_config(tmp_path, {
        "personal": _profile(tmp_path, "personal"),
        "work": _profile(tmp_path, "work"),
    })
    argv = ["--config", str(config_file), "--profile", "all"]

    with patch("src.photo_sync.parse_args"), \
         patch("src.photo_sync._sync_one_profile"):
        with pytest.raises(SystemExit):
            run_all_profiles(config_file, argv)

    out = capsys.readouterr().out
    assert "=== Profile: personal ===" in out
    assert "=== Profile: work ===" in out
    assert "=== Summary: --profile all ===" in out


def test_run_all_profiles_exits_0_when_all_succeed(tmp_path):
    config_file = _make_config(tmp_path, {"p1": _profile(tmp_path, "p1")})
    argv = ["--config", str(config_file), "--profile", "all"]

    with patch("src.photo_sync.parse_args"), \
         patch("src.photo_sync._sync_one_profile"):
        with pytest.raises(SystemExit) as exc:
            run_all_profiles(config_file, argv)
    assert exc.value.code == 0


# ---------------------------------------------------------------------------
# run_all_profiles — one profile fails
# ---------------------------------------------------------------------------

def test_run_all_profiles_continues_after_failure(tmp_path):
    config_file = _make_config(tmp_path, {
        "personal": _profile(tmp_path, "personal"),
        "work": _profile(tmp_path, "work"),
    })
    argv = ["--config", str(config_file), "--profile", "all"]

    call_count = {"n": 0}

    def side_effect(config, profile_name=""):
        call_count["n"] += 1
        if profile_name == "personal":
            raise RuntimeError("auth failure")

    with patch("src.photo_sync.parse_args") as mock_parse, \
         patch("src.photo_sync._sync_one_profile", side_effect=side_effect):
        mock_parse.return_value = MagicMock()
        with pytest.raises(SystemExit) as exc:
            run_all_profiles(config_file, argv)

    assert call_count["n"] == 2, "Both profiles must be attempted"
    assert exc.value.code == 1


def test_run_all_profiles_exits_1_when_any_fail(tmp_path):
    config_file = _make_config(tmp_path, {
        "good": _profile(tmp_path, "good"),
        "bad": _profile(tmp_path, "bad"),
    })
    argv = ["--config", str(config_file), "--profile", "all"]

    def side_effect(config, profile_name=""):
        if profile_name == "bad":
            raise RuntimeError("network error")

    with patch("src.photo_sync.parse_args") as mock_parse, \
         patch("src.photo_sync._sync_one_profile", side_effect=side_effect):
        mock_parse.return_value = MagicMock()
        with pytest.raises(SystemExit) as exc:
            run_all_profiles(config_file, argv)
    assert exc.value.code == 1


def test_run_all_profiles_summary_lists_failed_profiles(tmp_path, capsys):
    config_file = _make_config(tmp_path, {
        "personal": _profile(tmp_path, "personal"),
        "work": _profile(tmp_path, "work"),
    })
    argv = ["--config", str(config_file), "--profile", "all"]

    def side_effect(config, profile_name=""):
        if profile_name == "work":
            raise RuntimeError("error")

    with patch("src.photo_sync.parse_args") as mock_parse, \
         patch("src.photo_sync._sync_one_profile", side_effect=side_effect):
        mock_parse.return_value = MagicMock()
        with pytest.raises(SystemExit):
            run_all_profiles(config_file, argv)

    out = capsys.readouterr().out
    assert "personal" in out   # completed
    assert "work" in out       # failed


# ---------------------------------------------------------------------------
# run_all_profiles — CLI flag forwarding
# ---------------------------------------------------------------------------

def test_verbose_flag_forwarded_to_all_profiles(tmp_path):
    config_file = _make_config(tmp_path, {
        "p1": _profile(tmp_path, "p1"),
        "p2": _profile(tmp_path, "p2"),
    })
    argv = ["--config", str(config_file), "--profile", "all", "--verbose"]

    received_argvs = []

    def capture_parse(captured_argv):
        received_argvs.append(captured_argv)
        return MagicMock()

    with patch("src.photo_sync.parse_args", side_effect=capture_parse), \
         patch("src.photo_sync._sync_one_profile"):
        with pytest.raises(SystemExit):
            run_all_profiles(config_file, argv)

    for received in received_argvs:
        assert "--verbose" in received
