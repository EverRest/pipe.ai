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


def _old(tmp_path, record):
    root = tmp_path / "wt"
    root.mkdir(parents=True)
    old = _dir(root, "old", 30)
    if record is not None:
        (root / "old.repo").write_text(str(record))
    return root, old


def test_sweep_recorded_repo_not_in_config(tmp_path):
    repo = tmp_path / "gone"
    repo.mkdir()
    root, old = _old(tmp_path, repo)

    class G(FakeGit):
        def run(self, cwd, args):
            self.calls.append([cwd, *args])
            return GitResult(0, "", "")

    g = G()
    sweep_worktrees(g, [], str(root), NOW)
    assert not old.exists() and not (root / "old.repo").exists()
    assert [str(repo), "worktree", "remove", "--force", str(old)] in g.calls
    assert [str(repo), "worktree", "prune"] in g.calls
    assert not any("branch" in c or "-D" in c for c in g.calls)


def test_sweep_missing_or_bogus_record(tmp_path):
    for rec in (None, tmp_path / "nope", "relative"):
        root, old = _old(tmp_path / str(rec).replace("/", "_"), rec)
        g = FakeGit()
        sweep_worktrees(g, [], str(root), NOW)
        assert not old.exists() and g.calls == []
