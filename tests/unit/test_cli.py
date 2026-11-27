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


def test_run_calls_handler():
    assert main(["run"], run_handler=lambda: 5) == 5


def test_status_hook_always_0(monkeypatch):
    from pipe import hook

    monkeypatch.setattr(hook, "main", lambda e: 1 / 0)
    assert main(["status-hook", "Stop"]) == 0


def test_doctor_exit_codes(monkeypatch, capsys):
    from pipe import doctor

    monkeypatch.setattr(doctor, "check", lambda: [])
    assert main(["doctor"]) == 0
    monkeypatch.setattr(doctor, "check", lambda: ["owner: empty"])
    assert main(["doctor"]) == 1
    assert "FAIL owner: empty" in capsys.readouterr().out


def test_schedule(monkeypatch):
    from pipe import launchd

    seen = []
    monkeypatch.setattr(launchd, "install", lambda run: seen.append("i") or 0)
    monkeypatch.setattr(launchd, "remove", lambda run: seen.append("r") or 0)
    assert main(["schedule", "--install"]) == 0
    assert main(["schedule", "--remove"]) == 0
    assert seen == ["i", "r"]
    assert main(["schedule"]) == 1


def test_metrics_passes_its_args_to_the_handler():
    seen = []
    code = main(["metrics", "--weeks", "2"], metrics_handler=lambda a: seen.append(a) or 3)
    assert (code, seen) == (3, [["--weeks", "2"]])
