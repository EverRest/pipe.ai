import pytest

from pipe.cli import main


def _calls(argv):
    seen = []

    def handler(action, name):
        seen.append((action, name))
        return 7

    return main(argv, flows_handler=handler), seen


@pytest.mark.parametrize(
    "argv,expected",
    [
        (["flows"], ("list", None)),
        (["flows", "show", "x"], ("show", "x")),
        (["flows", "validate"], ("validate", None)),
        (["flows", "validate", "x"], ("validate", "x")),
    ],
)
def test_flows_forms_call_handler(argv, expected):
    code, seen = _calls(argv)
    assert code == 7
    assert seen == [expected]


@pytest.mark.parametrize(
    "argv",
    [
        ["flows", "save", "x"],
        ["flows", "delete", "x"],
        ["flows", "show"],
        ["flows", "list", "a", "b"],
    ],
)
def test_flows_rejects_other_forms(argv):
    with pytest.raises(SystemExit) as e:
        _calls(argv)
    assert e.value.code == 2


def test_flows_without_handler(capsys, tmp_path, monkeypatch):
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    assert main(["flows"]) == 1
    assert "flows: not installed" in capsys.readouterr().out
    assert list(cwd.iterdir()) == []


@pytest.mark.parametrize("cmd", ["run", "doctor", "schedule", "status-hook"])
def test_stubs_do_not_crash(cmd, capsys):
    argv = [cmd] + (["Stop"] if cmd == "status-hook" else [])
    assert main(argv) == 1
    assert "not implemented" in capsys.readouterr().err
