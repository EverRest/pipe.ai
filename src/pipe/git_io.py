"""`git` wrapper for delegation (argv only, no shell). Not a core module."""

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlparse

from pipe.core.scrub import scrub

ENV_KEEP = ("PATH", "HOME", "USER", "LANG", "LC_ALL", "TMPDIR", "SSH_AUTH_SOCK")
MAX_TITLE_CHARS = 100
BRANCH_PREFIX = "pipe/"
REF_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
SAFE_CFG = ["-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false"]  # no repo code runs
LINK_RE = re.compile(r"https://[^\s]+/-/merge_requests/\d+")


class GitResult(NamedTuple):
    code: int
    out: str
    err: str


class GitError(Exception):
    """A git step failed. The text is a fixed reason, never raw git output."""


class Git:
    """GitPort over subprocess. Never prompts, passes no secret in env."""

    def __init__(self, timeout: float = 120):
        self.timeout = timeout

    def run(self, cwd: str | None, args) -> GitResult:
        env = {k: os.environ[k] for k in ENV_KEEP if k in os.environ}
        env["GIT_TERMINAL_PROMPT"] = "0"
        try:
            p = subprocess.run(  # noqa: S603
                ["git", *SAFE_CFG, *args],  # noqa: S607
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired:
            return GitResult(124, "", "timeout")
        return GitResult(p.returncode, p.stdout, scrub(p.stderr))


def check_push_ref(branch: str, base: str) -> None:
    """Refuse base, main, master, and any name outside `pipe/`."""
    bad = (
        not branch.startswith(BRANCH_PREFIX)
        or branch in (base, "main", "master")
        or not REF_RE.fullmatch(branch)
        or ".." in branch
    )
    if bad:
        raise GitError("push ref refused")


def worktree_add(git, repo: str, path: str, branch: str, base: str) -> None:
    if git.run(repo, ["worktree", "add", path, "-b", branch, f"origin/{base}"]).code:
        raise GitError("worktree failed")


def pin_worktree(wt: str) -> str:
    """Content of the `.git` file the adapter created (a `gitdir:` pointer)."""
    return (Path(wt) / ".git").read_text()


def check_worktree(wt: str, pin: str) -> None:
    """The child must not rewrite the worktree's `.git` file."""
    try:
        same = pin_worktree(wt) == pin
    except OSError:
        same = False
    if not same:
        raise GitError("worktree git metadata changed")


def worktree_remove(git, repo: str, path: str) -> None:
    git.run(repo, ["worktree", "remove", "--force", path])
    git.run(repo, ["worktree", "prune"])


def sweep_worktrees(git, repo_roots, worktree_root: str, now: float, max_age: float = 86400):
    """Remove worktree dirs older than `max_age` s. Stays in the root, keeps branches."""
    root = os.path.realpath(worktree_root)
    if not os.path.isdir(root):
        return
    for name in os.listdir(root):
        p = os.path.join(root, name)
        # a symlink or a path that resolves outside the root is never touched
        if os.path.islink(p) or os.path.commonpath([root, os.path.realpath(p)]) != root:
            continue
        if not os.path.isdir(p) or now - os.stat(p).st_mtime < max_age:
            continue
        for repo in repo_roots:
            git.run(repo, ["worktree", "remove", "--force", p])
        shutil.rmtree(p, ignore_errors=True)  # plain dir, or git could not remove it
    for repo in repo_roots:
        git.run(repo, ["worktree", "prune"])


def commit_all(git, wt: str, message: str) -> None:
    ident = ["-c", "user.name=pipe", "-c", "user.email=pipe@localhost"]
    if git.run(wt, ["add", "-A"]).code or git.run(wt, [*ident, "commit", "-m", message]).code:
        raise GitError("commit failed")


def _host(url: str) -> str | None:
    if "://" not in url:  # scp form: git@host:path
        url = "ssh://" + url.replace(":", "/", 1)
    return urlparse(url).hostname


def mr_link(output: str, remote_url: str) -> str | None:
    """First https MR link whose host equals the origin host."""
    for m in LINK_RE.finditer(output):
        if urlparse(m[0]).hostname == _host(remote_url.strip()):
            return m[0]
    return None


def push_branch(git, wt: str, branch: str, base: str, title: str) -> str | None:
    """Push one `pipe/` branch with MR options. Never base, never force."""
    check_push_ref(branch, base)
    url = git.run(wt, ["config", "--get", "remote.origin.url"]).out
    title = " ".join(title.split())[:MAX_TITLE_CHARS]
    ref = f"refs/heads/{branch}"
    lease = f"--force-with-lease={ref}:"  # empty expected value: create only, never move
    args = ["push", lease, "-o", "merge_request.create", "-o", f"merge_request.target={base}"]
    r = git.run(wt, [*args, "-o", f"merge_request.title={title}", "origin", f"{ref}:{ref}"])
    if r.code:
        raise GitError("push failed")
    return mr_link(r.out + "\n" + r.err, url)
