import json
import subprocess
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from pipe.core.contract import RuntimeFailed, RuntimeInput
from pipe.git_io import Git
from pipe.runtime_claude_delegate import run_write

LINK = "https://gitlab.example.com/g/p/-/merge_requests/7"


def sh(cwd, *a):
    return subprocess.run(  # noqa: S603
        ["git", *a],  # noqa: S607
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


@pytest.fixture
def env(tmp_path):
    bare, roots = tmp_path / "origin.git", tmp_path / "roots"
    sh(tmp_path, "init", "--bare", "-b", "main", str(bare))
    sh(bare, "config", "receive.advertisePushOptions", "true")
    hook = bare / "hooks" / "pre-receive"
    opts = tmp_path / "opts.txt"
    hook.write_text(
        f"#!/bin/sh\nn=0\nwhile [ $n -lt $GIT_PUSH_OPTION_COUNT ]; do\n"
        f"  eval echo \\$GIT_PUSH_OPTION_$n >> {opts}; n=$((n+1))\ndone\n"
        f"echo {LINK} >&2\n"
    )
    hook.chmod(0o755)
    clone = roots / "app"
    roots.mkdir()
    fake = "https://gitlab.example.com/g/p.git"
    sh(tmp_path, "clone", str(bare), str(clone))
    sh(clone, "config", "user.email", "t@e")
    sh(clone, "config", "user.name", "t")
    (clone / "a.txt").write_text("a")
    sh(clone, "add", "-A")
    sh(clone, "commit", "-m", "init")
    sh(clone, "push", "origin", "HEAD:main")
    sh(clone, "remote", "set-url", "origin", fake)
    sh(clone, "config", f"url.{bare}.insteadOf", fake)
    cfg = NS(
        repo_roots=[str(roots)],
        delegate_repos={"app": str(clone)},
        worktree_root=str(tmp_path / "wts"),
        base_branch="main",
        model=None,
        max_budget_usd=None,
        step_timeout_min=1,
        owner_tools=["Read"],
        deny_rules=[],
        exposed=[],
    )
    return NS(bare=bare, clone=clone, cfg=cfg, opts=opts, wts=tmp_path / "wts")


def inp():
    req = NS(capabilities=(), capability_ids=(), access="write", requester_is_owner=False)
    req.target = None
    task = {"id": "1700.0001", "purpose": "step", "step": 1, "pipeline": {"goal": "add b"}}
    return RuntimeInput([{"user": "U1", "text": "x"}], task, False, req)


def runner(seen, write=True):
    def r(argv, stdin, e, cwd, timeout):
        seen.append((argv, cwd))
        if write:
            (Path(cwd) / "b.txt").write_text("b")
        return 0, json.dumps({"structured_output": {"text": "done", "status": "done"}})

    return r


def test_write_run_pushes_branch_only(env):
    main0 = sh(env.bare, "rev-parse", "main")
    seen = []
    out = run_write(inp(), env.cfg, Git(), runner(seen), [])
    assert out.artifacts == [LINK] and out.status == "done"
    assert sh(env.bare, "rev-parse", "main") == main0
    assert sh(env.clone, "rev-parse", "main") == main0
    assert sh(env.bare, "branch", "--list", "pipe/*").split() == ["pipe/1700-0001-s1"]
    assert sh(env.bare, "rev-list", "--count", "main..pipe/1700-0001-s1").strip() == "1"
    assert sh(env.clone, "worktree", "list").count("\n") == 1
    assert not list(env.wts.iterdir())
    opts = env.opts.read_text()
    assert "merge_request.create" in opts and "merge_request.target=main" in opts
    argv, cwd = seen[0]
    assert cwd.startswith(str(env.wts.resolve())) and argv[argv.index("--add-dir") + 1] == cwd
    assert "Bash(git push:*)" in argv

    # Retry: new branch with a suffix, the first stays.
    run_write(inp(), env.cfg, Git(), runner([]), [])
    assert sh(env.bare, "branch", "--list", "pipe/*").split() == [
        "pipe/1700-0001-s1",
        "pipe/1700-0001-s1-2",
    ]
    assert sh(env.bare, "rev-parse", "main") == main0


def test_no_changes_leaves_nothing(env):
    with pytest.raises(RuntimeFailed, match="no changes"):
        run_write(inp(), env.cfg, Git(), runner([], write=False), [])
    assert sh(env.bare, "branch", "--list", "pipe/*") == ""
    assert not list(env.wts.iterdir())
    assert sh(env.clone, "worktree", "list").count("\n") == 1
