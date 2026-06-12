import asyncio
import logging
from collections import deque
import httpx

logger = logging.getLogger("prompt_shields.telemetry")

MAX_BUFFER_SIZE = 1000

# atlas.ai prompt-events ingestion (see atlas.ai
# docs/superpowers/specs/2026-06-11-prompt-telemetry-design.md)
ATLAS_EVENTS_PATH = "/api/v1/telemetry/prompt-events"
ATLAS_MAX_BATCH = 500  # server rejects envelopes with more than 500 events


class TelemetrySender:
    """Buffers telemetry events and sends to collector. Fail-open: never blocks LLM calls.

    The keyword-only params exist for subclasses (see AtlasTelemetrySender);
    their defaults reproduce the original collector behavior exactly.
    """

    def __init__(
        self,
        collector_url: str,
        api_key: str,
        *,
        path: str = "/ingest/events",
        headers: dict[str, str] | None = None,
        max_batch: int | None = None,
    ):
        self._url = f"{collector_url.rstrip('/')}{path}"
        self._api_key = api_key
        self._headers = (
            headers if headers is not None
            else {"Authorization": f"Bearer {api_key}"}
        )
        self._max_batch = max_batch
        self._buffer: deque[dict] = deque(maxlen=MAX_BUFFER_SIZE)
        self._sync_client = httpx.Client(timeout=5.0)
        self._async_client = httpx.AsyncClient(timeout=5.0)

    def enqueue(self, event: dict) -> None:
        """Add event to buffer. If buffer full, oldest event is dropped (fail-open)."""
        if len(self._buffer) >= MAX_BUFFER_SIZE:
            logger.warning("Telemetry buffer full, dropping oldest event")
        self._buffer.append(event)

    def _drain_chunks(self) -> list[list[dict]]:
        """Drain the buffer into request-sized chunks (one chunk when unlimited)."""
        events = list(self._buffer)
        self._buffer.clear()
        if self._max_batch is None:
            return [events]
        return [
            events[i:i + self._max_batch]
            for i in range(0, len(events), self._max_batch)
        ]

    async def flush(self) -> None:
        """Async flush: send all buffered events. Swallows errors (fail-open).

        A 200 response is final even if the server skipped rows — skipped rows
        failed validation and can never succeed on retry. Only network errors
        and non-200 responses re-buffer.
        """
        if not self._buffer:
            return
        for chunk in self._drain_chunks():
            try:
                resp = await self._async_client.post(
                    self._url,
                    json={"events": chunk},
                    headers=self._headers,
                )
                if resp.status_code != 200:
                    logger.warning(f"Telemetry send failed: {resp.status_code}")
                    for e in chunk:
                        self.enqueue(e)
            except Exception as e:
                logger.warning(f"Telemetry send error: {e}")
                for ev in chunk:
                    self.enqueue(ev)

    def flush_sync(self) -> None:
        """Synchronous flush using httpx.Client. Fail-open with 5s timeout."""
        if not self._buffer:
            return
        for chunk in self._drain_chunks():
            try:
                resp = self._sync_client.post(
                    self._url,
                    json={"events": chunk},
                    headers=self._headers,
                )
                if resp.status_code != 200:
                    logger.warning(f"Telemetry send failed: {resp.status_code}")
                    for e in chunk:
                        self.enqueue(e)
            except Exception as e:
                logger.warning(f"Telemetry send error: {e}")
                for ev in chunk:
                    self.enqueue(ev)

    async def close(self) -> None:
        await self.flush()
        await self._async_client.aclose()
        self._sync_client.close()


class AtlasTelemetrySender(TelemetrySender):
    """Second telemetry destination: atlas.ai prompt-events ingestion.

    Same buffer/flush/fail-open machinery as TelemetrySender, but:
      - POSTs to {atlas_url}/api/v1/telemetry/prompt-events
      - authenticates with X-API-Key (aigrc_ keys), not a Bearer token
      - chunks each flush at 500 events (server-side envelope limit)
    """

    def __init__(self, atlas_url: str, atlas_api_key: str):
        super().__init__(
            atlas_url,
            atlas_api_key,
            path=ATLAS_EVENTS_PATH,
            headers={"X-API-Key": atlas_api_key},
            max_batch=ATLAS_MAX_BATCH,
        )
