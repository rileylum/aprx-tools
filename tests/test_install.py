import stat
import subprocess
from pathlib import Path

import pytest

from aprx_tools.install import install_hooks, MARKER, _find_git_root


@pytest.fixture
def git_repo(tmp_path):
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    return tmp_path


ALL_HOOKS = ("pre-commit", "pre-push", "post-stash", "post-merge", "post-checkout")


def test_hooks_are_written(git_repo):
    install_hooks(git_repo)
    for name in ALL_HOOKS:
        assert (git_repo / ".git" / "hooks" / name).exists()


def test_hooks_are_executable(git_repo):
    install_hooks(git_repo)
    for name in ALL_HOOKS:
        hook = git_repo / ".git" / "hooks" / name
        assert hook.stat().st_mode & stat.S_IXUSR


def test_hooks_contain_marker(git_repo):
    install_hooks(git_repo)
    for name in ALL_HOOKS:
        hook = git_repo / ".git" / "hooks" / name
        assert MARKER in hook.read_text()


def test_pre_push_runs_verify_without_install_hint(git_repo):
    # pre-push must let `aprx verify` speak for itself, not mask a real failure
    # with the generic "is aprx-tools installed?" message.
    install_hooks(git_repo)
    text = (git_repo / ".git" / "hooks" / "pre-push").read_text()
    assert "hook pre-push" in text
    assert "is aprx-tools installed" not in text


def test_install_is_idempotent(git_repo):
    install_hooks(git_repo)
    install_hooks(git_repo)
    for name in ALL_HOOKS:
        assert MARKER in (git_repo / ".git" / "hooks" / name).read_text()


def test_does_not_overwrite_foreign_hook(git_repo, capsys):
    foreign = "#!/usr/bin/env bash\necho 'foreign'\n"
    hook_path = git_repo / ".git" / "hooks" / "pre-commit"
    hook_path.write_text(foreign)
    install_hooks(git_repo)
    assert hook_path.read_text() == foreign
    assert "pre-commit" in capsys.readouterr().out


def test_fails_outside_git_repo(tmp_path):
    with pytest.raises(SystemExit):
        _find_git_root(tmp_path)
