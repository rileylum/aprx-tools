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
