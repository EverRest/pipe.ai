"""Post one pipe.task.v1 trigger mention to the work channel (stdlib only).

Form A: --pipeline-file (fixed pipeline). Form B: --flow (flow:<name> text).
The bot token is read from the env var named by --token-env. It is never printed.
"""

import argparse
import json
import os
import re
import sys
import urllib.request

_SECRET = re.compile(r"(xox\w-|xapp-|glpat-)\S*")


def _clean(text):
    # One line, no secret, no live mention, max 200 chars.
    text = _SECRET.sub("[redacted]", " ".join(str(text).split()))
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")[:200]


def read_token(name):
    token = os.environ.get(name, "").strip()
    if not token:
        raise ValueError(f"env var {name} is missing or empty")
    return token


def build_trigger_message(channel, agent_user_id, pipeline, flow, title, bot_id):
    if bool(pipeline) == bool(flow):
        raise ValueError("give exactly one of pipeline or flow")
    title = _clean(title)
    if not title:
        raise ValueError("title is empty")
    payload = {"v": 1, "phase": "plan", "status": "needs_approval", "by": bot_id, "hop": 0}
    text = f"<@{agent_user_id}> "
    if pipeline:
        payload["pipeline"] = pipeline
        text += title
    else:
        text += f"flow:{flow} {title}"
    return {
        "channel": channel,
        "text": text,
        "metadata": {"event_type": "pipe.task.v1", "event_payload": payload},
    }


def slack_http(method, body, token):
    req = urllib.request.Request(
        f"https://slack.com/api/{method}",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        return json.load(resp)


def card_main(argv, http):
    from dataclasses import asdict

    from pipe.core.card import CARD_EVENT, Card, skills_hash, validate_card

    a = argparse.ArgumentParser(prog="post_trigger.py card")
    for k in ("token-env", "agents-channel", "owner", "bot-user-id", "name"):
        a.add_argument(f"--{k}", required=True)
    args = a.parse_args(argv)
    try:
        token = read_token(args.token_env)
        bot_id = http("auth.test", {}, token).get("bot_id") or ""
        card = Card(
            name=_clean(args.name), description="Trigger bot", owner=args.owner, bot_id=bot_id,
            bot_user_id=args.bot_user_id, skills=[], hash=skills_hash([]), kind="trigger",
        )  # fmt: skip
        errs = validate_card(card)
        if errs:
            raise ValueError("invalid card: " + ", ".join(errs))
        msg = {
            "channel": args.agents_channel,
            "text": f"{card.name} (trigger), owner {card.owner}",
            "metadata": {"event_type": CARD_EVENT, "event_payload": asdict(card)},
        }
        reply = http("chat.postMessage", msg, token)
    except (ValueError, OSError) as e:
        print(f"error: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    if not reply.get("ok"):
        print(f"error: slack {reply.get('error', 'unknown')}", file=sys.stderr)
        return 1
    print(f"posted card ts={reply.get('ts')}")
    return 0


def main(argv=None, http=slack_http):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["card"]:
        return card_main(argv[1:], http)
    a = argparse.ArgumentParser()
    a.add_argument("--token-env", required=True)
    a.add_argument("--channel", required=True)
    a.add_argument("--agent", required=True)
    a.add_argument("--title", required=True)
    a.add_argument("--pipeline-file")
    a.add_argument("--flow")
    args = a.parse_args(argv)
    try:
        pipeline = None
        if args.pipeline_file:
            with open(args.pipeline_file) as f:
                pipeline = json.load(f)
        build_trigger_message("", "", pipeline, args.flow, args.title, None)  # check before network
        token = read_token(args.token_env)
        bot_id = http("auth.test", {}, token).get("bot_id")
        msg = build_trigger_message(
            args.channel, args.agent, pipeline, args.flow, args.title, bot_id
        )
        reply = http("chat.postMessage", msg, token)
    except (ValueError, OSError) as e:  # json errors are ValueError; never include the token
        print(f"error: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    if not reply.get("ok"):
        print(f"error: slack {reply.get('error', 'unknown')}", file=sys.stderr)
        return 1
    print(f"posted ts={reply.get('ts')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
