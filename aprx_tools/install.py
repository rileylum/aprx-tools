"""Install git hooks into the current (or specified) repository."""

import stat
import subprocess
import sys
from pathlib import Path

MARKER = "managed-by: aprx-tools"

# Probe for a repo-local virtualenv Python, falling back to python3.
_PYTHON_PROBE = """\
REPO_ROOT=$(git rev-parse --show-toplevel)

PYTHON=python3
for candidate in \\
    "$REPO_ROOT/.venv/bin/python3" \\
    "$REPO_ROOT/venv/bin/python3"  \\
    "$REPO_ROOT/env/bin/python3";  \\
do
    if [ -x "$candidate" ]; then PYTHON="$candidate"; break; fi
done
"""


def _hook_script(hook_name: str, blocking: bool, hint: bool = False) -> str:
    """Build a hook script. Blocking hooks fail the git operation on error;
    non-blocking hooks (post-*) never block it. `hint` adds an "is aprx-tools
    installed?" message — useful when failure usually means a missing install
    (pre-commit), but not for pre-push where the command prints its own reason."""
    invoke = f'"$PYTHON" -m aprx_tools hook {hook_name}'
    if not blocking:
        tail = f"{invoke} || true\n"
    elif hint:
        tail = (
            f"{invoke} || {{\n"
            f'    echo "aprx-tools: hook failed — is aprx-tools installed? '
            f'(pip install aprx-tools)" >&2\n'
            f"    exit 1\n"
            f"}}\n"
        )
    else:
        tail = f"{invoke}\n"  # set -e propagates the exit code (and its output)
    return f"#!/usr/bin/env bash\n# {MARKER}\nset -euo pipefail\n\n{_PYTHON_PROBE}\n{tail}"


HOOKS = {
    "pre-commit": _hook_script("pre-commit", blocking=True, hint=True),
    "pre-push": _hook_script("pre-push", blocking=True),
    "post-stash": _hook_script("post-stash", blocking=False),
    "post-merge": _hook_script("post-merge", blocking=False),
    "post-checkout": _hook_script("post-checkout", blocking=False),
}


def _find_git_root(start: Path) -> Path:
    try:
        return Path(subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=start, text=True, stderr=subprocess.DEVNULL
        ).strip())
    except subprocess.CalledProcessError:
        sys.exit("aprx-tools: not inside a git repository")


def install_hooks(repo_root: Path = None) -> None:
    if repo_root is None:
        repo_root = _find_git_root(Path.cwd())

    hooks_dir = repo_root / ".git" / "hooks"
    hooks_dir.mkdir(exist_ok=True)

    for name, content in HOOKS.items():
        hook_path = hooks_dir / name

        if hook_path.exists():
            existing = hook_path.read_text()
            if MARKER in existing:
                # Already installed — overwrite with latest version.
                pass
            else:
                print(
                    f"  aprx-tools: {name} hook already exists and is not ours.\n"
                    f"  Add this line to {hook_path}:\n"
                    f"    python3 -m aprx_tools hook {name}"
                )
                continue

        hook_path.write_text(content)
        hook_path.chmod(hook_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        print(f"  aprx-tools: installed {name} hook")
