"""Unit tests for src/config_loader.py — load_config, validate_profile, get_profile."""
import textwrap
import pytest

from src.config_loader import load_config, validate_profile, get_profile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_yaml(tmp_path, content: str):
    """Write a YAML string to a config.yml in tmp_path and return the path."""
    config_file = tmp_path / "config.yml"
    config_file.write_text(textwrap.dedent(content))
    return config_file


def _minimal_profile(tmp_path, name="default"):
    """Return a minimal valid profile dict with absolute paths under tmp_path."""
    return {
        "destination": str(tmp_path / "photos"),
        "token_dir": str(tmp_path / "token"),
    }


# ---------------------------------------------------------------------------
# load_config — valid file
# ---------------------------------------------------------------------------

def test_load_config_returns_dict_with_profiles(tmp_path):
    config_file = _write_yaml(tmp_path, f"""
        personal:
          destination: {tmp_path}/photos
          token_dir: {tmp_path}/token
        work:
          destination: {tmp_path}/work_photos
          token_dir: {tmp_path}/work_token
    """)
    data = load_config(config_file)
    assert "personal" in data
    assert "work" in data


# ---------------------------------------------------------------------------
# load_config — missing file
# ---------------------------------------------------------------------------

def test_load_config_missing_file_exits(tmp_path):
    missing = tmp_path / "nonexistent.yml"
    with pytest.raises(SystemExit) as exc:
        load_config(missing)
    assert exc.value.code == 1


def test_load_config_missing_file_error_message(tmp_path, capsys):
    missing = tmp_path / "nonexistent.yml"
    with pytest.raises(SystemExit):
        load_config(missing)
    stderr = capsys.readouterr().err
    assert "Config file not found" in stderr
    assert str(missing) in stderr


# ---------------------------------------------------------------------------
# load_config — unparseable YAML
# ---------------------------------------------------------------------------

def test_load_config_invalid_yaml_exits(tmp_path):
    bad_file = tmp_path / "config.yml"
    bad_file.write_text("key: [unclosed bracket\nnot_yaml: :")
    with pytest.raises(SystemExit) as exc:
        load_config(bad_file)
    assert exc.value.code == 1


def test_load_config_invalid_yaml_error_message(tmp_path, capsys):
    bad_file = tmp_path / "config.yml"
    bad_file.write_text("key: [unclosed bracket\nnot_yaml: :")
    with pytest.raises(SystemExit):
        load_config(bad_file)
    stderr = capsys.readouterr().err
    assert "Config file parse error" in stderr
    assert str(bad_file) in stderr


# ---------------------------------------------------------------------------
# load_config — empty / no profiles
# ---------------------------------------------------------------------------

def test_load_config_empty_file_exits(tmp_path):
    config_file = tmp_path / "config.yml"
    config_file.write_text("")
    with pytest.raises(SystemExit) as exc:
        load_config(config_file)
    assert exc.value.code == 1


def test_load_config_empty_file_error_message(tmp_path, capsys):
    config_file = tmp_path / "config.yml"
    config_file.write_text("")
    with pytest.raises(SystemExit):
        load_config(config_file)
    stderr = capsys.readouterr().err
    assert "contains no profiles" in stderr


# ---------------------------------------------------------------------------
# validate_profile — valid profile
# ---------------------------------------------------------------------------

def test_validate_profile_valid_no_error(tmp_path):
    profile = _minimal_profile(tmp_path)
    validate_profile("default", profile)  # should not raise


# ---------------------------------------------------------------------------
# validate_profile — missing required field
# ---------------------------------------------------------------------------

def test_validate_profile_missing_destination_exits(tmp_path, capsys):
    profile = _minimal_profile(tmp_path)
    del profile["destination"]
    with pytest.raises(SystemExit) as exc:
        validate_profile("work", profile)
    assert exc.value.code == 1
    stderr = capsys.readouterr().err
    assert 'Profile "work"' in stderr
    assert "destination" in stderr


def test_validate_profile_missing_token_dir_exits(tmp_path, capsys):
    profile = _minimal_profile(tmp_path)
    del profile["token_dir"]
    with pytest.raises(SystemExit) as exc:
        validate_profile("default", profile)
    assert exc.value.code == 1
    stderr = capsys.readouterr().err
    assert "token_dir" in stderr


