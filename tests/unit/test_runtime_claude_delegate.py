import json
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from pipe.core.contract import RuntimeFailed, RuntimeInput
from pipe.git_io import GitResult
from pipe.runtime_claude_delegate import (
    branch_name,
    commit_message,
    pick_branch,
    resolve_repo,
    run_write,
)

TOKEN = "glpat-abcdefghijklmnop"  # noqa: S105
MR = "https://gitlab.example.com/g/p/-/merge_requests/3"


def test_branch_name_and_pick():
    assert branch_name("1700000000.000100", 1) == "pipe/1700000000-000100-s1"
    assert pick_branch("a", []) == "a"
    assert pick_branch("a", ["a"]) == "a-2"
    assert pick_branch("a", ["a", "a-2"]) == "a-3"


def test_commit_message():
    m = commit_message("fix it\nsecond line")
    assert m == "pipe: fix it"
    assert len(commit_message("x" * 200)) == 72
    assert "glpat-abcdefghijklmnop" not in commit_message("glpat-abcdefghijklmnop")


def test_resolve_repo(tmp_path):
    roots = tmp_path / "roots"
    ok, nogit = roots / "ok", roots / "nogit"
    (ok / ".git").mkdir(parents=True)
    nogit.mkdir()
    out = tmp_path / "out"
    (out / ".git").mkdir(parents=True)
    (roots / "link").symlink_to(out)
    r = [str(roots)]
    assert resolve_repo(str(ok), r) == str(ok.resolve())
    assert resolve_repo(str(nogit), r) is None
    assert resolve_repo(str(out), r) is None
    assert resolve_repo(str(roots / "link"), r) is None


class FakeGit:
    def __init__(self, status=" M f", push=None):
        self.calls, self.status, self.push = [], status, push or GitResult(0, "", "")
        self.remote = ""

    def run(self, cwd, args):
        self.calls.append(list(args))
        a = args[0]
        if a == "status":
            return GitResult(0, self.status, "")
        if a == "rev-parse":
            return GitResult(0, self.branch + "\n", "")
        if a == "push":
            return self.push
        if a == "config":
            return GitResult(0, "https://gitlab.example.com/g/p.git", "")
        if a == "ls-remote":
            return GitResult(0, self.remote, "")
        if a == "worktree" and args[1] == "add":
            self.branch = args[args.index("-b") + 1]
            Path(args[2]).mkdir(parents=True)
            Path(args[2], ".git").write_text("gitdir: /repo/.git/worktrees/x\n")
        return GitResult(0, "", "")

    def names(self):
        return [" ".join(c[:2]) for c in self.calls]


def setup(tmp_path, **kw):
    repo = tmp_path / "roots" / "app"
    (repo / ".git").mkdir(parents=True)
    cfg = NS(
        repo_roots=[str(tmp_path / "roots")],
        delegate_repos={"app": str(repo)},
        worktree_root=str(tmp_path / "wts"),
        base_branch="main",
        model=None,
        max_budget_usd=None,
        step_timeout_min=1,
        owner_tools=["Read"],
        deny_rules=[],
        exposed=[],
        **kw,
    )
    inp = RuntimeInput(
        [{"user": "U1", "text": "do"}],
        {"id": "1.2", "purpose": "step", "step": 1, "pipeline": {"goal": "add file"}},
        False,
        NS(capabilities=(), capability_ids=(), access="write", target=None),
    )
    return cfg, inp


def ok_runner(seen, status="done", rewrite=False):
    def r(argv, stdin, env, cwd, timeout):
        seen.append((argv, env, cwd))
        if rewrite:
            Path(cwd, ".git").write_text("gitdir: /evil\n")
        return 0, json.dumps(
            {"structured_output": {"text": "hi <!channel> " + TOKEN, "status": status}}
        )

    return r


def run(cfg, inp, git, runner, **kw):
    return run_write(
        inp,
        cfg,
        git,
        runner,
        [],
        scrub=lambda s: s.replace(TOKEN, "[redacted]"),
        esc=lambda s: s.replace("<!channel>", "@channel"),
        **kw,
    )


