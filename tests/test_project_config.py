"""Tests for the ProjectConfig.load seam (issue 0002).

ProjectConfig is the single home for the resolution ritual: it reads a Project's
declared mode/fields/token from the committed ``aprx.json`` and, for environment-mode
Projects, discovers the connection files and builds the token<->value maps. These tests
drive only that seam — they build a temporary ``aprx.json`` (plus ``connections/`` for
the env cases) and assert external behaviour, never private helper shapes.
"""

import json

import pytest

from aprx_tools import connections as conn
from aprx_tools.project_config import ProjectConfig


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _write_config(project_dir, **fields):
    (project_dir / conn.CONFIG_FILENAME).write_text(
        json.dumps(fields), encoding="utf-8"
    )


# --------------------------------------------------------------------------- #
# Reading mode / fields / token
# --------------------------------------------------------------------------- #

def test_load_reads_simple_mode(tmp_path):
    _write_config(tmp_path, mode="simple")
    cfg = ProjectConfig.load(tmp_path)
    assert cfg.mode == "simple"
    assert cfg.is_env is False
    # defaults apply when fields/token are omitted
    assert tuple(cfg.fields) == conn.DEFAULT_FIELDS
    assert cfg.token == conn.DEFAULT_TOKEN


def test_load_reads_env_mode_with_explicit_fields_and_token(tmp_path):
    _write_config(tmp_path, mode="env", fields=["url", "wcs"], token="<<{key}>>")
    cfg = ProjectConfig.load(tmp_path)
    assert cfg.mode == "env"
    assert cfg.is_env is True
    assert tuple(cfg.fields) == ("url", "wcs")
    assert cfg.token == "<<{key}>>"


# --------------------------------------------------------------------------- #
# Strict resolution (ADR-0001): no aprx.json / no mode -> "run aprx install"
# --------------------------------------------------------------------------- #

def test_load_missing_config_directs_to_install(tmp_path):
    with pytest.raises(SystemExit) as exc:
        ProjectConfig.load(tmp_path)
    assert "aprx install" in str(exc.value)


def test_load_config_without_mode_directs_to_install(tmp_path):
    _write_config(tmp_path, fields=["url"])  # has config, but no mode
    with pytest.raises(SystemExit) as exc:
        ProjectConfig.load(tmp_path)
    assert "aprx install" in str(exc.value)


def test_load_rejects_unknown_mode(tmp_path):
    _write_config(tmp_path, mode="production")
    with pytest.raises(SystemExit) as exc:
        ProjectConfig.load(tmp_path)
    assert "production" in str(exc.value)


def test_load_rejects_token_without_key_placeholder(tmp_path):
    _write_config(tmp_path, mode="env", token="@@no-placeholder@@")
    with pytest.raises(SystemExit) as exc:
        ProjectConfig.load(tmp_path)
    assert "{key}" in str(exc.value)


# --------------------------------------------------------------------------- #
# Environment mode: connection-file discovery + map building
# --------------------------------------------------------------------------- #

def _env_project(tmp_path, dev=None, uat=None, local=None):
    """An env-mode project dir with aprx.json + the given connection files."""
    _write_config(tmp_path, mode="env")
    (tmp_path / conn.CONNECTIONS_DIR).mkdir()
    if dev is not None:
        (tmp_path / conn.CONNECTIONS_DIR / "dev.json").write_text(json.dumps(dev))
    if uat is not None:
        (tmp_path / conn.CONNECTIONS_DIR / "uat.json").write_text(json.dumps(uat))
    if local is not None:
        (tmp_path / conn.LOCAL_FILE).write_text(json.dumps(local))
    return tmp_path


def test_env_discovers_connection_files(tmp_path):
    _env_project(tmp_path, dev={"main": "DEV"}, uat={"main": "UAT"}, local={"main": "DEV"})
    cfg = ProjectConfig.load(tmp_path)
    names = sorted(p.name for p in cfg.connection_files())
    assert names == ["dev.json", "local.json", "uat.json"]


def test_env_reverse_map_unions_environments(tmp_path):
    _env_project(tmp_path, dev={"main": "DEV"}, uat={"main": "UAT"})
    cfg = ProjectConfig.load(tmp_path)
    # value -> token key, unioned across every environment file
    assert cfg.reverse_map() == {"DEV": "main", "UAT": "main"}


def test_env_forward_map_for_chosen_environment(tmp_path):
    _env_project(tmp_path, dev={"main": "DEV"}, uat={"main": "UAT"}, local={"main": "DEV"})
    cfg = ProjectConfig.load(tmp_path)
    # token key -> value for the named environment
    assert cfg.forward_map(env="uat") == {"main": "UAT"}
    # default (no flag) falls back to local.json
    assert cfg.forward_map() == {"main": "DEV"}


def test_env_reverse_map_value_collision_is_hard_error(tmp_path):
    # one connection value mapped to two different keys is ambiguous
    _env_project(tmp_path, dev={"main": "SAME"}, uat={"other": "SAME"})
    cfg = ProjectConfig.load(tmp_path)
    with pytest.raises(SystemExit):
        cfg.reverse_map()
