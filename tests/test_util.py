import pytest
from pathlib import Path

from aprx_tools.util import src_dir_for, aprx_for_src_dir, is_aprx_src_dir


def test_src_dir_for_bare_name():
    assert src_dir_for(Path("simple.aprx")) == Path("simple.aprx.src")


def test_src_dir_for_preserves_parent():
    assert src_dir_for(Path("/some/path/simple.aprx")) == Path("/some/path/simple.aprx.src")


def test_aprx_for_src_dir():
    assert aprx_for_src_dir(Path("simple.aprx.src")) == Path("simple.aprx")


def test_aprx_for_src_dir_preserves_parent():
    assert aprx_for_src_dir(Path("/some/path/simple.aprx.src")) == Path("/some/path/simple.aprx")


def test_aprx_for_src_dir_raises_on_non_conforming():
    with pytest.raises(ValueError):
        aprx_for_src_dir(Path("simple"))


def test_aprx_for_src_dir_raises_on_plain_aprx():
    with pytest.raises(ValueError):
        aprx_for_src_dir(Path("simple.aprx"))


def test_is_aprx_src_dir_true(tmp_path):
    d = tmp_path / "simple.aprx.src"
    d.mkdir()
    (d / "GISProject.json").write_text("{}")
    assert is_aprx_src_dir(d) is True


def test_is_aprx_src_dir_false_wrong_name(tmp_path):
    d = tmp_path / "simple"
    d.mkdir()
    (d / "GISProject.json").write_text("{}")
    assert is_aprx_src_dir(d) is False


def test_is_aprx_src_dir_false_missing_gisproject(tmp_path):
    d = tmp_path / "simple.aprx.src"
    d.mkdir()
    assert is_aprx_src_dir(d) is False
