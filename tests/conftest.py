"""Shared test fixtures."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from kreuzberg_surrealdb.config import DatabaseConfig, IndexConfig

FIXTURES_DIR = Path(__file__).parent / "fixtures"


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
