"""Tests for DocumentConnector."""

import hashlib
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kreuzberg_surrealdb.ingester import DocumentConnector


async def test_setup_schema_executes_all_statements(mock_client: AsyncMock) -> None:
    connector = DocumentConnector(db=mock_client)

    await connector.setup_schema()

    assert mock_client.query.call_count > 0
    calls = [str(c) for c in mock_client.query.call_args_list]
    joined = " ".join(calls)
    assert "DEFINE TABLE" in joined
    assert "idx_doc_content" in joined
    assert "BM25" in joined


@patch("kreuzberg_surrealdb.ingester.extract_file")
async def test_ingest_file(
    mock_extract: MagicMock,
    mock_client: AsyncMock,
    sample_extraction_result: MagicMock,
) -> None:
    mock_extract.return_value = sample_extraction_result

    connector = DocumentConnector(db=mock_client)

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
    mock_extract: MagicMock,
    mock_client: AsyncMock,
    sample_extraction_result: MagicMock,
) -> None:
    mock_extract.return_value = sample_extraction_result

    connector = DocumentConnector(db=mock_client)

    await connector.ingest_files(["/tmp/a.pdf", "/tmp/b.pdf"])

    assert mock_extract.call_count == 2
    assert mock_client.query.call_count == 2


@patch("kreuzberg_surrealdb.ingester.extract_bytes")
async def test_ingest_bytes(
    mock_extract: MagicMock,
    mock_client: AsyncMock,
    sample_extraction_result: MagicMock,
) -> None:
    mock_extract.return_value = sample_extraction_result

    connector = DocumentConnector(db=mock_client)

    await connector.ingest_bytes(data=b"hello world", mime_type="text/plain", source="api://response")

    mock_extract.assert_called_once_with(b"hello world", "text/plain", config=None)
    call_args = mock_client.query.call_args
    records = call_args[1]["records"] if "records" in call_args[1] else call_args[0][1]["records"]
    assert records[0]["source"] == "api://response"


@patch("kreuzberg_surrealdb.ingester.extract_file")
async def test_content_hash_computed(
    mock_extract: MagicMock,
    mock_client: AsyncMock,
    sample_extraction_result: MagicMock,
) -> None:
    mock_extract.return_value = sample_extraction_result

    connector = DocumentConnector(db=mock_client)

    await connector.ingest_file("/tmp/test.txt")

    call_args = mock_client.query.call_args
    records = call_args[1]["records"] if "records" in call_args[1] else call_args[0][1]["records"]
    expected_hash = hashlib.sha256(sample_extraction_result.content.encode()).hexdigest()
    assert records[0]["content_hash"] == expected_hash


@patch("kreuzberg_surrealdb.ingester.extract_file")
async def test_metadata_fields_mapped(
    mock_extract: MagicMock,
    mock_client: AsyncMock,
    sample_extraction_result: MagicMock,
) -> None:
    mock_extract.return_value = sample_extraction_result

    connector = DocumentConnector(db=mock_client)

    await connector.ingest_file("/tmp/test.txt")

    call_args = mock_client.query.call_args
    records = call_args[1]["records"] if "records" in call_args[1] else call_args[0][1]["records"]
    doc = records[0]
    assert doc["title"] == "Test Document"
    assert doc["authors"] == ["Alice", "Bob"]
    assert doc["quality_score"] == 0.95
    assert doc["detected_languages"] == [{"language": "en", "confidence": 0.99}]
    assert doc["keywords"] == [{"keyword": "test", "score": 0.8}]



@patch("kreuzberg_surrealdb.ingester.extract_file")
async def test_connector_raises_on_silent_insert_error(
    mock_extract: MagicMock,
    mock_client: AsyncMock,
    sample_extraction_result: MagicMock,
) -> None:
    mock_extract.return_value = sample_extraction_result
    mock_client.query = AsyncMock(return_value=["Some unexpected database error"])

    connector = DocumentConnector(db=mock_client)

    with pytest.raises(RuntimeError, match="INSERT IGNORE failed silently"):
        await connector.ingest_file("/tmp/test.pdf")


@patch("kreuzberg_surrealdb.ingester.extract_file")
async def test_ingest_directory(
    mock_extract: MagicMock,
    mock_client: AsyncMock,
    sample_extraction_result: MagicMock,
    tmp_path: Path,
) -> None:
    (tmp_path / "a.txt").write_text("hello")
    (tmp_path / "b.txt").write_text("world")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "c.txt").write_text("nested")

    mock_extract.return_value = sample_extraction_result

    connector = DocumentConnector(db=mock_client)

    await connector.ingest_directory(tmp_path, glob="**/*.txt")

    assert mock_extract.call_count == 3
