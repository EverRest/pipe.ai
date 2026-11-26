"""Ports of the core. No chat library is imported here."""

from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from pipe.core.contract import Button, Identity, Message, RuntimeInput, RuntimeOutput


class Formatter(Protocol):
    id_pattern: str

    def mention(self, handle: str) -> str: ...
    def escape_mentions(self, text: str) -> str: ...


class Transport(Formatter, Protocol):
    def whoami(self) -> Identity: ...
    def find_channel(self, name: str) -> str: ...
    def member_channels(self) -> list[str]: ...
    def post_message(
        self,
        channel: str,
        text: str,
        thread: str | None = None,
        metadata: dict | None = None,
        buttons: list[Button] | None = None,
    ) -> str: ...
    def update_message(
        self,
        channel: str,
        ts: str,
        text: str,
        metadata: dict | None = None,
        buttons: list[Button] | None = None,
    ) -> None: ...
    def delete_message(self, channel: str, ts: str) -> None: ...
    def history(
        self, channel: str, oldest: str | None = None, limit: int | None = None
    ) -> list[Message]:
        """Top-level messages with ts > oldest, oldest first.

        `limit` keeps the newest N (catch-up needs the latest parents).
        Slack returns newest first: the adapter must reverse it.
        """
        ...

    def replies(self, channel: str, thread: str, oldest: str | None = None) -> list[Message]: ...
    def pin(self, channel: str, ts: str) -> None: ...
    def list_pins(self, channel: str) -> list[str]: ...
    def send_dm(self, user_id: str, text: str) -> None: ...
    def upload_file(
        self, channel: str, thread: str, name: str, data: bytes | Path, title: str
    ) -> str: ...
    def on_event(self, handler: Callable[[Any], None]) -> None: ...
    def on_reconnect(self, callback: Callable[[], None]) -> None: ...


class RuntimePort(Protocol):
    def run(self, inp: RuntimeInput) -> RuntimeOutput: ...  # raises RuntimeFailed
