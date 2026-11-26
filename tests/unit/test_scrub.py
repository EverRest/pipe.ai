from pipe.core.scrub import scrub


def test_slack_tokens():
    for t in ("xoxb-123-abc-def", "xoxp-123-abc-def", "xapp-1-A0B-123-abcdef"):
        assert scrub(f"key {t} end") == "key [redacted] end"


def test_other_tokens():
    assert scrub("glpat-abcdefghij1234567890") == "[redacted]"
    assert scrub("Authorization: Bearer abcdefghijklmnop1234") == "Authorization: [redacted]"


def test_exact_secret():
    assert scrub("pw hunter2 ok", secrets=["hunter2", ""]) == "pw [redacted] ok"


def test_plain_text_same():
    assert scrub("hello <@U1> world") == "hello <@U1> world"
