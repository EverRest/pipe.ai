"""sweep_worktrees: old dirs go, fresh stay, nothing outside the root, no branch delete."""

import os

from pipe.git_io import GitResult, sweep_worktrees

NOW = 1_000_000_000.0


class FakeGit:
    def __init__(self):
        self.calls = []

    def run(self, cwd, args):
        self.calls.append(list(args))
        return GitResult(0, "", "")


def _dir(root, name, age_h):
    p = root / name
    p.mkdir()
    t = NOW - age_h * 3600
    os.utime(p, (t, t))
    return p


def test_sweep(tmp_path):
    root = tmp_path / "wt"
    root.mkdir()
    old, fresh = _dir(root, "old", 30), _dir(root, "fresh", 1)
    outside = tmp_path / "outside"
    outside.mkdir()
    os.utime(outside, (0, 0))
    (root / "link").symlink_to(outside)
    g = FakeGit()
    sweep_worktrees(g, [str(tmp_path / "repo")], str(root), NOW)
    assert not old.exists() and fresh.exists() and outside.exists()
    flat = [" ".join(c) for c in g.calls]
    assert any(c.startswith("worktree remove --force") and str(old) in c for c in flat)
    assert not any(str(outside) in c or str(fresh) in c for c in flat)
    assert "worktree prune" in flat
    assert not any(c.startswith("branch") or " -D" in c for c in flat)
