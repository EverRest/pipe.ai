import subprocess

import pytest

from pipe.keychain import KeychainError, read_token


def runner(out="xoxb-secret\n", code=0):
    calls = []

    def run(cmd):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, code, out, "")

    run.calls = calls
    return run


def test_read_token_command_and_strip():
    r = runner()
    assert read_token("svc", "bot", run=r) == "xoxb-secret"
    assert r.calls == [["security", "find-generic-password", "-s", "svc", "-a", "bot", "-w"]]


def test_bad_account():
    with pytest.raises(ValueError):
        read_token("svc", "other", run=runner())


def test_failure_hides_token():
    with pytest.raises(KeychainError) as e:
        read_token("svc", "app", run=runner(out="xapp-secret", code=44))
    assert "xapp-secret" not in str(e.value)
