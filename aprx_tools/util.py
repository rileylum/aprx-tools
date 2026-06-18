from pathlib import Path


def src_dir_for(aprx_path: Path) -> Path:
    """map.aprx → map.aprx.src  (adjacent to the .aprx file)."""
    return aprx_path.parent / (aprx_path.name + ".src")


def aprx_for_src_dir(src_dir: Path) -> Path:
    """map.aprx.src → map.aprx  (Path.stem strips the last extension)."""
    if not src_dir.name.endswith(".aprx.src"):
        raise ValueError(f"{src_dir.name!r} does not follow the <name>.aprx.src convention")
    return src_dir.parent / src_dir.stem


def is_aprx_src_dir(path: Path) -> bool:
    return (
        path.is_dir()
        and path.name.endswith(".aprx.src")
        and (path / "GISProject.json").exists()
    )


def iter_src_dirs(root: Path):
    """Yield every .aprx.src directory under *root* (located via GISProject.json)."""
    for gis_project in Path(root).rglob("GISProject.json"):
        src_dir = gis_project.parent
        if is_aprx_src_dir(src_dir):
            yield src_dir
