"""Real-time Server-Sent Events (SSE) broadcaster for streaming datastore mutations and periodic ticks."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger("mock_api_py.events")


def format_sse(data: Any, event: str | None = None, event_id: str | None = None) -> str:
    """Formats payload according to the Server-Sent Events (SSE) specification."""
    lines: list[str] = []
    if event:
        lines.append(f"event: {event}")
    if event_id:
        lines.append(f"id: {event_id}")

    payload_str = json.dumps(data) if not isinstance(data, str) else data
    for line in payload_str.split("\n"):
        lines.append(f"data: {line}")

    lines.append("\n")
    return "\n".join(lines)


class EventBroadcaster:
    """In-memory pub/sub broadcaster distributing events to connected SSE client queues."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()

    def subscribe(self, maxsize: int = 100) -> asyncio.Queue[dict[str, Any]]:
        """Registers a new client queue subscriber."""
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=maxsize)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        """Removes a client queue subscriber."""
        self._subscribers.discard(queue)

    @property
    def subscriber_count(self) -> int:
        """Returns the number of active subscribers."""
        return len(self._subscribers)

    async def publish(
        self,
        event: str,
        data: Any,
        collection: str | None = None,
        event_id: str | None = None,
    ) -> None:
        """Broadcasts an event message to all registered subscriber queues."""
        if not self._subscribers:
            return

        message = {
            "event": event,
            "data": data,
            "collection": collection,
            "id": event_id,
        }

        # Deliver to all subscriber queues, dropping if queue is full to avoid backpressure hangs
        for q in list(self._subscribers):
            try:
                q.put_nowait(message)
            except asyncio.QueueFull:
                logger.warning("Subscriber queue is full. Dropping event '%s'", event)
            except Exception:
                pass
