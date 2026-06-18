import json
import zipfile

import pytest

from aprx_tools import connections as conn
from aprx_tools.explode import explode
from aprx_tools.pack import pack
from aprx_tools.compare import compare


# --------------------------------------------------------------------------- #
# Engine: tokenize / substitute
# --------------------------------------------------------------------------- #

def _doc(value):
    return {"layers": [{"dataConnection": {"workspaceConnectionString": value,
                                           "dataset": "pts"}}]}


def _conn_str(doc):
    return doc["layers"][0]["dataConnection"]["workspaceConnectionString"]


def test_tokenize_then_substitute_roundtrip():
    doc = _doc("DATABASE=.\\acme.gdb")
    tokenized, unknown = conn.tokenize(doc, {"DATABASE=.\\acme.gdb": "main"})
    assert _conn_str(tokenized) == "@@main@@"
    assert unknown == set()

    restored, missing = conn.substitute(tokenized, {"main": "SERVER=uat;DATABASE=acme"})
    assert _conn_str(restored) == "SERVER=uat;DATABASE=acme"
    assert missing == set()


def test_tokenize_flags_unknown_value():
    _, unknown = conn.tokenize(_doc("DATABASE=mystery"), {"DATABASE=known": "k"})
    assert unknown == {"DATABASE=mystery"}


def test_tokenize_leaves_existing_token():
    doc, unknown = conn.tokenize(_doc("@@main@@"), {"DATABASE=x": "main"})
    assert _conn_str(doc) == "@@main@@"
    assert unknown == set()


def test_substitute_flags_missing_key():
    _, missing = conn.substitute(_doc("@@nope@@"), {"main": "x"})
    assert missing == {"nope"}


def test_only_configured_fields_are_touched():
    doc = {"workspaceConnectionString": "v", "somethingElse": "v"}
    tokenized, _ = conn.tokenize(doc, {"v": "k"})
    assert tokenized["workspaceConnectionString"] == "@@k@@"
    assert tokenized["somethingElse"] == "v"  # untouched


def test_configurable_fields():
    doc = {"serviceUrl": "https://dev/svc"}
    tokenized, _ = conn.tokenize(doc, {"https://dev/svc": "svc"}, fields=("serviceUrl",))
    assert tokenized["serviceUrl"] == "@@svc@@"


def test_backslash_value_reserialises_validly(tmp_path):
    # A Windows path with backslashes must survive substitution as valid JSON.
    doc = _doc("@@main@@")
    restored, _ = conn.substitute(doc, {"main": "DATABASE=C:\\data\\acme.gdb"})
    reparsed = json.loads(json.dumps(restored))
    assert _conn_str(reparsed) == "DATABASE=C:\\data\\acme.gdb"


# --------------------------------------------------------------------------- #
# Engine: reverse map
# --------------------------------------------------------------------------- #

def test_reverse_map_unions_envs(tmp_path):
    (tmp_path / "dev.json").write_text(json.dumps({"main": "DEV"}))
    (tmp_path / "uat.json").write_text(json.dumps({"main": "UAT"}))
    rev = conn.build_reverse_map([tmp_path / "dev.json", tmp_path / "uat.json"])
    assert rev == {"DEV": "main", "UAT": "main"}


def test_reverse_map_value_collision_errors(tmp_path):
    (tmp_path / "a.json").write_text(json.dumps({"main": "SAME"}))
    (tmp_path / "b.json").write_text(json.dumps({"other": "SAME"}))
    with pytest.raises(SystemExit):
        conn.build_reverse_map([tmp_path / "a.json", tmp_path / "b.json"])


# --------------------------------------------------------------------------- #
# Engine: resolution precedence
# --------------------------------------------------------------------------- #

def test_resolve_explicit_connections_file(env_project):
    p = conn.resolve_connections_file(env_project.dir, None,
                                      str(env_project.dir / "local.json"))
    assert p.name == "local.json"


def test_resolve_env(env_project):
    p = conn.resolve_connections_file(env_project.dir, "uat", None)
    assert p == env_project.dir / "connections" / "uat.json"


def test_resolve_default_local(env_project):
    p = conn.resolve_connections_file(env_project.dir, None, None)
    assert p.name == "local.json"


def test_resolve_none_when_no_local(tmp_path):
    assert conn.resolve_connections_file(tmp_path, None, None) is None


def test_resolve_missing_explicit_errors(env_project):
    with pytest.raises(SystemExit):
        conn.resolve_connections_file(env_project.dir, None, "nope.json")


def test_resolve_missing_env_errors(env_project):
    with pytest.raises(SystemExit):
        conn.resolve_connections_file(env_project.dir, "prd", None)


# --------------------------------------------------------------------------- #
# Integration: explode + pack through a project
# --------------------------------------------------------------------------- #

def _packed_layer(out):
    with zipfile.ZipFile(out) as zf:
        return zf.read("map/test_points.json").decode("utf-8")


def test_explode_tokenizes(env_project):
    src = explode(str(env_project.aprx))
    pts = (src / "map" / "test_points.json").read_text()
    assert "@@main@@" in pts
    assert env_project.value not in pts


def test_pack_substitutes_for_env(env_project):
    src = explode(str(env_project.aprx))
    out = pack(str(src), str(env_project.dir / "map.uat.aprx"), env="uat")
    data = _packed_layer(out)
    assert env_project.uat_value in data
    assert "@@main@@" not in data


def test_roundtrip_identical_with_local(env_project):
    src = explode(str(env_project.aprx))
    rebuilt = pack(str(src), str(env_project.dir / "rebuilt.aprx"),
                   connections_file=str(env_project.dir / "local.json"))
    assert compare(str(env_project.aprx), str(rebuilt)) is False


def test_pack_missing_key_fails(env_project):
    src = explode(str(env_project.aprx))
    (env_project.dir / "connections" / "broken.json").write_text("{}")
    with pytest.raises(SystemExit):
        pack(str(src), str(env_project.dir / "x.aprx"), env="broken")


def test_explode_unknown_connection_fails(env_project):
    # Point every connection file away from the fixture's real value.
    for name in ("dev.json", "uat.json"):
        (env_project.dir / "connections" / name).write_text(json.dumps({"main": "OTHER"}))
    (env_project.dir / "local.json").write_text(json.dumps({"main": "OTHER"}))
    with pytest.raises(SystemExit):
        explode(str(env_project.aprx))


def test_simple_mode_untouched(tmp_path, simple_aprx):
    # No connection files anywhere → explode keeps the raw connection string.
    src = explode(str(simple_aprx), str(tmp_path / "simple.aprx.src"))
    pts = (src / "map" / "test_points.json").read_text()
    assert "@@" not in pts
    assert ".gdb" in pts
