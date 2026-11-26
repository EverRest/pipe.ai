import os
import stat

import pytest

from pipe import doctor
from pipe.keychain import KeychainError


@pytest.fixture
def good(pipe_home):
    (pipe_home / "config.yaml").write_text(
        "agent_name: c\nslack_tokens: keychain:pipe-c\nowner: U1\n"
    )
    pipe_home.chmod(0o700)
    return pipe_home


def reader(service, account):
    return "xoxb-secret"


def test_good_setup(good):
    assert doctor.check(reader) == []


def test_missing_token(good):
    def bad(service, account):
        raise KeychainError("nope")

    probs = doctor.check(bad)
    assert len(probs) == 2 and all(
        "pipe-c" in x and "security add-generic-password" in x for x in probs
    )
    assert "xox" not in "".join(probs)


def test_no_config(pipe_home):
    pipe_home.chmod(0o700)
    probs = doctor.check(reader)
    assert len(probs) == 1 and "config" in probs[0]


def test_empty_owner(good):
    (good / "config.yaml").write_text("agent_name: c\nslack_tokens: keychain:pipe-c\n")
    assert any("owner" in p for p in doctor.check(reader))


def test_loose_mode(good):
    good.chmod(0o755)
    probs = doctor.check(reader)
    assert any("mode" in p for p in probs)
    assert stat.S_IMODE(os.stat(good).st_mode) == 0o755  # check only, no fix
