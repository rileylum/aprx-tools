import json
import shutil
import types
import zipfile

import pytest
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SIMPLE_APRX = FIXTURES_DIR / "simple" / "simple.aprx"


@pytest.fixture
def simple_aprx() -> Path:
    return SIMPLE_APRX


@pytest.fixture
def exploded(tmp_path, simple_aprx) -> Path:
    """Exploded simple.aprx — reused by pack and compare tests."""
    from aprx_tools.explode import explode
    return explode(str(simple_aprx), str(tmp_path / "simple.aprx.src"))


def _first_connection_value(aprx: Path) -> str:
    """The actual workspaceConnectionString stored in the fixture."""
    from aprx_tools.connections import collect_field_values
    with zipfile.ZipFile(aprx) as zf:
        for name in zf.namelist():
            if name.endswith(".json"):
                vals = collect_field_values(json.loads(zf.read(name)))
                if vals:
                    return sorted(vals)[0]
    raise AssertionError("fixture has no connection strings")


@pytest.fixture
def env_project(tmp_path, simple_aprx):
    """An environment-managed project: map.aprx plus connections/{dev,uat}.json and
    local.json, with `dev` and `local` pointing at the fixture's real connection
    string and `uat` at a distinct one."""
    proj = tmp_path / "proj"
    (proj / "connections").mkdir(parents=True)
    aprx = proj / "map.aprx"
    shutil.copy(simple_aprx, aprx)

    value = _first_connection_value(aprx)
    uat_value = "DATABASE=uat-server;SERVER=uat"
    (proj / "connections" / "dev.json").write_text(json.dumps({"main": value}))
    (proj / "connections" / "uat.json").write_text(json.dumps({"main": uat_value}))
    (proj / "local.json").write_text(json.dumps({"main": value}))

    return types.SimpleNamespace(dir=proj, aprx=aprx, value=value, uat_value=uat_value)


# A synthetic .aprx (a plain zip of JSON) carrying several *distinct* connection
# strings of different shapes — the fixture has only one, so this exercises the
# multiple-keys path through explode / connections init without a real Pro export.
MULTI_CONN_VALUES = {
    "local":  r"DATABASE=.\acme.gdb",
    "parcels": r"\\fileserver\gis\parcels.gdb",
    "acme_prod": "SERVER=gisdb;INSTANCE=sde:postgresql:gisdb;DATABASE=acme_prod;USER=viewer",
}


@pytest.fixture
def multi_conn_aprx(tmp_path):
    proj = tmp_path / "multi"
    proj.mkdir()
    aprx = proj / "multi.aprx"
    entries = {
        "GISProject.json": {"version": "3.0"},
        "map/a.json": {"dataConnection": {"workspaceConnectionString": MULTI_CONN_VALUES["local"], "dataset": "a"}},
        "map/b.json": {"dataConnection": {"workspaceConnectionString": MULTI_CONN_VALUES["parcels"], "dataset": "b"}},
        "map/c.json": {"layer": {"dataConnection": {"workspaceConnectionString": MULTI_CONN_VALUES["acme_prod"], "dataset": "c"}}},
    }
    with zipfile.ZipFile(aprx, "w") as zf:
        for name, obj in entries.items():
            zf.writestr(name, json.dumps(obj))
    return types.SimpleNamespace(dir=proj, aprx=aprx, values=set(MULTI_CONN_VALUES.values()))
