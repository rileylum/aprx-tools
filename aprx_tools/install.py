"""Install git hooks into the current (or specified) repository."""

import stat
import subprocess
import sys
from pathlib import Path

MARKER = "managed-by: aprx-tools"

_PRE_COMMIT = """\
#!/usr/bin/env bash
# {marker}
set -euo pipefail

REPO_ROOT=$(git rev-parse --show-toplevel)

# Prefer a virtual-environment Python if one exists in the repo root.
PYTHON=python3
for candidate in \\
    "$REPO_ROOT/.venv/bin/python3" \\
    "$REPO_ROOT/venv/bin/python3"  \\
    "$REPO_ROOT/env/bin/python3";  \\
do
    if [ -x "$candidate" ]; then PYTHON="$candidate"; break; fi
done

"$PYTHON" -m aprx_tools hook pre-commit || {{
    echo "aprx-tools: hook failed — is aprx-tools installed? (pip install aprx-tools)" >&2
    exit 1
}}
""".format(marker=MARKER)

_POST_STASH = """\
#!/usr/bin/env bash
# {marker}
set -euo pipefail

REPO_ROOT=$(git rev-parse --show-toplevel)

PYTHON=python3
for candidate in \\
    "$REPO_ROOT/.venv/bin/python3" \\
    "$REPO_ROOT/venv/bin/python3"  \\
    "$REPO_ROOT/env/bin/python3";  \\
do
    if [ -x "$candidate" ]; then PYTHON="$candidate"; break; fi
done

# post-stash failure should not block the stash operation
"$PYTHON" -m aprx_tools hook post-stash || true
""".format(marker=MARKER)

HOOKS = {
    "pre-commit": _PRE_COMMIT,
    "post-stash": _POST_STASH,
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
                    f'    python3 -m aprx_tools hook {name.replace("-", "_").split("_", 1)[-1]}'
                )
                continue

        hook_path.write_text(content)
        hook_path.chmod(hook_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        print(f"  aprx-tools: installed {name} hook")
