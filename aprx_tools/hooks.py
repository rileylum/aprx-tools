"""Logic executed by the installed git hooks."""

import subprocess
import sys
from pathlib import Path

from .explode import explode
from .pack import pack
from .util import is_aprx_src_dir


def _git_root() -> Path:
    return Path(subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"], text=True
    ).strip())


def _git(root: Path, *args) -> str:
    return subprocess.check_output(["git"] + list(args), cwd=root, text=True).strip()


def _git_run(root: Path, *args) -> None:
    subprocess.run(["git"] + list(args), cwd=root, check=True, capture_output=True)


def _staged(root: Path) -> set:
    output = _git(root, "diff", "--cached", "--name-only", "--diff-filter=ACM")
    return set(output.splitlines()) if output else set()


def hook_pre_commit() -> None:
    root = _git_root()
    staged = _staged(root)

    # Step 1: for any staged .aprx, explode it and stage the resulting src dir.
    # The binary is removed from staging; we'll re-add it (normalised) in step 2.
    for rel in list(staged):
        if not rel.endswith(".aprx"):
            continue
        aprx_abs = root / rel
        src_dir = aprx_abs.parent / (aprx_abs.name + ".src")
        explode(str(aprx_abs), str(src_dir))
        _git_run(root, "add", str(src_dir.relative_to(root)))
        _git_run(root, "reset", "HEAD", rel)

    # Refresh: newly staged src files are now visible.
    staged = _staged(root)

    # Step 2: for any staged files inside a .aprx.src directory, pack and stage
    # the .aprx.  This covers both the normal ArcGIS workflow (step 1 just added
    # src files) and merge-conflict resolution (developer edited src files directly).
    packed: set = set()
    for rel in staged:
        top = root / Path(rel).parts[0]
        if top in packed or not is_aprx_src_dir(top):
            continue
        aprx_path = top.parent / top.stem   # map.aprx.src → map.aprx
        pack(str(top), str(aprx_path))
        _git_run(root, "add", str(aprx_path.relative_to(root)))
        packed.add(top)


def hook_post_stash() -> None:
    """Repack all .aprx.src directories after a stash pop so the local .aprx
    stays in sync with the checked-out src files."""
    root = _git_root()
    for gis_project in root.rglob("GISProject.json"):
        src_dir = gis_project.parent
        if not is_aprx_src_dir(src_dir):
            continue
        aprx_path = src_dir.parent / src_dir.stem
        pack(str(src_dir), str(aprx_path))
