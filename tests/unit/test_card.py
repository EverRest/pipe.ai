import hashlib
import json

from pipe.core.card import sanitize_text, skills_hash


def test_urls_paths():
    for s in ("https://a.b/c", "http://x", "wss://h/p"):
        assert sanitize_text(f"see {s} now") == "see [removed] now"
    for p in ("/Users/x/y", "~/code/x", "/home/x/y", "/private/tmp/x"):
        assert sanitize_text(f"in {p} ok") == "in [removed] ok"
    assert sanitize_text("use and/or") == "use and/or"


def test_token_spaces_cut():
    assert sanitize_text("k xoxb-123-abc-def z") == "k [redacted] z"
    assert sanitize_text("a   b\n c") == "a b c"
    assert len(sanitize_text("x" * 500)) == 200
    assert len(sanitize_text("x" * 500, 10)) == 10


SK = [{"id": "b", "name": "B"}, {"id": "a", "name": "A"}]


def test_hash_vector_and_order():
    canon = '[{"id":"a","name":"A"},{"id":"b","name":"B"}]'
    h = hashlib.sha256(canon.encode()).hexdigest()
    assert skills_hash(SK) == h
    assert skills_hash(SK[::-1]) == h
    assert (
        json.dumps(sorted(SK, key=lambda s: s["id"]), sort_keys=True, separators=(",", ":"))
        == canon
    )
    assert skills_hash([{"id": "a", "name": "A2"}, SK[0]]) != h
