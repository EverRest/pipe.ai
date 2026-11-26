from pipe.runtime_claude_tools import ToolPolicy, effective_deny_rules, tools_for

PUSH = "Bash(git push:*)"
DEFAULT = ["Read", "Grep", "Glob"]


VARIANTS = [
    "Bash(git -C:*)", "Bash(git -c:*)", "Bash(env:*)",
    "Bash(sh:*)", "Bash(bash:*)", "Bash(zsh:*)",
]  # fmt: skip


def test_deny_default_and_none():
    assert effective_deny_rules([]) == [PUSH, *VARIANTS]
    assert effective_deny_rules(None) == [PUSH, *VARIANTS]


def test_deny_has_each_variant():
    out = effective_deny_rules(["Bash(rm:*)"])
    assert all(v in out for v in [PUSH, *VARIANTS])


def test_deny_adds_and_dedupes():
    assert effective_deny_rules(["Bash(rm:*)"]) == [PUSH, *VARIANTS, "Bash(rm:*)"]
    out = effective_deny_rules([PUSH, "Bash(env:*)", "Bash(rm:*)"])
    assert out == [PUSH, *VARIANTS, "Bash(rm:*)"]


def test_deny_does_not_mutate():
    src = ["Bash(rm:*)"]
    out = effective_deny_rules(src)
    assert src == ["Bash(rm:*)"] and out is not src


def test_owner_policy():
    p = tools_for(True, DEFAULT, [])
    deny = effective_deny_rules([])
    assert p == ToolPolicy(tools=DEFAULT, allowed=DEFAULT, disallowed=deny, restricted=True)


def test_owner_scoped_bash_keeps_push_deny():
    p = tools_for(True, ["Read", "Bash(pytest:*)"], ["Bash(rm:*)"])
    assert p.tools == ["Read", "Bash(pytest:*)"]
    assert p.disallowed == [PUSH, *VARIANTS, "Bash(rm:*)"]


def test_non_owner_has_no_tools():
    p = tools_for(False, DEFAULT, ["Bash(rm:*)"])
    assert p == ToolPolicy(tools=[], allowed=[], disallowed=[], restricted=True)
