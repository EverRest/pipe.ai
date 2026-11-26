import pytest


@pytest.fixture(autouse=True)
def pipe_home(tmp_path, monkeypatch):
    """Point PIPE_HOME at a temporary directory (research.md D2 'State')."""
    home = tmp_path / "pipe_home"
    home.mkdir()
    monkeypatch.setenv("PIPE_HOME", str(home))
    monkeypatch.delenv("PIPE_RUNTIME", raising=False)
    return home
