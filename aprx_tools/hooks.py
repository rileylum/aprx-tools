"""Logic executed by the installed git hooks."""

import json
import subprocess
import sys
from pathlib import Path

from .explode import explode
from .pack import pack
from .project_config import ProjectConfig
from .transform import SubstitutionError, explode_transform, pack_transform
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


def _has_head(root: Path) -> bool:
    """True once the repo has at least one commit (``HEAD`` resolves)."""
    return subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", "HEAD"],
        cwd=root, capture_output=True,
    ).returncode == 0


def _unstage(root: Path, rel: str) -> None:
    """Drop *rel* from the index. ``git reset HEAD <path>`` needs a ``HEAD`` to reset
    against and fails fatally on the very first commit (no ``HEAD`` yet, so the whole
    hook would abort); there the file can only be newly-added, so ``git rm --cached``
    removes the index entry without touching the work tree."""
    if _has_head(root):
        _git_run(root, "reset", "HEAD", rel)
    else:
        _git_run(root, "rm", "--cached", "--quiet", rel)


def _aprx_for(src_dir: Path) -> Path:
    """map.aprx.src → map.aprx (Path.stem drops the trailing .src)."""
    return src_dir.parent / src_dir.stem


def _is_env_project(project_dir: Path) -> bool:
    """True iff the Project at *project_dir* declares **environment mode**.

    Mode is read from the committed ``aprx.json`` via ``ProjectConfig`` (ADR-0001),
    never sniffed from the presence of stray files — since every Project (simple ones
    too) now carries an ``aprx.json``, presence-sniffing would mis-classify a simple
    Project as env-managed and never stage its binary.

    A Project whose declaration can't be read returns ``False`` here. That is safe
    *only* because every caller of this predicate treats a non-env answer as "leave it
    alone" (the ``_refresh_env_sources`` sweep skips it; it never bare-explodes). The
    leak-sensitive path — exploding a *staged* binary — does **not** use this fail-open
    predicate; it loads ``ProjectConfig`` strictly so an undeclared Project blocks the
    commit (ADR-0001) instead of being bare-exploded as if it were simple."""
    try:
        return ProjectConfig.load(project_dir).is_env
    except SystemExit:
        return False


def _containing_src_dir(root: Path, rel: str) -> "Path | None":
    """The ``.aprx.src`` directory that contains staged path *rel* (so a Project nested
    in a monorepo subdirectory is found, not just one at the repo root), or ``None``."""
    path = root / rel
    for ancestor in (path, *path.parents):
        if ancestor == root:
            break
        if is_aprx_src_dir(ancestor):
            return ancestor
    return None


# --------------------------------------------------------------------------- #
# pre-commit
# --------------------------------------------------------------------------- #

def _refresh_env_sources(root: Path) -> set:
    """Environment-mode projects: the .aprx is a gitignored build artifact, so
    re-explode each working .aprx into **neutral** (tokenised) source and stage the
    source only — the binary is never committed. Returns the set of src dirs handled
    this way (skipped by the simple path)."""
    handled = set()
    for src_dir in iter_src_dirs(root):
        project_dir = src_dir.parent
        if not _is_env_project(project_dir):
            continue
        # Marked handled even if the refresh below fails, so the simple pass never
        # steps in and stages this env project's binary.
        handled.add(src_dir.resolve())
        aprx = _aprx_for(src_dir)
        if not aprx.exists():
            continue
        try:
            # Inject the env transform so source is tokenised. A bare explode() would
            # default to IDENTITY and stage *raw* connection strings (the leak 0004
            # left open); explode_transform is the same composition-root helper the CLI
            # dispatch uses, so the two roots can never drift.
            explode(str(aprx), str(src_dir), transform=explode_transform(project_dir))
        except (SystemExit, SubstitutionError) as e:
            # A misconfigured env project (no connections/*.json yet, or a connection
            # string registered in none of them) must not abort the *whole* commit —
            # this sweep runs over every project on every commit, so one bad project
            # would block unrelated work and dump a traceback. Skipping never bare-
            # explodes, so no raw string leaks; pre-push/`verify` is the gate that
            # actually blocks until it's fixed.
            print(f"  aprx-tools: skipping {src_dir.name} — {e}", file=sys.stderr)
            continue
        _git_run(root, "add", str(src_dir.relative_to(root)))
    return handled


