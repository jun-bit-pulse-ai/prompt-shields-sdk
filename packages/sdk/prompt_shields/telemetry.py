import asyncio
import logging
import threading
from collections import deque
import httpx

logger = logging.getLogger("prompt_shields.telemetry")

MAX_BUFFER_SIZE = 1000


class TelemetrySender:
    """Async sender that buffers events and sends to collector. Fail-open: never blocks LLM calls."""

    def __init__(self, collector_url: str, api_key: str):
        self._url = f"{collector_url.rstrip('/')}/ingest/events"
        self._api_key = api_key
        self._buffer: deque[dict] = deque(maxlen=MAX_BUFFER_SIZE)
        self._client = httpx.AsyncClient(timeout=5.0)

    def enqueue(self, event: dict) -> None:
        """Add event to buffer. If buffer full, oldest event is dropped (fail-open)."""
        if len(self._buffer) >= MAX_BUFFER_SIZE:
            logger.warning("Telemetry buffer full, dropping oldest event")
        self._buffer.append(event)

    async def flush(self) -> None:
        """Send all buffered events to collector. Swallows errors (fail-open)."""
        if not self._buffer:
            return
        events = list(self._buffer)
        self._buffer.clear()
        try:
            resp = await self._client.post(
                self._url,
                json={"events": events},
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
            if resp.status_code != 200:
                logger.warning(f"Telemetry send failed: {resp.status_code}")
                for e in events:
                    self.enqueue(e)
        except Exception as e:
            logger.warning(f"Telemetry send error: {e}")
            for ev in events:
                self.enqueue(ev)

    def flush_sync(self) -> None:
        """Synchronous flush for use after each LLM call. Uses a thread to avoid event loop issues."""
        def _run():
            asyncio.run(self.flush())
        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=5.0)

    async def close(self) -> None:
        await self.flush()
        await self._client.aclose()