def test_happy_path(tmp_path):
    cfg, inp = setup(tmp_path)
    g, seen = FakeGit(push=GitResult(0, "", "remote: " + MR)), []
    out = run(cfg, inp, g, ok_runner(seen))
    assert out.status == "done" and out.artifacts == [MR]
    assert "glpat" not in out.text and "<!channel>" not in out.text
    argv, env, cwd = seen[0]
    assert cwd in argv and argv.index("--add-dir") >= 0 and argv.count("--add-dir") == 1
    assert "--restricted" in argv and "Bash(git push:*)" in argv
    assert set(env) <= {"PATH", "HOME", "USER", "LANG", "LC_ALL", "TMPDIR", "PIPE_RUNTIME"}
    assert g.names()[-2:] == ["worktree remove", "worktree prune"]
    pushed = next(c for c in g.calls if c[0] == "push")
    assert pushed[-1].startswith("refs/heads/pipe/")


@pytest.mark.parametrize(
    "mutate,reason",
    [
        (lambda c, i: c.delegate_repos.clear(), "repo not available"),
        (lambda c, i: setattr(i.request, "target", "zzz"), "unknown_target"),
        (lambda c, i: c.delegate_repos.update(lib="/x"), "target_required"),
    ],
)
def test_refused_before_git(tmp_path, mutate, reason):
    cfg, inp = setup(tmp_path)
    mutate(cfg, inp)
    g = FakeGit()
    with pytest.raises(RuntimeFailed, match=reason):
        run(cfg, inp, g, ok_runner([]))
    assert g.calls == []


def test_no_changes_cleans_up(tmp_path):
    cfg, inp = setup(tmp_path)
    g = FakeGit(status="")
    with pytest.raises(RuntimeFailed, match="no changes"):
        run(cfg, inp, g, ok_runner([]))
    assert "push" not in [c[0] for c in g.calls]
    assert g.names()[-2:] == ["worktree remove", "worktree prune"]


def test_push_failed_and_no_mr(tmp_path):
    cfg, inp = setup(tmp_path)
    g = FakeGit(push=GitResult(1, "", "denied glpat-abcdefghijklmnop"))
    with pytest.raises(RuntimeFailed) as e:
        run(cfg, inp, g, ok_runner([]))
    assert str(e.value) == "push failed" and g.names()[-1] == "worktree prune"
    with pytest.raises(RuntimeFailed, match="no merge request"):
        run(cfg, inp, FakeGit(), ok_runner([]))


def test_child_timeout_cleans_up(tmp_path):
    import subprocess

    def boom(*a):
        raise subprocess.TimeoutExpired("claude", 1)

    cfg, inp = setup(tmp_path)
    g = FakeGit()
    with pytest.raises(RuntimeFailed, match="timeout"):
        run(cfg, inp, g, boom)
    assert g.names()[-1] == "worktree prune"


def test_failed_child_is_not_committed(tmp_path):
    cfg, inp = setup(tmp_path)
    g = FakeGit()
    with pytest.raises(RuntimeFailed) as e:
        run(cfg, inp, g, ok_runner([], status="failed"))
    assert str(e.value) == "delegate run failed"
    assert not {"commit", "push"} & {c[0] for c in g.calls}


def test_rewritten_git_file_stops_before_git(tmp_path):
    cfg, inp = setup(tmp_path)
    g = FakeGit()
    with pytest.raises(RuntimeFailed) as e:
        run(cfg, inp, g, ok_runner([], rewrite=True))
    assert str(e.value) == "worktree git metadata changed"
    assert not {"status", "add", "commit", "push"} & {c[0] for c in g.calls}


def test_remote_branch_name_is_skipped(tmp_path):
    cfg, inp = setup(tmp_path)
    g = FakeGit(push=GitResult(0, "", "remote: " + MR))
    g.remote = "abc\trefs/heads/pipe/1-2-s1\n"
    run(cfg, inp, g, ok_runner([]))
    push = next(c for c in g.calls if c[0] == "push")
    assert push[-1] == "refs/heads/pipe/1-2-s1-2:refs/heads/pipe/1-2-s1-2"
    assert "--force-with-lease=refs/heads/pipe/1-2-s1-2:" in push