def hook_pre_commit() -> None:
    root = _git_root()

    # Env-mode projects first (refresh tokenised src; never stage a binary).
    handled = _refresh_env_sources(root)

    staged = _staged(root)

    # Step 1: a staged .aprx. Mode is read **strictly** here (not via the fail-open
    # _is_env_project): a staged binary is about to be turned into committed source, so
    # an undeclared/unreadable Project must block the commit (ProjectConfig.load exits
    # with the `aprx install` hint, ADR-0001) rather than be bare-exploded as if simple
    # — that bare explode is exactly the raw-connection-string leak this issue closes.
    #   * env mode  → the binary is never committed (its neutral src was refreshed
    #                 above), so unstage it;
    #   * simple    → explode (IDENTITY is faithful) and stage its src; the binary is
    #                 unstaged here and re-added, normalised, in step 2.
    for rel in list(staged):
        if not rel.endswith(".aprx"):
            continue
        aprx_abs = root / rel
        if ProjectConfig.load(aprx_abs.parent).is_env:
            _unstage(root, rel)
            continue
        src_dir = aprx_abs.parent / (aprx_abs.name + ".src")
        explode(str(aprx_abs), str(src_dir))
        _git_run(root, "add", str(src_dir.relative_to(root)))
        _unstage(root, rel)

    staged = _staged(root)

    # Step 2: staged src dirs are packed and the .aprx staged. This covers the normal
    # simple-mode workflow and merge-conflict resolution (developer edited src JSON
    # directly). Env-mode src dirs are skipped — their binary is built locally, not
    # committed.
    packed: set = set()
    for rel in staged:
        src_top = _containing_src_dir(root, rel)
        if (src_top is None or src_top in packed
                or src_top.resolve() in handled):
            continue
        aprx_path = _aprx_for(src_top)
        pack(str(src_top), str(aprx_path))
        _git_run(root, "add", str(aprx_path.relative_to(root)))
        packed.add(src_top)


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
        project_dir = sd.resolve().parent

        # Read the declared Mode (ADR-0001) — never sniffed. A Project with no
        # declaration (e.g. not yet `aprx install`ed) can't be resolved strictly, so
        # skip it: a never-blocking post-* hook reports and moves on rather than crashing.
        try:
            cfg = ProjectConfig.load(project_dir)
        except SystemExit as e:
            print(f"  aprx-tools: skipping {sd.name} — {e}", file=sys.stderr)
            continue

        # An env-mode Project with no resolvable connections file can't be built into a
        # working copy without emitting unsubstituted tokens — skip with a hint rather
        # than leak a broken binary full of @@tokens@@.
        if cfg.is_env and conn.resolve_connections_file(project_dir, env, None) is None:
            print(f"  aprx-tools: skipping {sd.name} — no {conn.LOCAL_FILE} "
                  f"(copy {conn.LOCAL_FILE}.example and fill in your connections)",
                  file=sys.stderr)
            continue

        # pack is connection-ignorant (ADR-0002); pack_transform carries the env
        # substitution (or IDENTITY for simple mode). These post-* hooks are documented
        # never to block, so a Project whose env is missing a key (SubstitutionError) or
        # otherwise won't resolve (sys.exit) downgrades to a skip, not a crashed hook.
        try:
            transform = pack_transform(project_dir, env=env)
            pack(str(sd), str(_aprx_for(sd)), transform=transform)
        except (SystemExit, SubstitutionError, json.JSONDecodeError) as e:
            # JSONDecodeError covers a hand-broken connections/local.json (load_connections
            # parses it raw): these post-* hooks are documented never to block, so a
            # malformed file downgrades to a skip instead of crashing the rebuild.
            print(f"  aprx-tools: skipping {sd.name} — {e}", file=sys.stderr)


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
