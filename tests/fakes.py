"""Test doubles. No chat library needed."""

from dataclasses import replace
from pathlib import Path

from pipe.core.contract import (
    Identity,
    Message,
    RuntimeFailed,
    RuntimeInput,
    RuntimeOutput,
    check_upload,
)
from pipe.state import pipe_home  # noqa: E402

PAGE = 100


class FakeTransport:
    """In-memory Transport (the former FakeSlack)."""

    id_pattern = r"^[BUW][A-Z0-9]{2,}$"
    FILE_LINK = "https://files.example/fake"

    def __init__(self, bot_id="B1", handle="U1", channels=None, upload_roots=None):
        self.upload_roots = upload_roots  # default: PIPE_HOME/run
        self.identity = Identity(bot_id, handle)
        self.channels = dict(channels or {"pipe-status": "C_STATUS"})
        self.messages: list[Message] = []  # all messages, in ts order
        self.posts: list[dict] = []
        self.updates: list[dict] = []
        self.deleted: list[tuple] = []
        self.pins: dict[str, list[str]] = {}
        self.dms: list[tuple] = []
        self.uploads: list[dict] = []  # no content recorded
        self.history_pages: list[int] = []  # page count per history/replies call
        self.handlers: list = []
        self.reconnect_callbacks: list = []
        self.link_down = False
        self._held: list[Message] = []
        self._n = 0

    def _ts(self) -> str:
        self._n += 1
        return f"{1700000000 + self._n}.000000"

    def add_message(self, channel, text, sender_id="U9", thread=None, ts=None, **kw) -> Message:
        """Seed a message from a user (held while the link is down)."""
        ts = ts or self._ts()
        m = Message(
            channel, ts, thread or ts, sender_id, kw.pop("sender_is_bot", False), text, **kw
        )
        (self._held if self.link_down else self.messages).append(m)
        if not self.link_down and m.thread != m.ts:
            self._bump(channel, m.thread, m.ts)
        return m

    def _bump(self, channel, thread, ts):
        for i, p in enumerate(self.messages):
            if p.channel == channel and p.ts == thread:
                self.messages[i] = replace(p, latest_reply=ts)

    # Transport
    def whoami(self):
        return self.identity

    def find_channel(self, name):
        return self.channels[name]

    def member_channels(self):
        return list(self.channels.values())

    def post_message(self, channel, text, thread=None, metadata=None, buttons=None):
        ts = self._ts()
        self.posts.append(
            {"channel": channel, "text": text, "thread": thread, "metadata": metadata,
             "buttons": buttons, "ts": ts}
        )  # fmt: skip
        self.messages.append(
            Message(channel, ts, thread or ts, self.identity.agent_id, True, text,
                    self.identity.handle, metadata)
        )  # fmt: skip
        if thread:
            self._bump(channel, thread, ts)
        return ts

    def update_message(self, channel, ts, text, metadata=None, buttons=None):
        self.updates.append(
            {"channel": channel, "ts": ts, "text": text, "metadata": metadata, "buttons": buttons}
        )
        for i, m in enumerate(self.messages):
            if m.channel == channel and m.ts == ts:
                self.messages[i] = replace(m, text=text, metadata=metadata or m.metadata)

    def delete_message(self, channel, ts):
        self.deleted.append((channel, ts))
        self.messages = [m for m in self.messages if (m.channel, m.ts) != (channel, ts)]

    def _serve(self, msgs, oldest, limit):
        if oldest:
            msgs = [m for m in msgs if float(m.ts) > float(oldest)]
        if limit:
            msgs = msgs[-limit:]  # oldest first, newest N kept
        self.history_pages.append(max(1, -(-len(msgs) // PAGE)))  # cursor pages of 100
        return msgs

    def history(self, channel, oldest=None, limit=None):
        msgs = [m for m in self.messages if m.channel == channel and m.thread == m.ts]
        return self._serve(msgs, oldest, limit)

    def replies(self, channel, thread, oldest=None):
        msgs = [m for m in self.messages if m.channel == channel and m.thread == thread]
        return self._serve(msgs, oldest, None)

    def pin(self, channel, ts):
        self.pins.setdefault(channel, []).append(ts)

    def list_pins(self, channel):
        return list(self.pins.get(channel, []))

    def send_dm(self, user_id, text):
        self.dms.append((user_id, text))

    def upload_file(self, channel, thread, name, data, title):
        size = check_upload(data, self.upload_roots or [pipe_home() / "run"])
        self.uploads.append(
            {"channel": channel, "thread": thread, "name": name, "title": title,
             "kind": "path" if isinstance(data, Path) else "bytes", "size": size}
        )  # fmt: skip
        return self.FILE_LINK

    def on_event(self, handler):
        self.handlers.append(handler)

    def on_reconnect(self, callback):
        self.reconnect_callbacks.append(callback)

    def raise_event(self, event):
        for h in self.handlers:
            h(event)

    def reconnect(self):
        """Link back: serve held messages, then run the callbacks."""
        self.link_down = False
        self.messages.extend(self._held)
        for m in self._held:
            if m.thread != m.ts:
                self._bump(m.channel, m.thread, m.ts)
        self._held.clear()
        for cb in self.reconnect_callbacks:
            cb()

    # Formatter
    def mention(self, handle):
        return f"<@{handle}>"

    def escape_mentions(self, text):
        # Same rule as the Slack adapter: escape & < > (see transport_slack_map.escape_mentions).
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class FakeCallSlack:
    """Recording fake of call_slack(method, payload)."""

    def __init__(self, response=None, error=None):
        self.calls: list[tuple] = []
        self.response = response or {"ok": True, "channel": "C_STATUS", "ts": "1700000001.000000"}
        self.error = error  # exception to raise, e.g. TimeoutError()

    def __call__(self, method, payload):
        self.calls.append((method, payload))
        if self.error:
            raise self.error
        return dict(self.response)


class FakeRuntime:
    """Returns a canned RuntimeOutput and records its inputs."""

    def __init__(self, output=None, error=None):
        self.output = output or RuntimeOutput(text="ok", status="done")
        self.error = error  # RuntimeFailed reason string
        self.inputs: list[RuntimeInput] = []

    def run(self, inp):
        self.inputs.append(inp)
        if self.error:
            raise RuntimeFailed(self.error)
        return self.output


class FakeKeychain:
    """Canned tokens. Use as `read_token`: fake(service, account)."""

    def __init__(self, tokens=None):
        self.tokens = tokens or {"bot": "xoxb-fake", "app": "xapp-fake"}

    def __call__(self, service, account):
        return self.tokens[account]
