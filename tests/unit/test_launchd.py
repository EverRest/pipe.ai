import plistlib

from pipe import launchd


def test_plist_fields(tmp_path):
    d = plistlib.loads(
        launchd.plist_text("/h/.pipe/bin/pipe", "/h/.pipe/logs/adapter.log").encode()
    )
    assert d["Label"] == "com.pipe-ai.adapter"
    assert d["RunAtLoad"] is True and d["KeepAlive"] is True and d["ThrottleInterval"] == 10
    assert d["StandardOutPath"] == d["StandardErrorPath"] == "/h/.pipe/logs/adapter.log"
    assert d["ProgramArguments"] == ["/h/.pipe/bin/pipe", "run"]


def test_install_remove(tmp_path):
    calls = []
    p = tmp_path / "x.plist"
    launchd.install(lambda c: calls.append(c) or 0, plist_path=p, uid=501, launcher="/l/pipe")
    assert p.exists() and "/l/pipe" in p.read_text()
    assert calls[-1] == ["launchctl", "bootstrap", "gui/501", str(p)]
    assert launchd.plist_is_current(p, "/l/pipe")
    assert not launchd.plist_is_current(p, "/other")
    launchd.remove(lambda c: calls.append(c) or 0, plist_path=p, uid=501)
    assert calls[-1] == ["launchctl", "bootout", "gui/501/com.pipe-ai.adapter"]
    assert not p.exists()


def test_is_loaded():
    assert launchd.is_loaded(lambda c: 0, 501)
    assert not launchd.is_loaded(lambda c: 113, 501)
