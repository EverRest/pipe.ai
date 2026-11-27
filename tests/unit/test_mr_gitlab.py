from pipe.mr_gitlab import mr_link_from_push

BASE = "https://git.example.com"
LINK = "https://git.example.com/grp/proj/-/merge_requests/12"
OUT = f"remote:\nremote: View merge request for pipe/x:\nremote:   {LINK}\nremote:\n"


def test_valid_link():
    assert mr_link_from_push(OUT, BASE) == LINK


def test_other_host_refused():
    out = "remote:   https://evil.example.org/grp/proj/-/merge_requests/12\n"
    assert mr_link_from_push(out, BASE) is None
    assert mr_link_from_push("https://git.example.com.evil.org/a/-/merge_requests/1", BASE) is None
    assert mr_link_from_push("https://user:tok@git.example.com/a/-/merge_requests/1", BASE) is None


def test_http_scheme_refused():
    assert mr_link_from_push(LINK.replace("https", "http"), BASE) is None


def test_no_link_none():
    assert mr_link_from_push("Everything up-to-date\n", BASE) is None


def test_bad_input_none():
    for bad in ("", None, 5, b"x"):
        assert mr_link_from_push(bad, BASE) is None
    assert mr_link_from_push(OUT, "http://git.example.com") is None
    assert mr_link_from_push(OUT, "") is None


def test_first_valid_link_wins_over_foreign():
    out = "https://evil.example.org/a/-/merge_requests/1\n" + OUT
    assert mr_link_from_push(out, BASE) == LINK


def test_token_never_leaks():
    tok = "glpat-SECRET123"
    out = f"remote: https://oauth2:{tok}@git.example.com/a/-/merge_requests/1\n"
    assert mr_link_from_push(out, BASE) is None
    assert tok not in str(mr_link_from_push(OUT + tok, BASE))
