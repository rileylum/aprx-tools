"""Logic executed by the installed git hooks."""

import subprocess
import sys
from pathlib import Path

from .explode import explode
from .pack import pack
from .util import is_aprx_src_dir, iter_src_dirs
from . import connections as conn


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


def _aprx_for(src_dir: Path) -> Path:
    """map.aprx.src → map.aprx (Path.stem drops the trailing .src)."""
    return src_dir.parent / src_dir.stem


# --------------------------------------------------------------------------- #
# pre-commit
# --------------------------------------------------------------------------- #

def _refresh_env_sources(root: Path) -> set:
    """Environment-managed projects: the .aprx is a gitignored build artifact, so
    re-explode each working .aprx into its tokenised src and stage the src only.
    Returns the set of src dirs handled this way (skipped by the simple path)."""
    handled = set()
    for src_dir in iter_src_dirs(root):
        if conn.find_project_config(src_dir) is None:
            continue
        handled.add(src_dir.resolve())
        aprx = _aprx_for(src_dir)
        if aprx.exists():
            explode(str(aprx), str(src_dir))
            _git_run(root, "add", str(src_dir.relative_to(root)))
    return handled


def hook_pre_commit() -> None:
    root = _git_root()

    # Env-managed projects first (refresh tokenised src; never stage a binary).
    handled = _refresh_env_sources(root)

    staged = _staged(root)

    # Simple mode, step 1: a staged .aprx is exploded and its src staged; the
    # binary is unstaged and re-added (normalised) in step 2.
    for rel in list(staged):
        if not rel.endswith(".aprx"):
            continue
        aprx_abs = root / rel
        src_dir = aprx_abs.parent / (aprx_abs.name + ".src")
        explode(str(aprx_abs), str(src_dir))
        _git_run(root, "add", str(src_dir.relative_to(root)))
        _git_run(root, "reset", "HEAD", rel)

    staged = _staged(root)

    # Simple mode, step 2: staged src dirs are packed and the .aprx staged. This
    # covers the normal workflow and merge-conflict resolution. Env-managed src
    # dirs are skipped — their binary is built locally, not committed.
    packed: set = set()
    for rel in staged:
        top = root / Path(rel).parts[0]
        if top in packed or top.resolve() in handled or not is_aprx_src_dir(top):
            continue
        aprx_path = _aprx_for(top)
        pack(str(top), str(aprx_path))
        _git_run(root, "add", str(aprx_path.relative_to(root)))
        packed.add(top)


# --------------------------------------------------------------------------- #
# post-merge / post-checkout / post-stash — rebuild local working copies
# --------------------------------------------------------------------------- #

def build_working_copies(root: Path = None, src_dir: str = None, env: str = None) -> None:
    """Rebuild the working .aprx for one or all src dirs from the resolved
    connections (default local.json). Env-managed projects without a resolvable
    connections file are skipped with a hint rather than producing a binary full
    of unsubstituted tokens."""
    if src_dir is not None:
        targets = [Path(src_dir)]
    else:
        if root is None:
            root = _git_root()
        targets = list(iter_src_dirs(root))

    for sd in targets:
        project = conn.find_project_config(sd)
        if (project is not None and conn.connection_files(project)
                and conn.resolve_connections_file(project, env, None) is None):
            print(f"  aprx-tools: skipping {sd.name} — no local.json "
                  f"(copy local.json.example and fill in your connections)",
                  file=sys.stderr)
            continue
        pack(str(sd), str(_aprx_for(sd)), env=env)


def hook_post_merge() -> None:
    build_working_copies(_git_root())


def hook_post_checkout() -> None:
    build_working_copies(_git_root())


def hook_post_stash() -> None:
    """Repack all .aprx.src directories after a stash pop so the local .aprx
    stays in sync with the checked-out src files."""
    build_working_copies(_git_root())


def hook_pre_push() -> int:
    """Pre-push gate — the local mirror of the CI `aprx verify` check. Blocks a
    push whose source is untokenised or won't build for every environment.
    Returns the verify exit code so the hook can fail the push."""
    from .verify import verify
    return verify()
