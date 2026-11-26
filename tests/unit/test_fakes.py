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
