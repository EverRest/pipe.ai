import pytest

from pipe.git_io import (
    Git,
    GitError,
    GitResult,
    check_push_ref,
    check_worktree,
    commit_all,
    mr_link,
    pin_worktree,
    push_branch,
    worktree_add,
)

U = "https://gitlab.example.com/g/p.git"
L = "https://gitlab.example.com/g/p/-/merge_requests/1"
EVIL = L.replace("gitlab", "evil")
HTTP = L.replace("https", "http")


class Fake:
    def __init__(self, url=U, push=None):
        self.calls, self.url, self.push = [], url, push or GitResult(0, "", "")

    def run(self, cwd, args):
        self.calls.append((cwd, list(args)))
        if args[0] == "config":
            return GitResult(0, self.url + "\n", "")
        if args[0] == "push":
            return self.push
        return GitResult(0, "", "")


@pytest.mark.parametrize(
    "ref",
    [
        "main",
        "master",
        "dev",
        "origin/main",
        "",
        "feat/x",
        "pipe/a b",
        "pipe/a..b",
        "pipe/a;b",
        "pipe/$x",
        "pipe/a\nb",
    ],
)
def test_check_push_ref_refuses(ref):
    with pytest.raises(GitError):
        check_push_ref(ref, "dev")


def test_check_push_ref_ok():
    check_push_ref("pipe/1700-000100-s1", "main")


def test_push_args_and_link():
    out = "remote:   https://gitlab.example.com/g/p/-/merge_requests/12\n"
    g = Fake(push=GitResult(0, "", out))
    assert push_branch(g, "/wt", "pipe/b", "main", "t; $(x)\n'q'") == (
        "https://gitlab.example.com/g/p/-/merge_requests/12"
    )
    cwd, args = g.calls[-1]
    assert cwd == "/wt"
    assert args[:6] == [
        "push", "--force-with-lease=refs/heads/pipe/b:",
        "-o", "merge_request.create", "-o", "merge_request.target=main",
    ]  # fmt: skip
    assert args[-2:] == ["origin", "refs/heads/pipe/b:refs/heads/pipe/b"]
    assert "--force" not in args and "-f" not in args and all(a != "main" for a in args[-2:])
    assert "--force-with-lease=refs/heads/pipe/b:" in args
    assert len(args) == 10 and args[7].startswith("merge_request.title=")


def test_push_main_makes_no_call():
    g = Fake()
    with pytest.raises(GitError):
        push_branch(g, "/wt", "main", "main", "t")
    assert g.calls == []


def test_push_failure_and_no_link():
    with pytest.raises(GitError, match="push failed"):
        push_branch(Fake(push=GitResult(1, "", "boom")), "/wt", "pipe/b", "main", "t")
    assert push_branch(Fake(), "/wt", "pipe/b", "main", "t") is None


@pytest.mark.parametrize(
    "url,link,ok",
    [
        (U, L, 1),
        ("git@gitlab.example.com:g/p.git", L, 1),
        ("ssh://git@gitlab.example.com/g/p.git", L, 1),
        (U, EVIL, 0),
        (U, HTTP, 0),
    ],
)
def test_mr_link_host_rule(url, link, ok):
    assert mr_link(f"remote: {link}\n", url) == (link if ok else None)


def test_error_text_scrubbed():
    class R:
        def run(self, cwd, args):
            return GitResult(1, "", "x")

    with pytest.raises(GitError) as e:
        worktree_add(R(), "/r", "/wt", "pipe/b", "main")
    assert str(e.value) == "worktree failed"
    with pytest.raises(GitError) as e:
        commit_all(R(), "/wt", "m")
    assert str(e.value) == "commit failed"


def test_git_run_real(tmp_path):
    r = Git().run(str(tmp_path), ["--version"])
    assert r.code == 0 and r.out.startswith("git version")
    assert Git().run(str(tmp_path), ["rev-parse", "HEAD"]).code != 0


def test_git_run_adds_safe_config_to_every_call(monkeypatch):
    seen = []

    def fake(argv, **kw):
        seen.append(argv)
        return type("P", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr("pipe.git_io.subprocess.run", fake)
    Git().run("/wt", ["status", "--porcelain"])
    Git().run("/wt", ["push", "origin"])
    for argv in seen:
        assert argv[:6] == [
            "git", "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false", argv[5],
        ]  # fmt: skip
        assert argv[5] in ("status", "push")


def test_check_worktree_detects_rewritten_git_file(tmp_path):
    (tmp_path / ".git").write_text("gitdir: /repo/.git/worktrees/a\n")
    pin = pin_worktree(str(tmp_path))
    check_worktree(str(tmp_path), pin)
    (tmp_path / ".git").write_text("gitdir: /evil\n")
    with pytest.raises(GitError, match="worktree git metadata changed"):
        check_worktree(str(tmp_path), pin)


@pytest.mark.parametrize(
    "out",
    [
        "remote: https://user:tok@git.example.com/a/-/merge_requests/1",  # userinfo
        "remote: https://git.example.com:8443/a/-/merge_requests/1",  # port
        "remote: http://git.example.com/a/-/merge_requests/1",  # not https
        "remote: https://git.example.com.evil.org/a/-/merge_requests/1",  # lookalike host
    ],
)
def test_mr_link_refuses_userinfo_port_scheme_and_lookalike(out):
    from pipe import git_io

    assert git_io.mr_link(out, "https://git.example.com") is None


def test_mr_link_non_string_is_none():
    from pipe import git_io

    assert git_io.mr_link(None, "https://git.example.com") is None
    assert git_io.mr_link("x", None) is None


def test_mr_link_keeps_a_clean_link():
    from pipe import git_io

    out = "remote: https://git.example.com/a/-/merge_requests/9"
    assert git_io.mr_link(out, "https://git.example.com") == out.split()[-1]
