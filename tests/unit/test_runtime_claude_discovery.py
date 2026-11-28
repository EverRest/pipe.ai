import json

from pipe.runtime_claude_discovery import discover, read_mcp_entries

FAKE_URL = "https://secret.example/x?token=abc123"


def w(p, text):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def skill(d, name, extra="", body="hello"):
    w(d / name / "SKILL.md", f"---\nname: {name}\ndescription: d {name}\n{extra}---\n{body}\n")


def tree(home, repos):
    c = home / ".claude"
    plug = home / "plugstore" / "pa"
    off = home / "plugstore" / "off"
    plug2 = home / "plugstore2" / "pa"
    inst = {"version": 2, "plugins": {}}
    for k, p in (("pa@m1", plug), ("pa@m2", plug2), ("off@m1", off)):
        inst["plugins"][k] = [{"installPath": str(p)}]
        w(p / ".claude-plugin" / "plugin.json", json.dumps({"name": k.split("@")[0]}))
    w(c / "plugins" / "installed_plugins.json", json.dumps(inst))
    w(
        c / "settings.json",
        json.dumps(
            {
                "enabledPlugins": {"pa@m1": True, "pa@m2": True, "off@m1": False},
                "env": {"X": FAKE_URL},
            }
        ),
    )
    skill(plug / "skills", "shared", "tags: [review]\n")
    skill(plug2 / "skills", "shared")
    skill(off / "skills", "hidden")
    w(plug / "commands" / "cmd.md", "---\ndescription: c\ntags: [ops]\n---\nbody")
    w(plug / ".mcp.json", json.dumps({"mcpServers": {"pm": {"url": FAKE_URL}}}))
    skill(c / "skills", "mine")
    (home / "elsewhere").mkdir()
    skill(home / "elsewhere", "linked")
    (c / "skills" / "linked").symlink_to(home / "elsewhere" / "linked")
    skill(c / "skills", "synced")
    w(c / "skills" / "bad" / "SKILL.md", "---\na: [x\n---\n")
    w(c / "commands" / "mycmd.md", "body only")
    w(
        home / ".claude.json",
        json.dumps({"mcpServers": {"gl": {"url": FAKE_URL, "headers": {"A": "s3"}}}}),
    )
    (repos / "pipe.ai" / ".git").mkdir(parents=True)
    (repos / "notrepo").mkdir()


def run(tmp_path):
    home, repos = tmp_path / "h", tmp_path / "repos"
    home.mkdir()
    repos.mkdir()
    tree(home, repos)
    return home, repos


def test_discover(tmp_path):
    home, repos = run(tmp_path)
    caps, notices = discover(home, [str(repos)])
    ids = {c.id for c in caps}
    assert {
        "skill:mine", "skill:linked", "command:mycmd", "mcp:gl", "repo:pipe.ai",
        "command:pa:cmd", "mcp:pa:pm",
    } <= ids  # fmt: skip
    assert not any("hidden" in i or "off" in i or "synced" in i or "notrepo" in i for i in ids)
    shared = [i for i in ids if i.startswith("skill:pa:shared")]
    assert len(shared) == 2 and all("#" in i for i in shared)
    assert [(n.kind, n.id) for n in notices] == [("skipped", "skill:bad")]
    assert str(home) not in notices[0].text
    by = {c.id: c for c in caps}
    assert by["command:pa:cmd"].declared_tags == ("ops",)
    assert by["skill:mine"].declared_tags == ()
    assert any(c.declared_tags == ("review",) for c in caps)
    assert by["skill:mine"].plugin_id is None
    plugs = {i for i in ids if i.startswith("plugin:pa#")}
    assert len(plugs) == 2 and by["command:pa:cmd"].plugin_id in plugs
    blob = repr([c for c in caps])
    assert "secret.example" not in blob and "s3" not in blob.replace("skill", "")


def test_stable_and_new_skill(tmp_path):
    home, repos = run(tmp_path)
    first = {c.id for c in discover(home, [str(repos)])[0]}
    skill(home / ".claude" / "skills", "fresh")
    second = {c.id for c in discover(home, [str(repos)])[0]}
    assert second - first == {"skill:fresh"} and first <= second


def test_read_mcp_entries(tmp_path):
    home, _ = run(tmp_path)
    e = read_mcp_entries(home)
    assert e["gl"]["url"] == FAKE_URL and e["pm"]["url"] == FAKE_URL
    assert read_mcp_entries(tmp_path / "none") == {}


def test_same_mcp_name_in_two_scopes_is_kept(tmp_path):
    home, repos = run(tmp_path)
    j = home / ".claude.json"
    d = json.loads(j.read_text())
    d["mcpServers"]["pm"] = {"url": FAKE_URL}  # same name as the plugin server
    j.write_text(json.dumps(d))
    caps = [c for c in discover(home, [str(repos)])[0] if c.type == "mcp" and c.name == "pm"]
    assert {c.plugin for c in caps} == {None, "pa"} and len({c.source for c in caps}) == 2


def test_marketplace_from_plugin_key(tmp_path):
    home, repos = run(tmp_path)
    caps = discover(home, [str(repos)])[0]
    by = {c.id: c.marketplace for c in caps if c.plugin == "pa" and c.type != "mcp"}
    assert set(by.values()) == {"m1", "m2"} or {"m1", "m2"} <= set(by.values())
    assert next(c for c in caps if c.id == "skill:mine").marketplace is None
    assert next(c for c in caps if c.id == "mcp:pa:pm").marketplace == "m1"
