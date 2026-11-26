"""Send the owner summary DM when its hash changes."""

import logging

from pipe.core.summary import decide_dm

log = logging.getLogger(__name__)


def send_summary(slack, state: dict, owner: str, summary) -> dict:
    """Return {"summary_hash": ...} after a DM, else {}. Never raises."""
    if not owner:
        log.warning("summary not sent: owner is empty")
        return {}
    if decide_dm(summary.hash, state.get("summary_hash")) == "none":
        return {}
    try:
        # hash is made before the escape (core/summary.py)
        slack.send_dm(owner, slack.escape_mentions(summary.text))
    except Exception as e:
        log.error("summary DM failed: %s", e)
        return {}
    return {"summary_hash": summary.hash}
