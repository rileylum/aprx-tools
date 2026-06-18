"""`aprx verify` — a single exit-coded gate for CI.

The check that every CI system calls. It does NOT need GitHub — it is a plain
command that exits non-zero on failure, so GitHub Actions, GitLab CI, Azure
Pipelines, or any runner can invoke it identically.

For an environment-managed project it asserts:
  * the committed source is fully tokenised (no raw connection string leaked in —
    i.e. nobody committed without the hooks), and
  * every token the source references has a value in every environment file (the
    project actually builds for each environment).

For a simple (single-environment) project it asserts the committed .aprx is in
sync with its source.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from . import connections as conn
from .util import iter_src_dirs
from .pack import pack
from .compare import compare


def _project_root() -> Path:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], text=True, stderr=subprocess.DEVNULL
        )
        return Path(out.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Path.cwd()


def _verify_env_project(src_dir: Path, project: Path, env: str, problems: list) -> None:
    cfg = conn.load_config(project)
    fields, token = cfg["fields"], cfg["token"]

    referenced: set = set()
    raw: set = set()
    for jf in sorted(src_dir.rglob("*.json")):
        try:
            obj = json.loads(jf.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        keys, raws = conn.scan_tokens(obj, fields, token)
        referenced |= keys
        raw |= raws

    if raw:
        problems.append(
            f"{src_dir.name}: raw connection string(s) in source — committed without "
            f"hooks?\n      " + "\n      ".join(sorted(raw))
        )

    conn_dir = project / conn.CONNECTIONS_DIR
    if env:
        env_files = [conn_dir / f"{env}.json"]
        if not env_files[0].exists():
            problems.append(f"{src_dir.name}: no connections file for env {env!r}")
            return
    else:
        env_files = sorted(conn_dir.glob("*.json")) if conn_dir.is_dir() else []
        if not env_files:
            problems.append(f"{src_dir.name}: no connections/*.json to verify against")
            return

    for env_file in env_files:
        missing = referenced - set(conn.load_connections(env_file))
        if missing:
            problems.append(
                f"{src_dir.name}: {env_file.name} missing keys: " + ", ".join(sorted(missing))
            )


def _verify_simple_project(src_dir: Path, problems: list) -> None:
    aprx = src_dir.parent / src_dir.stem
    if not aprx.exists():
        return  # nothing committed to compare against
    with tempfile.TemporaryDirectory() as tmp:
        rebuilt = pack(str(src_dir), str(Path(tmp) / aprx.name))
        if compare(str(aprx), str(rebuilt)):
            problems.append(
                f"{src_dir.name}: committed {aprx.name} is out of sync with its source "
                f"(committed without hooks?)"
            )


def verify(src_dir: str = None, env: str = None) -> int:
    if src_dir is not None:
        targets = [Path(src_dir)]
    else:
        targets = list(iter_src_dirs(_project_root()))

    if not targets:
        print("aprx verify: no .aprx.src directories found", file=sys.stderr)
        return 1

    problems: list = []
    for sd in targets:
        project = conn.find_project_config(sd)
        if project is not None:
            _verify_env_project(sd, project, env, problems)
        else:
            _verify_simple_project(sd, problems)

    if problems:
        print(f"aprx verify: FAILED ({len(problems)} problem(s))", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    print(f"aprx verify: OK ({len(targets)} project(s) checked)")
    return 0
