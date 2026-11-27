import pytest

from pipe.runtime_claude_delegate import pick_target

ONE = {"app": "/r/app"}
TWO = {"app": "/r/app", "lib": "/r/lib"}


@pytest.mark.parametrize(
    "repos,target,want",
    [
        (TWO, "web", (None, "unknown_target")),
        (TWO, "App", (None, "unknown_target")),
        (TWO, "app ", (None, "unknown_target")),
        (TWO, None, (None, "target_required")),
        (TWO, "", (None, "target_required")),
        (ONE, None, ("/r/app", None)),
        (ONE, "app", ("/r/app", None)),
        (ONE, "lib", (None, "unknown_target")),
        (TWO, "lib", ("/r/lib", None)),
        ({}, None, (None, "repo not available")),
        ({}, "app", (None, "repo not available")),
    ],
)
def test_pick_target(repos, target, want):
    before = dict(repos)
    assert pick_target(repos, target) == want
    assert repos == before