# ---------------------------------------------------------------------------
# validate_profile — relative paths rejected
# ---------------------------------------------------------------------------

def test_validate_profile_relative_destination_exits(tmp_path, capsys):
    profile = _minimal_profile(tmp_path)
    profile["destination"] = "relative/path"
    with pytest.raises(SystemExit) as exc:
        validate_profile("personal", profile)
    assert exc.value.code == 1
    stderr = capsys.readouterr().err
    assert 'Profile "personal"' in stderr
    assert "destination" in stderr
    assert "absolute path" in stderr
    assert "relative/path" in stderr


def test_validate_profile_relative_token_dir_exits(tmp_path, capsys):
    profile = _minimal_profile(tmp_path)
    profile["token_dir"] = "./token"
    with pytest.raises(SystemExit) as exc:
        validate_profile("work", profile)
    assert exc.value.code == 1
    stderr = capsys.readouterr().err
    assert "token_dir" in stderr
    assert "./token" in stderr


# ---------------------------------------------------------------------------
# get_profile — reserved name "all"
# ---------------------------------------------------------------------------

def test_get_profile_reserved_name_all_exits(tmp_path, capsys):
    config = {"default": _minimal_profile(tmp_path)}
    with pytest.raises(SystemExit) as exc:
        get_profile(config, "all")
    assert exc.value.code == 1
    stderr = capsys.readouterr().err
    assert '"all" is reserved' in stderr


def test_get_profile_reserved_all_does_not_call_validate(tmp_path, capsys):
    """Ensure we exit before attempting to look up or validate "all" as a profile."""
    config = {"all": _minimal_profile(tmp_path)}
    with pytest.raises(SystemExit):
        get_profile(config, "all")
    stderr = capsys.readouterr().err
    assert "reserved" in stderr


# ---------------------------------------------------------------------------
# get_profile — profile not found (generic)
# ---------------------------------------------------------------------------

def test_get_profile_not_found_exits(tmp_path, capsys):
    config = {
        "personal": _minimal_profile(tmp_path),
        "work": _minimal_profile(tmp_path),
    }
    with pytest.raises(SystemExit) as exc:
        get_profile(config, "staging")
    assert exc.value.code == 1
    stderr = capsys.readouterr().err
    assert '"staging" not found' in stderr
    assert "personal" in stderr
    assert "work" in stderr


# ---------------------------------------------------------------------------
# get_profile — no default profile (distinct message)
# ---------------------------------------------------------------------------

def test_get_profile_no_default_exits(tmp_path, capsys):
    config = {
        "personal": _minimal_profile(tmp_path),
        "work": _minimal_profile(tmp_path),
    }
    with pytest.raises(SystemExit) as exc:
        get_profile(config, "default")
    assert exc.value.code == 1
    stderr = capsys.readouterr().err
    assert 'No "default" profile found' in stderr
    assert "personal" in stderr
    assert "work" in stderr


def test_get_profile_no_default_message_differs_from_not_found(tmp_path, capsys):
    config = {"personal": _minimal_profile(tmp_path)}

    with pytest.raises(SystemExit):
        get_profile(config, "default")
    default_err = capsys.readouterr().err

    with pytest.raises(SystemExit):
        get_profile(config, "nonexistent")
    generic_err = capsys.readouterr().err

    assert 'No "default" profile found' in default_err
    assert '"nonexistent" not found' in generic_err


# ---------------------------------------------------------------------------
# get_profile — success
# ---------------------------------------------------------------------------

def test_get_profile_found_returns_profile_dict(tmp_path):
    profile_data = _minimal_profile(tmp_path)
    config = {"personal": profile_data, "work": _minimal_profile(tmp_path)}
    result = get_profile(config, "personal")
    assert result["destination"] == profile_data["destination"]


def test_get_profile_calls_validate(tmp_path, capsys):
    """get_profile should exit if the profile fails validation."""
    config = {"personal": {"destination": str(tmp_path / "photos")}}  # missing token_dir
    with pytest.raises(SystemExit):
        get_profile(config, "personal")
    stderr = capsys.readouterr().err
    assert "missing required field" in stderr
