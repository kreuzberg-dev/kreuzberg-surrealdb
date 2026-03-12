"""Tests for DocumentConnector."""

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from kreuzberg import ExtractionConfig

from kreuzberg_surrealdb.connector import DocumentConnector
from kreuzberg_surrealdb.exceptions import IngestionError, SchemaNotInitializedError


def test_analyzer_name(mock_client: AsyncMock) -> None:
    connector = DocumentConnector(db=mock_client)
    assert connector.analyzer_name == "doc_analyzer"


def test_client_property(mock_client: AsyncMock) -> None:
    connector = DocumentConnector(db=mock_client)
    assert connector.client is mock_client


def test_table_property(mock_client: AsyncMock) -> None:
    connector = DocumentConnector(db=mock_client, table="my_docs")
    assert connector.table == "my_docs"


@patch("kreuzberg_surrealdb._base.extract_file")
async def test_ingest_file(
    mock_extract: MagicMock,
    mock_client: AsyncMock,
    sample_extraction_result: MagicMock,
) -> None:
    mock_extract.return_value = sample_extraction_result

    connector = DocumentConnector(db=mock_client)
    connector._schema_ready = True

    await connector.ingest_file("/tmp/test.pdf")

    mock_extract.assert_called_once_with("/tmp/test.pdf", config=None)
    mock_client.query.assert_called_once()
    call_args = mock_client.query.call_args
    assert "INSERT IGNORE INTO documents" in call_args[0][0]
    records = call_args[0][1]["records"]
    assert records[0]["source"] == "/tmp/test.pdf"
    assert records[0]["content"] == sample_extraction_result.content


@patch("kreuzberg_surrealdb._base.extract_file")
async def test_ingest_file_passes_custom_config(
    mock_extract: MagicMock,
    mock_client: AsyncMock,
    sample_extraction_result: MagicMock,
) -> None:
    mock_extract.return_value = sample_extraction_result
    user_config = ExtractionConfig()

    connector = DocumentConnector(db=mock_client, config=user_config)
    connector._schema_ready = True

    await connector.ingest_file("/tmp/test.pdf")

    mock_extract.assert_called_once_with("/tmp/test.pdf", config=user_config)


@patch("kreuzberg_surrealdb._base.extract_bytes")
async def test_ingest_bytes(
    mock_extract: MagicMock,
    mock_client: AsyncMock,
    sample_extraction_result: MagicMock,
) -> None:
    mock_extract.return_value = sample_extraction_result

    connector = DocumentConnector(db=mock_client)
    connector._schema_ready = True

    await connector.ingest_bytes(data=b"hello world", mime_type="text/plain", source="api://response")

    mock_extract.assert_called_once_with(b"hello world", "text/plain", config=None)
    records = mock_client.query.call_args[0][1]["records"]
    assert records[0]["source"] == "api://response"


@patch("kreuzberg_surrealdb._base.extract_file")
async def test_content_hash_computed(
    mock_extract: MagicMock,
    mock_client: AsyncMock,
    sample_extraction_result: MagicMock,
) -> None:
    mock_extract.return_value = sample_extraction_result

    connector = DocumentConnector(db=mock_client)
    connector._schema_ready = True

    await connector.ingest_file("/tmp/test.txt")

    records = mock_client.query.call_args[0][1]["records"]
    expected_hash = hashlib.sha256(sample_extraction_result.content.encode()).hexdigest()
    assert records[0]["content_hash"] == expected_hash


@patch("kreuzberg_surrealdb._base.extract_file")
async def test_metadata_fields_mapped(
    mock_extract: MagicMock,
    mock_client: AsyncMock,
    sample_extraction_result: MagicMock,
) -> None:
    mock_extract.return_value = sample_extraction_result

    connector = DocumentConnector(db=mock_client)
    connector._schema_ready = True

    await connector.ingest_file("/tmp/test.txt")

    records = mock_client.query.call_args[0][1]["records"]
    doc = records[0]
    assert doc["title"] == "Test Document"
    assert doc["authors"] == ["Alice", "Bob"]
    assert doc["quality_score"] == 0.95
    assert doc["detected_languages"] == [{"language": "en", "confidence": 0.99}]
    assert doc["keywords"] == [{"keyword": "test", "score": 0.8}]


@patch("kreuzberg_surrealdb._base.extract_file")
async def test_connector_raises_on_silent_insert_error(
    mock_extract: MagicMock,
    mock_client: AsyncMock,
    sample_extraction_result: MagicMock,
) -> None:
    mock_extract.return_value = sample_extraction_result
    mock_client.query = AsyncMock(return_value=["Some unexpected database error"])

    connector = DocumentConnector(db=mock_client)
    connector._schema_ready = True

    with pytest.raises(IngestionError, match="INSERT IGNORE failed silently"):
        await connector.ingest_file("/tmp/test.pdf")


@pytest.mark.parametrize(
    "method,args,kwargs",
    [
        ("ingest_file", ["/tmp/test.pdf"], {}),
        ("ingest_files", [["/tmp/a.pdf", "/tmp/b.pdf"]], {}),
        ("ingest_directory", ["/tmp"], {}),
        ("ingest_bytes", [], {"data": b"hello", "mime_type": "text/plain", "source": "test"}),
    ],
    ids=["ingest_file", "ingest_files", "ingest_directory", "ingest_bytes"],
)
async def test_connector_raises_without_schema(
    mock_client: AsyncMock,
    method: str,
    args: list,
    kwargs: dict,
) -> None:
    connector = DocumentConnector(db=mock_client)

    with pytest.raises(SchemaNotInitializedError, match="setup_schema"):
        await getattr(connector, method)(*args, **kwargs)
