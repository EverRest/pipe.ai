"""One `write` step: worktree, claude child, commit, push branch, MR link."""

import os
import subprocess
import uuid
from collections.abc import Callable, Sequence
from pathlib import Path
from types import SimpleNamespace

from pipe.core.contract import RuntimeFailed, RuntimeInput, RuntimeOutput, parse_output
from pipe.core.scrub import scrub as _scrub
from pipe.git_io import (
    BRANCH_PREFIX,
    GitError,
    check_push_ref,  # noqa: F401 (re-export: the push guard lives with git)
    check_worktree,
    commit_all,
    pin_worktree,
    push_branch,
    worktree_add,
    worktree_remove,
)
from pipe.runtime_claude_discovery import read_mcp_entries
from pipe.runtime_claude_load import cleanup
from pipe.runtime_claude_load import prepare as _prepare
from pipe.runtime_claude_request import map_request
from pipe.state import pipe_home


def pick_target(delegate_repos: dict, target: str | None) -> tuple[str | None, str | None]:
    """DQ3. Returns (path, None) or (None, reason). Exact, case-sensitive match."""
    if not delegate_repos:
        return None, "repo not available"
    if target:
        path = delegate_repos.get(target)
        return (path, None) if path else (None, "unknown_target")
    if len(delegate_repos) == 1:
        return next(iter(delegate_repos.values())), None
    return None, "target_required"


def branch_name(task_id: str, step: int) -> str:
    return f"{BRANCH_PREFIX}{task_id.replace('.', '-')}-s{step}"


def pick_branch(name: str, existing: Sequence[str]) -> str:
    n, cand = 2, name
    while cand in existing:
        cand, n = f"{name}-{n}", n + 1
    return cand


def resolve_repo(path: str, repo_roots: Sequence[str]) -> str | None:
    """Realpath when inside a root and a git repo, else None."""
    real = os.path.realpath(os.path.expanduser(path))
    for r in repo_roots:
        root = os.path.realpath(os.path.expanduser(r))
        if real.startswith(root + os.sep) and os.path.exists(os.path.join(real, ".git")):
            return real
    return None


def commit_message(goal: str) -> str:
    first = (_scrub(goal).splitlines() or [""])[0]
    return f"pipe: {first}"[:72]


def _existing(git, repo: str) -> list[str]:
    r = git.run(repo, ["for-each-ref", "--format=%(refname:short)", "refs/heads/pipe/"])
    ls = git.run(repo, ["ls-remote", "--heads", "origin", "refs/heads/pipe/*"])
    if ls.code:
        raise RuntimeFailed("branch lookup failed")
    remote = [x.removeprefix("refs/heads/") for x in ls.out.split()[1::2]]
    return r.out.split() + remote


def run_write(
    inp: RuntimeInput,
    cfg,
    git,
    runner: Callable,
    caps: list,
    scrub: Callable[[str], str] = _scrub,
    esc: Callable[[str], str] = lambda s: s,
    prepare: Callable = _prepare,
    home: Path | None = None,
) -> RuntimeOutput:
    """Raises RuntimeFailed(<fixed reason>). The worktree is always removed."""
    from pipe.runtime_claude import _child_env, _payload, build_cmd, build_prompt  # no import cycle

    req = inp.request
    path, reason = pick_target(getattr(cfg, "delegate_repos", None) or {}, req.target)
    repo = None if reason else resolve_repo(path, cfg.repo_roots)
    if reason or not repo:
        raise RuntimeFailed(reason or "repo not available")
    base = getattr(cfg, "base_branch", "main")
    root = Path(getattr(cfg, "worktree_root", "~/.pipe/worktrees")).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex
    wt = str(root.resolve() / run_id)
    st = map_request(req, cfg, caps, workdir=wt)
    if st.load.skipped:
        raise RuntimeFailed("capability not available")
    if git.run(repo, ["fetch", "origin", base]).code:
        raise RuntimeFailed("base not available")
    task = inp.task
    branch = pick_branch(branch_name(task["id"], task.get("step", 0)), _existing(git, repo))
    goal = (task.get("pipeline") or {}).get("goal", "")
    run_dir = pipe_home() / "run" / run_id
    try:
        worktree_add(git, repo, wt, branch, base)
        pin = pin_worktree(wt)
        ls = st.load
        prepared = None
        if ls.skills or ls.commands or ls.mcp:
            prepared = prepare(ls, run_dir, read_mcp_entries(home or Path.home()))
        # the worktree is the only root: add-dir and path rules come from it
        wcfg = SimpleNamespace(**{**vars(cfg), "repo_roots": [wt]})
        cmd = build_cmd(wcfg, st.policy, prepared) + ["--add-dir", wt]
        try:
            code, out = runner(
                cmd, build_prompt(inp.thread, task), _child_env(), wt, cfg.step_timeout_min * 60
            )
        except subprocess.TimeoutExpired as e:
            raise RuntimeFailed("timeout") from e
        except FileNotFoundError as e:
            raise RuntimeFailed("command not found") from e
        if code != 0:
            raise RuntimeFailed(f"exit {code}")
        o = parse_output(_payload(out))
        if o.status != "done":
            raise RuntimeFailed("delegate run failed")
        check_worktree(wt, pin)
        if not git.run(wt, ["status", "--porcelain"]).out.strip():
            raise RuntimeFailed("no changes")
        if git.run(wt, ["rev-parse", "--abbrev-ref", "HEAD"]).out.strip() != branch:
            raise RuntimeFailed("branch changed")
        commit_all(git, wt, commit_message(goal))
        link = push_branch(git, wt, branch, base, scrub(goal.splitlines()[0] if goal else "pipe"))
        if not link:
            raise RuntimeFailed("no merge request")
        return RuntimeOutput(text=esc(scrub(o.text)), status="done", artifacts=[scrub(link)])
    except GitError as e:
        raise RuntimeFailed(str(e)) from e
    finally:
        cleanup(run_dir)
        worktree_remove(git, repo, wt)
