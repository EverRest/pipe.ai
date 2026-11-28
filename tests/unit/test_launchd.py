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
    lp = str(tmp_path / "l" / "pipe")
    launchd.install(lambda c: calls.append(c) or 0, plist_path=p, uid=501, launcher=lp)
    assert p.exists() and lp in p.read_text()
    assert calls[-1] == ["launchctl", "bootstrap", "gui/501", str(p)]
    assert launchd.plist_is_current(p, lp)
    assert not launchd.plist_is_current(p, "/other")
    launchd.remove(lambda c: calls.append(c) or 0, plist_path=p, uid=501)
    assert calls[-1] == ["launchctl", "bootout", "gui/501/com.pipe-ai.adapter"]
    assert not p.exists()


def test_is_loaded():
    assert launchd.is_loaded(lambda c: 0, 501)
    assert not launchd.is_loaded(lambda c: 113, 501)


def test_write_launcher(tmp_path):
    p = tmp_path / "bin" / "pipe"
    launchd.write_launcher(p, python="/v/bin/python")
    text = p.read_text()
    assert p.stat().st_mode & 0o777 == 0o700
    assert text.startswith("#!/bin/sh\n")
    assert 'exec /v/bin/python -m pipe.cli "$@"\n' in text
    assert "token" not in text.lower() and "xox" not in text


def test_launcher_path_has_claude_and_git_dirs(tmp_path, monkeypatch):
    found = {"claude": "/opt/x/bin/claude", "git": "/usr/bin/git"}
    monkeypatch.setattr(launchd.shutil, "which", lambda n: found.get(n))
    p = tmp_path / "pipe"
    launchd.write_launcher(p, python="/v/bin/python")
    lines = p.read_text().splitlines()
    assert lines[1] == "export PATH=/opt/x/bin:/usr/bin:/usr/local/bin:/opt/homebrew/bin:/bin"
    assert lines[-1] == 'exec /v/bin/python -m pipe.cli "$@"'


def test_launcher_path_falls_back_when_not_found(tmp_path, monkeypatch):
    monkeypatch.setattr(launchd.shutil, "which", lambda n: None)
    p = tmp_path / "pipe"
    launchd.write_launcher(p, python="/v/bin/python")
    assert "export PATH=/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin\n" in p.read_text()


def test_install_writes_launcher_first(tmp_path):
    order = []
    p, lp = tmp_path / "x.plist", tmp_path / "bin" / "pipe"

    def run(c):
        order.append(lp.exists())
        return 0

    launchd.install(run, plist_path=p, uid=1, launcher=str(lp))
    assert order == [True] and f"<string>{lp}</string>" in p.read_text()
