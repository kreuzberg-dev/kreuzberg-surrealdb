"""Tests for DocumentConnector."""
import hashlib
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kreuzberg_surrealdb.config import DatabaseConfig
from kreuzberg_surrealdb.ingester import DocumentConnector, _BaseIngester

# --- setup_schema ---


async def test_setup_schema_executes_all_statements(db_config: DatabaseConfig, mock_client: AsyncMock) -> None:
    connector = DocumentConnector(db=db_config)
    connector._client = mock_client

    await connector.setup_schema()

    assert mock_client.query.call_count > 0
    calls = [str(c) for c in mock_client.query.call_args_list]
    joined = " ".join(calls)
    assert "DEFINE TABLE" in joined
    assert "idx_doc_content" in joined
    assert "BM25" in joined


# --- ingestion ---


@patch("kreuzberg_surrealdb.ingester.extract_file")
async def test_ingest_file(
    mock_extract: MagicMock, db_config: DatabaseConfig, mock_client: AsyncMock, sample_extraction_result: MagicMock,
) -> None:
    mock_extract.return_value = sample_extraction_result
    mock_client.query = AsyncMock(return_value=[])

    connector = DocumentConnector(db=db_config)
    connector._client = mock_client

    await connector.ingest_file("/tmp/test.pdf")

    mock_extract.assert_called_once_with("/tmp/test.pdf", config=None)
    mock_client.query.assert_called_once()
    call_args = mock_client.query.call_args
    assert "INSERT IGNORE INTO documents" in call_args[0][0]
    records = call_args[1]["records"] if "records" in call_args[1] else call_args[0][1]["records"]
    assert records[0]["source"] == "/tmp/test.pdf"
    assert records[0]["content"] == sample_extraction_result.content


@patch("kreuzberg_surrealdb.ingester.extract_file")
async def test_ingest_files(
    mock_extract: MagicMock, db_config: DatabaseConfig, mock_client: AsyncMock, sample_extraction_result: MagicMock,
) -> None:
    mock_extract.return_value = sample_extraction_result
    mock_client.query = AsyncMock(return_value=[])

    connector = DocumentConnector(db=db_config)
    connector._client = mock_client

    await connector.ingest_files(["/tmp/a.pdf", "/tmp/b.pdf"])

    assert mock_extract.call_count == 2
    assert mock_client.query.call_count == 2


@patch("kreuzberg_surrealdb.ingester.extract_bytes")
async def test_ingest_bytes(
    mock_extract: MagicMock, db_config: DatabaseConfig, mock_client: AsyncMock, sample_extraction_result: MagicMock,
) -> None:
    mock_extract.return_value = sample_extraction_result
    mock_client.query = AsyncMock(return_value=[])

    connector = DocumentConnector(db=db_config)
    connector._client = mock_client

    await connector.ingest_bytes(b"hello world", "text/plain", "api://response")

    mock_extract.assert_called_once_with(b"hello world", "text/plain", config=None)
    call_args = mock_client.query.call_args
    records = call_args[1]["records"] if "records" in call_args[1] else call_args[0][1]["records"]
    assert records[0]["source"] == "api://response"


@patch("kreuzberg_surrealdb.ingester.extract_file")
async def test_content_hash_computed(
    mock_extract: MagicMock, db_config: DatabaseConfig, mock_client: AsyncMock, sample_extraction_result: MagicMock,
) -> None:
    mock_extract.return_value = sample_extraction_result
    mock_client.query = AsyncMock(return_value=[])

    connector = DocumentConnector(db=db_config)
    connector._client = mock_client

    await connector.ingest_file("/tmp/test.txt")

    call_args = mock_client.query.call_args
    records = call_args[1]["records"] if "records" in call_args[1] else call_args[0][1]["records"]
    expected_hash = hashlib.sha256(sample_extraction_result.content.encode()).hexdigest()
    assert records[0]["content_hash"] == expected_hash


