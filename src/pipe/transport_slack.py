"""Slack `Transport` over `slack_sdk.WebClient`. Events come from transport_slack_events."""

from collections.abc import Callable
from pathlib import Path

from pipe import transport_slack_events as events
from pipe.core.contract import Identity, check_upload
from pipe.state import pipe_home
from pipe.transport_slack_map import (
    buttons_to_blocks,
    escape_mentions,
    id_pattern,
    mention,
    to_message,
)

PAGE = 100


class SlackTransport:
    id_pattern = id_pattern

    def __init__(self, client, roots: list[Path] | None = None, scrub: Callable | None = None):
        self.client = client  # a slack_sdk WebClient (or a stub)
        self.roots = roots  # upload roots; default PIPE_HOME/run
        self._scrub = scrub
        self._handlers: list[Callable] = []
        self._reconnect_cbs: list[Callable] = []

    # Formatter (pure)
    def mention(self, handle):
        return mention(handle)

    def escape_mentions(self, text):
        return escape_mentions(text)

    def _pages(self, call, key, limit=None, **kw):
        """Yield items of a cursor-paged Slack call. Stop after `limit` items."""
        cursor, n = None, 0
        while True:
            size = PAGE if limit is None else min(PAGE, limit - n)
            r = call(cursor=cursor, limit=size, **kw)
            for item in r[key]:
                yield item
                n += 1
            cursor = (r.get("response_metadata") or {}).get("next_cursor")
            if not cursor or (limit is not None and n >= limit):
                return

    def whoami(self):
        r = self.client.auth_test()
        return Identity(r["bot_id"], r["user_id"])

    def find_channel(self, name):
        for c in self._pages(
            self.client.conversations_list,
            "channels",
            types="public_channel,private_channel",
            exclude_archived=True,
        ):
            if c["name"] == name:
                return c["id"]
        raise KeyError(name)

    def member_channels(self):
        return [
            c["id"]
            for c in self._pages(
                self.client.users_conversations,
                "channels",
                types="public_channel,private_channel",
                exclude_archived=True,
            )
        ]

    def post_message(self, channel, text, thread=None, metadata=None, buttons=None):
        r = self.client.chat_postMessage(
            channel=channel,
            text=text,
            thread_ts=thread,
            metadata=metadata,
            blocks=buttons_to_blocks(buttons),
        )
        return r["ts"]

    def update_message(self, channel, ts, text, metadata=None, buttons=None):
        self.client.chat_update(
            channel=channel, ts=ts, text=text, metadata=metadata, blocks=buttons_to_blocks(buttons)
        )

    def delete_message(self, channel, ts):
        self.client.chat_delete(channel=channel, ts=ts)

    def history(self, channel, oldest=None, limit=None):
        raw = self._pages(
            self.client.conversations_history,
            "messages",
            limit=limit,
            channel=channel,
            oldest=oldest,
            include_all_metadata=True,
        )
        return [to_message(m, channel) for m in reversed(list(raw))]  # Slack: newest first

    def replies(self, channel, thread, oldest=None):
        raw = self._pages(
            self.client.conversations_replies,
            "messages",
            channel=channel,
            ts=thread,
            oldest=oldest,
            include_all_metadata=True,
        )
        return [to_message(m, channel) for m in raw]

    def pin(self, channel, ts):
        self.client.pins_add(channel=channel, timestamp=ts)

    def list_pins(self, channel):
        items = self.client.pins_list(channel=channel)["items"]
        return [i["message"]["ts"] for i in items if i.get("message")]

    def send_dm(self, user_id, text):
        dm = self.client.conversations_open(users=user_id)["channel"]["id"]
        self.client.chat_postMessage(channel=dm, text=text)

    def upload_file(self, channel, thread, name, data, title):
        check_upload(data, self.roots or [pipe_home() / "run"])
        scrub = self._scrub
        if scrub is None:
            from pipe.core.scrub import scrub  # lazy: core module of another stream
        kw = {"file": str(data)} if isinstance(data, Path) else {"content": data}
        r = self.client.files_upload_v2(
            channel=channel, thread_ts=thread, filename=scrub(name), title=scrub(title), **kw
        )
        return r["file"]["permalink"]

    def on_event(self, handler):
        self._handlers.append(handler)

    def on_reconnect(self, callback):
        self._reconnect_cbs.append(callback)

    def _emit(self, event):
        for h in self._handlers:
            h(event)

    def _reconnected(self):
        for cb in self._reconnect_cbs:
            cb()

    def connect(self, bot_token: str, app_token: str):
        """Open Socket Mode. Returns the handler (call `.close()`)."""
        return events.start(bot_token, app_token, self._emit, self._reconnected)
