from pathlib import Path
from types import SimpleNamespace as NS

from pipe.cli import main, make_flows_handler


def _flow(name):
    steps = (
        NS(id="a", capability="tag:build", access="write", goal="do it"),
        NS(id="h", capability=None, access="approve", goal="sign off"),
    )
    return NS(name=name, description=f"{name} desc", steps=steps)


def _run(argv, errors=(), flows=("x", "y")):
    h = make_flows_handler(lambda: ({n: _flow(n) for n in flows}, list(errors)))
    return main(argv, flows_handler=h)


def test_list(capsys):
    assert _run(["flows"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out == ["x  x desc  1", "y  y desc  1"]


def test_show(capsys):
    assert _run(["flows", "show", "x"]) == 0
    out = capsys.readouterr().out
    assert "0 a tag:build write do it" in out and "1 h human approve sign off" in out


def test_show_unknown(capsys):
    assert _run(["flows", "show", "zz"]) == 1
    assert "unknown flow" in capsys.readouterr().out


def test_validate_all_and_refusal(capsys):
    assert _run(["flows", "validate"]) == 0
    assert capsys.readouterr().out.splitlines() == ["ok x", "ok y"]
    assert _run(["flows", "validate"], errors=["bad: step s: tag not in vocabulary"]) == 1
    assert "bad: step s: tag not in vocabulary" in capsys.readouterr().out


def test_validate_one(capsys):
    assert _run(["flows", "validate", "x"], errors=["y: broken"]) == 0
    assert capsys.readouterr().out == "ok x\n"
    assert _run(["flows", "validate", "zz"]) == 1
    assert "unknown flow" in capsys.readouterr().out


def test_import_error_prints_not_installed(capsys, monkeypatch):
    import pipe.cli as cli

    def boom():
        raise ImportError

    monkeypatch.setattr(cli, "_default_load", boom)
    assert main(["flows"]) == 1
    assert "flows: not installed" in capsys.readouterr().out


def test_flows_list_reads_pipe_home_override(tmp_path, monkeypatch, capsys):
    import pipe.cli as cli

    monkeypatch.setenv("PIPE_HOME", str(tmp_path))
    (tmp_path / "flows").mkdir()
    text = Path("flows/review-handoff.yaml").read_text()
    (tmp_path / "flows" / "mine.yaml").write_text(text.replace("review-handoff", "mine", 1))
    assert cli.main(["flows"]) == 0
    assert "mine" in capsys.readouterr().out
