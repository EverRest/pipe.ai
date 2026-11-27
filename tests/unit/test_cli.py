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
    assert main(["flows"]) == 0
    assert "feature-dev" in capsys.readouterr().out
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


def test_metrics_uses_config_values():
    from types import SimpleNamespace as NS

    from pipe.cli import _metrics_args, _mr_state_reader

    got = []
    cfg = NS(
        work_channel="w", mr_state={"gitlab": {"url": "https://g.example", "token": "keychain:gl"}}
    )
    mk = lambda url, tok: got.append((url, tok)) or "reader"  # noqa: E731
    assert _mr_state_reader(cfg, lambda svc: f"tok-{svc}", mk) == "reader"
    assert got == [("https://g.example", "tok-gl")]
    assert _mr_state_reader(NS(mr_state=None), None, None) is None
    assert _metrics_args(cfg, ["--weeks", "1"]) == ["--channel", "w", "--weeks", "1"]
    assert _metrics_args(cfg, ["--channel", "x"]) == ["--channel", "x"]


def test_declared_http_gets_keychain_reader_and_never_prints_token(capsys):
    from types import SimpleNamespace as NS

    from pipe.cli import _build_runtime
    from pipe.core.contract import RuntimeInput
    from pipe.keychain import read_token

    entry = {
        "id": "h", "runtime": "http", "name": "H", "description": "d", "access": "read",
        "url": "https://api.example/x", "token": "keychain:svc",
    }  # fmt: skip
    cfg = NS(capabilities=[entry], exposed=["http:h"], step_timeout_min=1)
    seen, sent = [], []
    body = b'{"text": "ok", "status": "done"}'

    def transport(url, headers, data, timeout):
        sent.append(headers)
        return 200, body

    def reader(svc):
        seen.append(svc)
        return "tok-1234567890abcdef"

    class Default:
        def run(self, inp):
            return "default"

    rt = _build_runtime(cfg, Default(), reader, transport=transport)
    req = NS(capabilities=("http:h",), access="read", requester_is_owner=True, output_schema=None)
    out = rt.run(RuntimeInput([], {"id": "T", "purpose": "step", "step": 0}, True, req))
    assert out.text == "ok" and seen == ["svc"]
    assert sent[0]["Authorization"] == "Bearer tok-1234567890abcdef"
    assert "tok-1234567890abcdef" not in capsys.readouterr().out + repr(out)
    assert rt.run(RuntimeInput([], {"id": "T"}, True)) == "default"
    with pytest.raises(ValueError):
        read_token("svc", "token")
