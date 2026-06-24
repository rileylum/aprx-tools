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


def test_load_rejects_malformed_json(tmp_path):
    # A merge-conflict / typo'd aprx.json must fail loudly with our diagnostic,
    # not a raw json.JSONDecodeError traceback.
    (tmp_path / conn.CONFIG_FILENAME).write_text("{not: valid", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        ProjectConfig.load(tmp_path)
    assert str(tmp_path / conn.CONFIG_FILENAME) in str(exc.value)


@pytest.mark.parametrize("payload", ["42", "null", '"simple"', "[]"])
def test_load_rejects_non_object_config(tmp_path, payload):
    # A top-level scalar/list must not crash with TypeError or be misread as
    # "declares no mode" — it is simply not a valid config object.
    (tmp_path / conn.CONFIG_FILENAME).write_text(payload, encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        ProjectConfig.load(tmp_path)
    assert "JSON object" in str(exc.value)


def test_load_rejects_string_fields(tmp_path):
    # A string `fields` would be shredded into single characters by tuple(),
    # silently matching nothing and leaking raw connection strings. Reject it.
    _write_config(tmp_path, mode="env", fields="workspaceConnectionString")
    with pytest.raises(SystemExit) as exc:
        ProjectConfig.load(tmp_path)
    assert "fields" in str(exc.value)


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


def test_env_forward_map_for_chosen_environment(tmp_path):
    _env_project(tmp_path, dev={"main": "DEV"}, uat={"main": "UAT"}, local={"main": "DEV"})
    cfg = ProjectConfig.load(tmp_path)
    # token key -> value for the named environment
    assert cfg.forward_map(env="uat") == {"main": "UAT"}
    # default (no flag) falls back to local.json
    assert cfg.forward_map() == {"main": "DEV"}


# --------------------------------------------------------------------------- #
# Mode is the master switch: env-only helpers reject a simple-mode project
# --------------------------------------------------------------------------- #

def test_simple_mode_rejects_substitution_helpers(tmp_path):
    # Even with a stray local.json present, a simple-mode project must not
    # expose connection maps — substitution is an environment-mode concept.
    _write_config(tmp_path, mode="simple")
    (tmp_path / conn.LOCAL_FILE).write_text(json.dumps({"main": "X"}))
    cfg = ProjectConfig.load(tmp_path)
    for call in (cfg.committed_reverse_map, cfg.forward_map):
        with pytest.raises(SystemExit) as exc:
            call()
        assert "simple" in str(exc.value)