@patch("kreuzberg_surrealdb.ingester.extract_file")
async def test_metadata_fields_mapped(
    mock_extract: MagicMock, db_config: DatabaseConfig, mock_client: AsyncMock, sample_extraction_result: MagicMock,
) -> None:
    mock_extract.return_value = sample_extraction_result
    mock_client.query = AsyncMock(return_value=[])

    connector = DocumentConnector(db=db_config)
    connector._client = mock_client

    await connector.ingest_file("/tmp/test.txt")

    call_args = mock_client.query.call_args
    records = call_args[1]["records"] if "records" in call_args[1] else call_args[0][1]["records"]
    doc = records[0]
    assert doc["title"] == "Test Document"
    assert doc["authors"] == ["Alice", "Bob"]
    assert doc["quality_score"] == 0.95
    assert doc["detected_languages"] == [{"language": "en", "confidence": 0.99}]
    assert doc["keywords"] == [{"keyword": "test", "score": 0.8}]


# --- search ---


async def test_search_delegates_to_fulltext(db_config: DatabaseConfig, mock_client: AsyncMock) -> None:
    expected = [{"content": "result", "score": 1.0}]
    mock_client.query = AsyncMock(return_value=expected)

    connector = DocumentConnector(db=db_config)
    connector._client = mock_client

    result = await connector.search("test query", limit=5)

    assert result == expected
    call_args = mock_client.query.call_args
    query_str = call_args[0][0]
    assert "documents" in query_str
    assert "@1@" in query_str
    params = call_args[0][1] if len(call_args[0]) > 1 else call_args[1]
    assert params["query"] == "test query"
    assert params["limit"] == 5


# --- connection lifecycle ---


@patch("kreuzberg_surrealdb.ingester.AsyncSurreal")
async def test_connect_and_close(mock_surreal_factory: MagicMock, db_config: DatabaseConfig) -> None:
    mock_conn = AsyncMock()
    mock_surreal_factory.return_value = mock_conn

    connector = DocumentConnector(db=db_config)
    await connector.connect()

    mock_surreal_factory.assert_called_once_with(url="mem://")
    mock_conn.connect.assert_called_once()
    mock_conn.use.assert_called_once_with("test", "test")

    await connector.close()
    mock_conn.close.assert_called_once()


@patch("kreuzberg_surrealdb.ingester.AsyncSurreal")
async def test_connect_with_auth(mock_surreal_factory: MagicMock) -> None:
    mock_conn = AsyncMock()
    mock_surreal_factory.return_value = mock_conn

    cfg = DatabaseConfig(db_url="ws://localhost:8000", username="root", password="root")
    connector = DocumentConnector(db=cfg)
    await connector.connect()

    mock_conn.signin.assert_called_once_with({"username": "root", "password": "root"})


@patch("kreuzberg_surrealdb.ingester.AsyncSurreal")
async def test_context_manager(mock_surreal_factory: MagicMock, db_config: DatabaseConfig) -> None:
    mock_conn = AsyncMock()
    mock_surreal_factory.return_value = mock_conn

    async with DocumentConnector(db=db_config) as connector:
        assert connector._client is not None

    mock_conn.close.assert_called_once()


# --- base class ---


async def test_base_ingester_setup_schema_raises(db_config: DatabaseConfig) -> None:
    base = _BaseIngester(db=db_config)
    with pytest.raises(NotImplementedError):
        await base.setup_schema()


# --- ingest_directory ---


@patch("kreuzberg_surrealdb.ingester.extract_file")
async def test_ingest_directory(
    mock_extract: MagicMock,
    db_config: DatabaseConfig,
    mock_client: AsyncMock,
    sample_extraction_result: MagicMock,
    tmp_path: Path,
) -> None:
    (tmp_path / "a.txt").write_text("hello")
    (tmp_path / "b.txt").write_text("world")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "c.txt").write_text("nested")

    mock_extract.return_value = sample_extraction_result
    mock_client.query = AsyncMock(return_value=[])

    connector = DocumentConnector(db=db_config)
    connector._client = mock_client

    await connector.ingest_directory(tmp_path, glob="**/*.txt")

    assert mock_extract.call_count == 3
