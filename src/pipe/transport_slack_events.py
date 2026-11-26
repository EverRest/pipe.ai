"""Slack Socket Mode handlers. The only module that imports `slack_bolt`."""

from collections.abc import Callable

from pipe.core.contract import ClickEvent, MentionEvent, ReactionEvent


def register_handlers(app, emit: Callable) -> None:
    """Map Slack events to neutral events and pass them to `emit`."""

    @app.event("app_mention")
    def _mention(event, body):
        bot_id = event.get("bot_id")
        emit(
            MentionEvent(
                channel=event["channel"],
                ts=event["ts"],
                thread_ts=event.get("thread_ts") or event["ts"],
                sender_id=bot_id or event.get("user"),
                sender_is_bot=bool(bot_id),
                text=event.get("text", ""),
                event_id=body.get("event_id"),
            )
        )

    @app.event("reaction_added")
    def _reaction(event, body):
        item = event["item"]
        emit(
            ReactionEvent(
                body.get("event_id"), item["channel"], item["ts"], event["user"], event["reaction"]
            )
        )

    @app.action(r".*")
    def _click(ack, body):
        ack()
        # block_actions has no event_id; trigger_id is the dedupe key
        emit(
            ClickEvent(
                body.get("trigger_id"),
                body["channel"]["id"],
                body["message"]["ts"],
                body["user"]["id"],
                body["actions"][0]["action_id"],
            )
        )


def register_reconnect(client, callback: Callable[[], None]) -> None:
    """Call `callback` on each Socket Mode `hello` (every connect, A7)."""

    def _on_message(_client, message, _raw):
        if message.get("type") == "hello":
            callback()

    client.message_listeners.append(_on_message)


def start(bot_token: str, app_token: str, emit: Callable, on_reconnect: Callable[[], None]):
    """Build the Bolt app, wire handlers, connect. Returns the handler (call `.close()`)."""
    from slack_bolt import App
    from slack_bolt.adapter.socket_mode import SocketModeHandler

    app = App(token=bot_token)
    register_handlers(app, emit)
    handler = SocketModeHandler(app, app_token)
    register_reconnect(handler.client, on_reconnect)
    handler.connect()
    return handler
