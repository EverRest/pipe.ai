"""upload_run_files: the stepper uploads confined run files and links them (FR-026)."""

import pytest

from fakes import FakeTransport
from pipe.core.contract import UploadRefused
from pipe.runtime_exec import ExecOutput
from pipe.stepper import Stepper
from unit.test_stepper import Rig, first_handoff, meta


def stepper(root):
    t = FakeTransport(upload_roots=[root])
    return t, Stepper(t, None, None, {})


def test_two_files_in_order_name_is_base_name_title_scrubbed(tmp_path):
    a, b = tmp_path / "a.png", tmp_path / "b.html"
    a.write_text("x")
    b.write_text("y")
    t, st = stepper(tmp_path)
    links = st.upload_run_files("C", "T", [str(a), str(b)], "shot xoxb-123456789012")
    assert links == [t.FILE_LINK] * 2
    assert [u["name"] for u in t.uploads] == ["a.png", "b.html"]
    assert all(u["kind"] == "path" and "xoxb" not in u["title"] for u in t.uploads)


def test_no_files_no_call(tmp_path):
    t, st = stepper(tmp_path)
    assert st.upload_run_files("C", "T", [], "g") == [] and t.uploads == []


def test_refused_stops_at_the_first_bad_path(tmp_path):
    ok = tmp_path / "ok.txt"
    ok.write_text("x")
    t, st = stepper(tmp_path)
    with pytest.raises(UploadRefused):
        st.upload_run_files("C", "T", ["/etc/hosts", str(ok)], "g")
    assert t.uploads == []


def run_with(tmp_path, files):
    out = ExecOutput("done text", artifacts=["https://x/1"], files=files)
    r = Rig(seed=[first_handoff()], out=out)
    r.ft.upload_roots = [tmp_path]
    r.st.run_step(r.ev(first_handoff()), 0)
    return r


def test_step_links_files_in_artifacts_and_posts_no_path(tmp_path):
    f = tmp_path / "r.html"
    f.write_text("x")
    r = run_with(tmp_path, [str(f)])
    p = meta(r.last_post())
    assert p["artifacts"] == ["https://x/1", r.ft.FILE_LINK]
    assert str(tmp_path) not in " ".join(x["text"] for x in r.ft.posts + r.ft.updates)


def test_refused_file_fails_the_step(tmp_path):
    r = run_with(tmp_path, ["/etc/hosts"])
    p = meta(r.ft.updates[-1])
    assert (p["status"], p["reason"]) == ("failed", "upload refused")
    assert r.ft.updates[-1]["buttons"]  # Retry
    assert not [x for x in r.ft.posts if "next" in (x["metadata"] or {}).get("event_payload", {})]
