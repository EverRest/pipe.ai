"""sync_card with FakeTransport and a state dict (T030, T046 integration)."""

import re

from fakes import FakeTransport
from pipe.card_sync import sync_card
from pipe.core.capability import Capability, Notice
from pipe.core.card import CARD_EVENT, Identity, build_card

CH = "C_AGENTS"
SKILL = Capability("skill:a", "a", "does a", open=True)
SKILL_B = Capability("skill:b", "b", "does b", open=True)
CLOSED = Capability("skill:c", "c", "does c")


def make(**kw):
    tr = FakeTransport(channels={"pipe-agents": CH}, **kw)
    state = {"bot_id": tr.identity.agent_id, "agents_channel_id": CH}
    return tr, state


def start(tr, state, caps, exposed=(), tag_map=None, owner="U123", notices=()):
    """One adapter start: build the card, sync, save the returned values."""
    me = tr.whoami()
    card = build_card(
        Identity("coder", "agent", owner, me.agent_id, me.handle), caps, exposed, tag_map or {}
    )
    state.update(sync_card(tr, state, card, list(notices)))
    return card


def test_first_start_posts_and_pins():
    tr, st = make()
    start(tr, st, [SKILL])
    assert len(tr.posts) == 1 and tr.posts[0]["metadata"]["event_type"] == CARD_EVENT
    ts = tr.posts[0]["ts"]
    assert tr.pins[CH] == [ts]
    assert st["card"] == {"channel": CH, "ts": ts, "hash": st["card"]["hash"]}


def test_no_change_no_calls_and_ten_starts_one_card():
    tr, st = make()
    for _ in range(10):
        start(tr, st, [SKILL])
    assert len(tr.posts) == 1 and not tr.updates


def test_new_skill_updates_same_ts():
    tr, st = make()
    start(tr, st, [SKILL])
    ts = st["card"]["ts"]
    start(tr, st, [SKILL, SKILL_B])
    assert len(tr.posts) == 1 and tr.updates[0]["ts"] == ts
    assert tr.updates[0]["text"] and tr.updates[0]["metadata"]
    assert st["card"]["ts"] == ts


def test_exposed_toggle_and_notice_only():
    tr, st = make()
    start(tr, st, [SKILL, CLOSED])
    start(tr, st, [SKILL, CLOSED], exposed=["skill:c"])
    assert "skill:c" in tr.updates[-1]["text"]
    start(tr, st, [SKILL, CLOSED])
    assert "skill:c" not in tr.updates[-1]["text"]
    n = len(tr.updates)
    start(tr, st, [SKILL, CLOSED], notices=[Notice("unknown_id", "x", "gone")])
    assert len(tr.updates) == n  # a notice alone changes nothing


def test_tag_map_adds_tag_same_ts():
    tr, st = make()
    start(tr, st, [CLOSED], exposed=["skill:c"])
    start(tr, st, [CLOSED], exposed=["skill:c"], tag_map={"skill:c": ["review"]})
    skills = tr.updates[0]["metadata"]["event_payload"]["skills"]
    assert "review" in skills[0]["tags"] and tr.updates[0]["ts"] == st["card"]["ts"]


def test_card_deleted_posts_new():
    tr, st = make()
    start(tr, st, [SKILL])
    tr.delete_message(CH, st["card"]["ts"])

    def gone(*a, **k):
        raise RuntimeError("message_not_found")

    tr.update_message = gone
    start(tr, st, [SKILL, SKILL_B])
    assert len(tr.posts) == 2 and st["card"]["ts"] == tr.posts[1]["ts"]
    assert tr.pins[CH][-1] == tr.posts[1]["ts"]


def test_unpinned_card_is_pinned_again_not_edited():
    tr, st = make()
    start(tr, st, [SKILL])
    tr.pins[CH].clear()
    start(tr, st, [SKILL])
    assert tr.pins[CH] == [st["card"]["ts"]] and not tr.updates and len(tr.posts) == 1


def test_recovery_from_history_without_state_key():
    tr, st = make()
    start(tr, st, [SKILL])
    del st["card"]
    start(tr, st, [SKILL])
    assert len(tr.posts) == 1 and not tr.updates and st["card"]["ts"] == tr.posts[0]["ts"]


def test_empty_owner_posts_nothing(caplog):
    tr, st = make()
    me = tr.whoami()
    card = build_card(Identity("c", "d", "U1", me.agent_id, me.handle), [SKILL], (), {})
    object.__setattr__(card, "owner", "")
    assert sync_card(tr, st, card, []) == {} and not tr.posts


def test_slack_error_is_logged_not_raised():
    tr, st = make()

    def boom(*a, **k):
        raise OSError("slack down")

    tr.post_message = boom
    assert start(tr, st, [SKILL]) and "card" not in st


def test_card_has_no_leaks():
    leaky = Capability(
        "skill:l", "l", "see https://x.example/a /Users/me/x xoxb-123-abc ~/f", open=True
    )
    tr, st = make()
    start(tr, st, [leaky])
    blob = repr(tr.posts)
    assert not re.search(r"http|xox|/Users|~/", blob)


def test_bot_user_id_in_metadata_and_escaped_text():
    tr, st = make(handle="U777")
    start(tr, st, [SKILL])
    assert tr.posts[0]["metadata"]["event_payload"]["bot_user_id"] == "U777"
    assert "<@" not in tr.posts[0]["text"]


def test_bot_user_id_change_alone_no_update():
    tr, st = make(handle="U777")
    start(tr, st, [SKILL])
    tr.identity = type(tr.identity)(tr.identity.agent_id, "U888")
    start(tr, st, [SKILL])
    assert not tr.updates
