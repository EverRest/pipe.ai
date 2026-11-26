"""Minimal Slack Web API call over urllib. Used by the status hook (no slack_sdk)."""

import json
import urllib.request


def call_slack(method: str, payload: dict, token: str) -> dict:
    req = urllib.request.Request(  # noqa: S310
        f"https://slack.com/api/{method}",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=5) as r:  # noqa: S310
        return json.load(r)
