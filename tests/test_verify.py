import json
import shutil

from aprx_tools.explode import explode
from aprx_tools.verify import verify


# --------------------------------------------------------------------------- #
# Environment-managed projects
# --------------------------------------------------------------------------- #

def _src(env_project):
    return env_project.dir / "map.aprx.src"


def test_verify_env_passes(env_project, explode_env):
    explode_env(env_project.aprx)             # produces tokenised source
    assert verify(str(_src(env_project))) == 0


def test_verify_fails_when_env_missing_key(env_project, explode_env):
    explode_env(env_project.aprx)
    (env_project.dir / "connections" / "uat.json").write_text("{}")   # drop the key
    assert verify(str(_src(env_project))) == 1


def test_verify_specific_env(env_project, explode_env):
    explode_env(env_project.aprx)
    assert verify(str(_src(env_project)), env="uat") == 0
    (env_project.dir / "connections" / "uat.json").write_text("{}")
    assert verify(str(_src(env_project)), env="uat") == 1


def test_verify_fails_on_raw_connection_string(env_project, explode_env):
    src = explode_env(env_project.aprx)
    pts = src / "map" / "test_points.json"
    # Simulate a commit made without the hooks: a raw connection string in source.
    raw_json = json.dumps(env_project.value)[1:-1]   # JSON-escaped, quotes stripped
    pts.write_text(pts.read_text().replace("@@main@@", raw_json))
    assert verify(str(src)) == 1


# --------------------------------------------------------------------------- #
# Simple (single-environment) projects
# --------------------------------------------------------------------------- #

def test_verify_simple_in_sync(tmp_path, simple_aprx):
    aprx = tmp_path / "simple.aprx"
    shutil.copy(simple_aprx, aprx)
    explode(str(aprx))
    assert verify(str(tmp_path / "simple.aprx.src")) == 0


def test_verify_simple_out_of_sync(tmp_path, simple_aprx):
    aprx = tmp_path / "simple.aprx"
    shutil.copy(simple_aprx, aprx)
    src = explode(str(aprx))
    gp = src / "GISProject.json"
    data = json.loads(gp.read_text())
    data["__tamper__"] = True                  # source no longer matches the binary
    gp.write_text(json.dumps(data))
    assert verify(str(src)) == 1
