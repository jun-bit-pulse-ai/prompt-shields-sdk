"""Generate embeddings for AI asset descriptions using OpenAI."""
import os
import hashlib
import logging
from typing import Optional
import httpx

logger = logging.getLogger("prompt_shields.embeddings")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536


def build_asset_text(
    vendor: str,
    model: str | None,
    use_case_name: str | None,
    business_unit: str | None,
    data_classification: str | None,
) -> str:
    """Build a descriptive text string from asset metadata for embedding."""
    parts = [f"AI vendor: {vendor}"]
    if model:
        parts.append(f"model: {model}")
    if use_case_name:
        parts.append(f"use case: {use_case_name}")
    if business_unit:
        parts.append(f"business unit: {business_unit}")
    if data_classification:
        parts.append(f"data classification: {data_classification}")
    return ", ".join(parts)


async def get_embedding(text: str) -> Optional[list[float]]:
    """Get embedding vector from OpenAI. Returns None if API key not set or call fails."""
    if not OPENAI_API_KEY:
        logger.debug("No OPENAI_API_KEY set, skipping embedding generation")
        return None

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": EMBEDDING_MODEL,
                    "input": text,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                return data["data"][0]["embedding"]
            else:
                logger.warning(f"Embedding API returned {resp.status_code}")
                return None
    except Exception as e:
        logger.warning(f"Embedding generation failed: {e}")
        return None


def mock_embedding(text: str) -> list[float]:
    """Generate a deterministic mock embedding for testing (no API key needed)."""
    h = hashlib.sha256(text.encode()).hexdigest()
    # Generate 1536 floats from hash bytes, cycling through
    values = []
    for i in range(EMBEDDING_DIM):
        byte_idx = i % 32
        values.append((int(h[byte_idx * 2: byte_idx * 2 + 2], 16) - 128) / 128.0)
    return values
