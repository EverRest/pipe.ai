import pytest

from fakes import FakeKeychain, FakeTransport
from pipe.core.contract import UploadRefused
from pipe.ports import Transport  # noqa: F401


def test_thread_latest_reply_and_reconnect():
    t = FakeTransport()
    p = t.add_message("C1", "hi")
    seen = []
    t.on_reconnect(lambda: seen.append(1))
    t.link_down = True
    t.add_message("C1", "late", thread=p.ts)
    assert t.replies("C1", p.ts) == [p]
    t.reconnect()
    assert seen == [1] and len(t.replies("C1", p.ts)) == 2
    assert t.history("C1")[0].latest_reply is not None


def test_upload_records_no_content_and_keychain():
    t = FakeTransport()
    assert t.upload_file("C1", "1.0", "a.png", b"secret", "a").startswith("https://")
    assert "secret" not in str(t.uploads)
    assert FakeKeychain()("svc", "bot") == "xoxb-fake"


def test_history_oldest_first_limit_keeps_newest():
    t = FakeTransport()
    ms = [t.add_message("C1", str(i)) for i in range(5)]
    assert t.history("C1") == ms
    assert t.history("C1", limit=2) == ms[-2:]


def test_upload_refusals(tmp_path, pipe_home):
    run = pipe_home / "run"
    run.mkdir()
    ok = run / "a.txt"
    ok.write_bytes(b"12345")
    outside = tmp_path / "out.txt"
    outside.write_text("x")
    link = run / "link.txt"
    link.symlink_to(ok)
    big = run / "big.bin"
    big.write_bytes(b"0" * (10 * 1024 * 1024 + 1))
    t = FakeTransport()
    for bad in (outside, link, run, big):
        with pytest.raises(UploadRefused):
            t.upload_file("C1", "1.0", "n", bad, "t")
    with pytest.raises(UploadRefused):
        t.upload_file("C1", "1.0", "n", b"0" * (10 * 1024 * 1024 + 1), "t")
    assert t.uploads == []
    t.upload_file("C1", "1.0", "n", ok, "t")
    assert t.uploads[0]["size"] == 5


def test_fail_hooks_and_unpin():
    t = FakeTransport()
    ts = t.post_message("C1", "x")
    t.pin("C1", ts)
    t.unpin("C1", ts)
    assert t.list_pins("C1") == []
    t.fail_update = "message_not_found"
    with pytest.raises(RuntimeError, match="message_not_found"):
        t.update_message("C1", ts, "y")
    t.fail_dm = RuntimeError("boom")
    with pytest.raises(RuntimeError):
        t.send_dm("U1", "hi")
    assert t.dms == []


def test_build_claude_tree(tmp_path):
    from fakes import build_claude_tree
    from pipe.runtime_claude_discovery import discover

    home, roots = build_claude_tree(tmp_path)
    ids = {c.id for c in discover(home, roots)[0]}
    assert {"skill:mine", "skill:pa:clean", "skill:pa:cred", "command:mycmd", "mcp:gl"} <= ids
    assert {"repo:one", "repo:two"} <= ids
