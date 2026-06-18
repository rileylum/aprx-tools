import json

import pytest

from aprx_tools.bootstrap import _suggest_key, connections_init
from aprx_tools.explode import explode


# --------------------------------------------------------------------------- #
# _suggest_key — the only place connection-string *content* is parsed
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("value, expected", [
    (r"DATABASE=.\acme.gdb",                       "acme"),       # local file gdb
    (r"\\fileserver\gis\parcels.gdb",             "parcels"),   # UNC path
    (r"C:\connections\prod_sql.sde",              "prod_sql"),  # .sde reference
    ("SERVER=db;INSTANCE=sde:postgresql:db;DATABASE=acme_prod;USER=v", "acme_prod"),  # enterprise
    (".\\Café_Data.gdb",                          "caf_data"),  # non-ascii slugged out
])
def test_suggest_key_derives_from_shape(value, expected):
    assert _suggest_key(value, set()) == expected


def test_suggest_key_falls_back_for_opaque_values():
    # A URL has no .gdb/.sde or DATABASE= to key off → positional fallback.
    url = "http://services.arcgisonline.com/ArcGIS/rest/services/World/MapServer"
    assert _suggest_key(url, set()) == "conn1"
    assert _suggest_key(url, {"conn1"}) == "conn2"


def test_suggest_key_disambiguates_collisions():
    taken = set()
    first = _suggest_key(r"a\data.gdb", taken); taken.add(first)
    second = _suggest_key(r"b\data.gdb", taken); taken.add(second)
    assert first == "data"
    assert second == "data_2"


# --------------------------------------------------------------------------- #
# connections init — discovers every distinct string and scaffolds files
# --------------------------------------------------------------------------- #

def test_init_discovers_all_distinct_connections(multi_conn_aprx, capsys):
    connections_init(str(multi_conn_aprx.aprx))

    dev = json.loads((multi_conn_aprx.dir / "connections" / "dev.json").read_text())
    assert set(dev.values()) == multi_conn_aprx.values          # all three captured
    assert len(dev) == 3                                        # as three distinct keys
    assert (multi_conn_aprx.dir / "aprx.json").exists()
    assert (multi_conn_aprx.dir / "local.json.example").exists()


def test_init_then_explode_tokenizes_each_distinctly(multi_conn_aprx):
    connections_init(str(multi_conn_aprx.aprx))
    # use the discovered dev mapping as the local working config
    dev = (multi_conn_aprx.dir / "connections" / "dev.json").read_text()
    (multi_conn_aprx.dir / "local.json").write_text(dev)

    src = explode(str(multi_conn_aprx.aprx))

    blob = "".join(p.read_text() for p in (src / "map").glob("*.json"))
    for value in multi_conn_aprx.values:
        assert value not in blob                                # no raw strings leak
    keys = json.loads(dev).keys()
    for key in keys:
        assert f"@@{key}@@" in blob                             # each became its own token


def test_init_refuses_when_no_connections(tmp_path):
    import zipfile
    empty = tmp_path / "empty.aprx"
    with zipfile.ZipFile(empty, "w") as zf:
        zf.writestr("GISProject.json", json.dumps({"version": "3.0"}))
    with pytest.raises(SystemExit):
        connections_init(str(empty))
