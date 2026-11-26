from dataclasses import asdict

import pytest

from fakes import FakeTransport
from pipe.card_sync import sync_card
from pipe.config import validate_config
from pipe.core.card import Identity, build_card
from pipe.core.exposure import render_list, state_of
from pipe.core.summary import build_summary
from pipe.declared import declared_caps
from pipe.owner_summary import send_summary

BASE = {"agent_name": "a1", "slack_tokens": "keychain:pipe-a1", "owner": "U1"}
CH = "C_AGENTS"
CMD, URL, TOK, ENV = "/opt/fake-bin", "https://fake.example/api", "keychain:fake-svc", "FAKE_VAR"
SCHEMA = {"type": "object", "properties": {"repo": {"type": "string"}}}
CAPS = [
    {"id": "lint", "runtime": "exec", "name": "Lint", "description": "Lint", "access": "read",
     "command": [CMD], "env_allow": [ENV], "input_schema": SCHEMA},
    {"id": "deploys", "runtime": "http", "name": "Deploys", "description": "List", "access": "read",
     "url": URL, "token": TOK},
]  # fmt: skip


def conf(**kw):
    return validate_config({**BASE, "capabilities": CAPS, **kw})


def test_list_shows_owner_only_without_secrets():
    c = conf()
    caps = declared_caps(c)
    out = "\n".join(render_list(caps, c.exposed, []))
    assert "exec:lint" in out and "http:deploys" in out and "owner-only" in out
    assert not any(s in out for s in (CMD, URL, TOK, ENV))
    assert all(state_of(x, c.exposed) == "owner-only" for x in caps)


def test_bad_entry_fails_before_any_slack_call():
    with pytest.raises(ValueError):
        conf(capabilities=[{**CAPS[0], "access": "write"}])


def test_card_sync_with_declared_items():
    tr = FakeTransport(channels={"pipe-agents": CH})
    st = {"bot_id": tr.identity.agent_id, "agents_channel_id": CH}
    caps = declared_caps(conf())

    def start(exposed):
        me = tr.whoami()
        ident = Identity("a1", "agent", "U123", me.agent_id, me.handle)
        card = build_card(ident, caps, exposed, {})
        st.update(sync_card(tr, st, card, []))
        summ = build_summary(caps, exposed, [])
        st.update(send_summary(tr, st, "U123", summ))
        return card

    start([])
    assert len(tr.posts) == 1 and start([]).skills == []
    assert len(tr.posts) == 1 and not tr.updates and len(tr.dms) == 1
    ts = tr.posts[0]["ts"]
    card = start(["exec:lint", "http:deploys"])
    assert [x["id"] for x in card.skills] == ["exec:lint", "http:deploys"]
    assert len(tr.posts) == 1 and tr.updates[-1]["ts"] == ts
    assert card.skills[0]["input_schema"] == SCHEMA
    start(["exec:lint"])
    assert [x["id"] for x in asdict(start(["exec:lint"]))["skills"]] == ["exec:lint"]
    assert len(tr.updates) == 2
    seen = repr(tr.posts) + repr(tr.updates) + repr(tr.dms)
    for bad in ("://", "xox", "/Users", "~/", CMD, URL, TOK, ENV):
        assert bad not in seen
    # a new declared item gives exactly one new DM
    n = len(tr.dms)
    caps.append(declared_caps([{**CAPS[1], "id": "more"}])[0])
    start(["exec:lint"])
    assert len(tr.dms) == n + 1
