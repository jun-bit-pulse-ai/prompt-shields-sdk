"""Tests for pgvector semantic search functionality."""
import pytest
from collector.embeddings import build_asset_text, mock_embedding, EMBEDDING_DIM


def test_build_asset_text():
    text = build_asset_text(
        vendor="openai",
        model="gpt-4o",
        use_case_name="screening",
        business_unit="HR",
        data_classification="confidential",
    )
    assert "openai" in text
    assert "gpt-4o" in text
    assert "screening" in text
    assert "HR" in text
    assert "confidential" in text


def test_build_asset_text_minimal():
    text = build_asset_text(vendor="openai", model=None, use_case_name=None,
                            business_unit=None, data_classification=None)
    assert text == "AI vendor: openai"


def test_mock_embedding_dimensions():
    emb = mock_embedding("test query")
    assert len(emb) == EMBEDDING_DIM
    assert all(isinstance(v, float) for v in emb)


def test_mock_embedding_deterministic():
    emb1 = mock_embedding("same input")
    emb2 = mock_embedding("same input")
    assert emb1 == emb2


def test_mock_embedding_different_inputs():
    emb1 = mock_embedding("input A")
    emb2 = mock_embedding("input B")
    assert emb1 != emb2
