"""Shared test fixtures."""

import os
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from kreuzberg_surrealdb.config import DatabaseConfig, IndexConfig


def _find_ort_dylib() -> str | None:
    """Auto-detect libonnxruntime.so from the onnxruntime package."""
    try:
        import onnxruntime  # type: ignore[import-untyped]

        capi_dir = Path(onnxruntime.__file__).parent / "capi"
        for entry in capi_dir.iterdir():
            if entry.name.startswith("libonnxruntime.so.") and not entry.name.endswith("_providers_shared.so"):
                return str(entry)
    except (ImportError, FileNotFoundError):
        pass
    return None


def _can_embed() -> bool:
    """Check if kreuzberg can generate embeddings (needs ORT_DYLIB_PATH)."""
    if "ORT_DYLIB_PATH" not in os.environ:
        path = _find_ort_dylib()
        if path:
            os.environ["ORT_DYLIB_PATH"] = path
        else:
            return False
    return True


# Set ORT_DYLIB_PATH early so kreuzberg's Rust extension can find ONNX Runtime
_can_embed()


@pytest.fixture
def db_config() -> DatabaseConfig:
    return DatabaseConfig(db_url="mem://", namespace="test", database="test")


@pytest.fixture
def index_config() -> IndexConfig:
    return IndexConfig()


@pytest.fixture
def mock_client() -> AsyncMock:
    """Mock AsyncSurreal connection."""
    client = AsyncMock()
    client.connect = AsyncMock()
    client.close = AsyncMock()
    client.signin = AsyncMock()
    client.use = AsyncMock()
    client.query = AsyncMock(return_value=[])
    return client


@pytest.fixture
def sample_extraction_result() -> MagicMock:
    """A mock ExtractionResult with typical fields populated."""
    result = MagicMock()
    result.content = "This is the extracted document content."
    result.mime_type = "text/plain"
    result.metadata = {"title": "Test Document", "authors": ["Alice", "Bob"]}
    result.quality_score = 0.95
    result.detected_languages = [{"language": "en", "confidence": 0.99}]
    result.extracted_keywords = [{"keyword": "test", "score": 0.8}]
    result.chunks = []
    return result


@pytest.fixture
def sample_chunks() -> list[MagicMock]:
    """Mock chunks with embeddings and metadata."""
    chunks = []
    for i in range(3):
        chunk = MagicMock()
        chunk.content = f"Chunk {i} content about testing."
        chunk.embedding = [0.1 * i] * 768
        chunk.metadata = {
            "page_number": i + 1,
            "char_start": i * 100,
            "char_end": (i + 1) * 100,
            "first_page": i + 1,
            "last_page": i + 1,
        }
        chunks.append(chunk)
    return chunks


def make_query_result(records: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Wrap records in the format SurrealDB query() returns."""
    return [records]
