"""Tests for the optional atlas.ai telemetry sink.

Wire contract: POST {atlas}/api/v1/telemetry/prompt-events, X-API-Key header,
{"events": [...]} envelope (1-500), 200 + {ingested, skipped, skipped_reasons}.
Server-skipped rows are final; only network/HTTP failures re-buffer.
Spec: atlas.ai docs/superpowers/specs/2026-06-11-prompt-telemetry-design.md.

HTTP is mocked by swapping the sender's private httpx clients for ones built
on httpx.MockTransport (respx is not installed; existing tests never mock
httpx because they never hit the network).
"""
import hashlib
import json
import re

import httpx
import pytest

from prompt_shields.telemetry import (
    ATLAS_EVENTS_PATH,
    ATLAS_MAX_BATCH,
    AtlasTelemetrySender,
)


# --- helpers ----------------------------------------------------------------


def _ok_body(ingested=1, skipped=0, reasons=None):
    return {"ingested": ingested, "skipped": skipped,
            "skipped_reasons": reasons or []}


def _capture_transport(captured: list, status_code: int = 200, body: dict | None = None):
    """MockTransport that records every request and returns a canned response."""
    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(status_code, json=body if body is not None else _ok_body())
    return httpx.MockTransport(handler)


def _error_transport():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)
    return httpx.MockTransport(handler)


def _atlas_sender(transport: httpx.MockTransport) -> AtlasTelemetrySender:
    sender = AtlasTelemetrySender("http://atlas.test/", "aigrc_test_key")
    sender._sync_client = httpx.Client(transport=transport)
    sender._async_client = httpx.AsyncClient(transport=transport)
    return sender


# --- transport: envelope, header, endpoint ----------------------------------


def test_atlas_sender_posts_envelope_with_x_api_key_header():
    captured: list[httpx.Request] = []
    sender = _atlas_sender(_capture_transport(captured))
    sender.enqueue({"source": "sdk", "event_kind": "activity"})
    sender.flush_sync()

    assert len(captured) == 1
    req = captured[0]
    assert req.url.path == ATLAS_EVENTS_PATH == "/api/v1/telemetry/prompt-events"
    assert req.headers["x-api-key"] == "aigrc_test_key"
    assert "authorization" not in req.headers  # X-API-Key, not Bearer
    body = json.loads(req.content)
    assert body == {"events": [{"source": "sdk", "event_kind": "activity"}]}
    assert len(sender._buffer) == 0  # 200 => delivered, nothing re-buffered


@pytest.mark.asyncio
async def test_atlas_sender_async_flush_same_envelope():
    captured: list[httpx.Request] = []
    sender = _atlas_sender(_capture_transport(captured))
    sender.enqueue({"source": "sdk", "event_kind": "activity"})
    await sender.flush()

    assert len(captured) == 1
    assert captured[0].headers["x-api-key"] == "aigrc_test_key"
    assert json.loads(captured[0].content)["events"][0]["source"] == "sdk"
    assert len(sender._buffer) == 0


# --- fail-open / retry semantics ---------------------------------------------


def test_atlas_sender_fail_open_on_network_error_rebuffers():
    sender = _atlas_sender(_error_transport())
    sender.enqueue({"source": "sdk", "event_kind": "activity"})
    sender.flush_sync()  # must not raise
    assert len(sender._buffer) == 1  # network failure => kept for retry


def test_atlas_sender_rebuffers_on_http_error():
    captured: list[httpx.Request] = []
    sender = _atlas_sender(_capture_transport(captured, status_code=503, body={}))
    sender.enqueue({"source": "sdk", "event_kind": "activity"})
    sender.flush_sync()
    assert len(sender._buffer) == 1


def test_atlas_sender_does_not_rebuffer_server_skipped_rows():
    # 200 with skipped rows is FINAL: those rows failed validation and can
    # never succeed on retry. Re-buffering them would loop forever.
    captured: list[httpx.Request] = []
    sender = _atlas_sender(_capture_transport(
        captured, body=_ok_body(ingested=0, skipped=1,
                                reasons=["events[0]: prompt_hash: bad"])))
    sender.enqueue({"source": "sdk", "event_kind": "activity", "prompt_hash": "bad"})
    sender.flush_sync()
    assert len(sender._buffer) == 0


# --- chunking ----------------------------------------------------------------


def test_atlas_sender_chunks_batches_at_500():
    # The server envelope rejects >500 events; the collector sender sends the
    # whole buffer in one POST, so the atlas sender must chunk.
    captured: list[httpx.Request] = []
    sender = _atlas_sender(_capture_transport(captured))
    for i in range(ATLAS_MAX_BATCH + 1):
        sender.enqueue({"source": "sdk", "event_kind": "activity", "tokens_in": i})
    sender.flush_sync()

    assert len(captured) == 2
    sizes = [len(json.loads(r.content)["events"]) for r in captured]
    assert sizes == [500, 1]
    assert len(sender._buffer) == 0
