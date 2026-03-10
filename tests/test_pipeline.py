"""Tests for DocumentPipeline."""

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from kreuzberg import Chunk, ExtractionResult
from surrealdb import RecordID

from kreuzberg_surrealdb.ingester import DocumentPipeline, _check_insert_result

# --- init ---


def test_pipeline_defaults(mock_client: AsyncMock) -> None:
    pipeline = DocumentPipeline(db=mock_client)
    assert pipeline._embed is True
    assert pipeline.chunk_table == "chunks"
    assert pipeline.embedding_dimensions == 768


def test_pipeline_custom_embedding_preset(mock_client: AsyncMock) -> None:
    pipeline = DocumentPipeline(db=mock_client, embedding_model="fast")
    assert pipeline.embedding_dimensions == 384


def test_pipeline_invalid_embedding_preset(mock_client: AsyncMock) -> None:
    with pytest.raises(ValueError, match="Unknown embedding preset"):
        DocumentPipeline(db=mock_client, embedding_model="nonexistent")


def test_pipeline_embedding_model_type_direct(mock_client: AsyncMock) -> None:
    from kreuzberg import EmbeddingModelType

    model = EmbeddingModelType.fastembed("BGEBaseENV15", 768)
    pipeline = DocumentPipeline(db=mock_client, embedding_model=model, embedding_dimensions=768)
    assert pipeline.embedding_dimensions == 768


def test_pipeline_embedding_model_type_requires_dimensions(mock_client: AsyncMock) -> None:
    from kreuzberg import EmbeddingModelType

    model = EmbeddingModelType.fastembed("BGEBaseENV15", 768)
    with pytest.raises(ValueError, match="embedding_dimensions is required"):
        DocumentPipeline(db=mock_client, embedding_model=model)


def test_pipeline_embed_false(mock_client: AsyncMock) -> None:
    pipeline = DocumentPipeline(db=mock_client, embed=False)
    assert pipeline._embed is False


def test_pipeline_custom_chunk_table(mock_client: AsyncMock) -> None:
    pipeline = DocumentPipeline(db=mock_client, chunk_table="my_chunks")
    assert pipeline.chunk_table == "my_chunks"


def test_pipeline_extraction_config_has_chunking(mock_client: AsyncMock) -> None:
    pipeline = DocumentPipeline(db=mock_client)
    assert pipeline._config is not None
    assert pipeline._config.chunking is not None


def test_pipeline_embed_true_has_embedding(mock_client: AsyncMock) -> None:
    pipeline = DocumentPipeline(db=mock_client, embed=True)
    assert pipeline._config is not None
    assert pipeline._config.chunking.embedding is not None


def test_pipeline_embed_false_no_embedding(mock_client: AsyncMock) -> None:
    pipeline = DocumentPipeline(db=mock_client, embed=False)
    assert pipeline._config is not None
    assert pipeline._config.chunking.embedding is None


def test_pipeline_user_extraction_config_gets_chunking(mock_client: AsyncMock) -> None:
    from kreuzberg import ExtractionConfig

    user_config = ExtractionConfig()
    pipeline = DocumentPipeline(db=mock_client, config=user_config)

    assert pipeline._config is user_config
    assert pipeline._config.chunking is not None
    assert pipeline._config.chunking.embedding is not None


def test_pipeline_preserves_user_chunking_params(mock_client: AsyncMock) -> None:
    from kreuzberg import ChunkingConfig, ExtractionConfig

    user_config = ExtractionConfig(
        chunking=ChunkingConfig(max_chars=512, max_overlap=100),
    )
    pipeline = DocumentPipeline(db=mock_client, config=user_config)

    assert pipeline._config is user_config
    assert pipeline._config.chunking.max_chars == 512
    assert pipeline._config.chunking.max_overlap == 100
    assert pipeline._config.chunking.embedding is not None


def test_pipeline_preserves_user_chunking_params_embed_false(mock_client: AsyncMock) -> None:
    from kreuzberg import ChunkingConfig, ExtractionConfig

    user_config = ExtractionConfig(
        chunking=ChunkingConfig(max_chars=256),
    )
    pipeline = DocumentPipeline(db=mock_client, config=user_config, embed=False)

    assert pipeline._config is not None
    assert pipeline._config.chunking is not None
    assert pipeline._config.chunking.max_chars == 256
    assert pipeline._config.chunking.embedding is None


# --- setup_schema ---


async def test_pipeline_setup_schema_creates_tables_and_indexes(
    mock_client: AsyncMock,
) -> None:
    pipeline = DocumentPipeline(db=mock_client)

    await pipeline.setup_schema()

    calls = [str(c) for c in mock_client.query.call_args_list]
    joined = " ".join(calls)
    assert "DEFINE TABLE IF NOT EXISTS documents" in joined
    assert "DEFINE TABLE IF NOT EXISTS chunks" in joined
    assert "idx_chunk_content" in joined
    assert "idx_chunk_embedding" in joined
    assert "HNSW DIMENSION 768" in joined


async def test_pipeline_setup_schema_no_hnsw_when_embed_false(
    mock_client: AsyncMock,
) -> None:
    pipeline = DocumentPipeline(db=mock_client, embed=False)

    await pipeline.setup_schema()

    calls = [str(c) for c in mock_client.query.call_args_list]
    joined = " ".join(calls)
    assert "idx_chunk_content" in joined
    assert "idx_chunk_embedding" not in joined


# --- ingestion ---


@patch("kreuzberg_surrealdb.ingester.extract_file")
async def test_pipeline_ingest_file_stores_doc_and_chunks(
    mock_extract: MagicMock,
    mock_client: AsyncMock,
    sample_extraction_result: MagicMock,
    sample_chunks: list[MagicMock],
) -> None:
    sample_extraction_result.chunks = sample_chunks
    mock_extract.return_value = sample_extraction_result

    pipeline = DocumentPipeline(db=mock_client)

    await pipeline.ingest_file("/tmp/test.pdf")

    assert mock_client.query.call_count == 2
    first_call = mock_client.query.call_args_list[0]
    assert "INSERT IGNORE INTO documents" in first_call[0][0]

    second_call = mock_client.query.call_args_list[1]
    assert "INSERT IGNORE INTO chunks" in second_call[0][0]
    chunk_records = second_call[0][1]["records"]
    assert len(chunk_records) == 3

    expected_hash = hashlib.sha256(sample_extraction_result.content.encode()).hexdigest()
    expected_rid = RecordID("documents", expected_hash)
    assert chunk_records[0]["document"] == expected_rid
    assert chunk_records[0]["chunk_index"] == 0
    assert chunk_records[1]["chunk_index"] == 1
    assert chunk_records[0]["id"] == RecordID("chunks", f"{expected_hash}_0")
    assert chunk_records[1]["id"] == RecordID("chunks", f"{expected_hash}_1")
    assert chunk_records[2]["id"] == RecordID("chunks", f"{expected_hash}_2")


@patch("kreuzberg_surrealdb.ingester.extract_file")
async def test_pipeline_ingest_idempotent_on_duplicate(
    mock_extract: MagicMock,
    mock_client: AsyncMock,
    sample_extraction_result: MagicMock,
    sample_chunks: list[MagicMock],
) -> None:
    """Duplicate ingestion uses INSERT IGNORE for both docs and chunks, making it idempotent."""
    sample_extraction_result.chunks = sample_chunks
    mock_extract.return_value = sample_extraction_result

    pipeline = DocumentPipeline(db=mock_client)

    await pipeline.ingest_file("/tmp/dup.pdf")

    # Both doc and chunk inserts should be attempted (INSERT IGNORE handles dedup)
    assert mock_client.query.call_count == 2
    first_call = mock_client.query.call_args_list[0]
    assert "INSERT IGNORE INTO documents" in first_call[0][0]
    second_call = mock_client.query.call_args_list[1]
    assert "INSERT IGNORE INTO chunks" in second_call[0][0]


@patch("kreuzberg_surrealdb.ingester.extract_file")
async def test_pipeline_embed_false_nulls_embeddings(
    mock_extract: MagicMock,
    mock_client: AsyncMock,
    sample_extraction_result: MagicMock,
    sample_chunks: list[MagicMock],
) -> None:
    sample_extraction_result.chunks = sample_chunks
    mock_extract.return_value = sample_extraction_result

    pipeline = DocumentPipeline(db=mock_client, embed=False)

    await pipeline.ingest_file("/tmp/test.pdf")

    chunk_call = mock_client.query.call_args_list[1]
    chunk_records = chunk_call[0][1]["records"]
    for rec in chunk_records:
        assert rec["embedding"] is None


@patch("kreuzberg_surrealdb.ingester.extract_file")
async def test_pipeline_chunk_metadata_extracted(
    mock_extract: MagicMock,
    mock_client: AsyncMock,
    sample_extraction_result: MagicMock,
    sample_chunks: list[MagicMock],
) -> None:
    sample_extraction_result.chunks = sample_chunks
    mock_extract.return_value = sample_extraction_result

    pipeline = DocumentPipeline(db=mock_client)

    await pipeline.ingest_file("/tmp/test.pdf")

    chunk_call = mock_client.query.call_args_list[1]
    chunk_records = chunk_call[0][1]["records"]
    first_chunk = chunk_records[0]
    assert first_chunk["page_number"] == 1
    assert first_chunk["char_start"] == 0
    assert first_chunk["char_end"] == 100
    assert first_chunk["first_page"] == 1
    assert first_chunk["last_page"] == 1
    assert "token_count" in first_chunk


@patch("kreuzberg_surrealdb.ingester.extract_bytes")
async def test_pipeline_ingest_bytes(
    mock_extract: MagicMock,
    mock_client: AsyncMock,
    sample_extraction_result: MagicMock,
) -> None:
    sample_extraction_result.chunks = []
    mock_extract.return_value = sample_extraction_result

    mock_client.query = AsyncMock(return_value=[{"id": "doc"}])

    pipeline = DocumentPipeline(db=mock_client)

    await pipeline.ingest_bytes(data=b"data", mime_type="text/plain", source="test://source")

    mock_extract.assert_called_once()
    assert mock_extract.call_args[0][0] == b"data"
    assert mock_extract.call_args[0][1] == "text/plain"


# --- _check_insert_result ---


def test_check_insert_result_passes_on_normal_results() -> None:
    _check_insert_result([], context="test")
    _check_insert_result([{"id": "rec:1"}], context="test")
    _check_insert_result(None, context="test")


def test_check_insert_result_raises_on_dimension_error() -> None:
    result = ["Expected a vector of 768 dimensions, but got 384"]
    with pytest.raises(RuntimeError, match="Vector dimension mismatch"):
        _check_insert_result(result, context="chunk insertion")


def test_check_insert_result_raises_on_generic_string_error() -> None:
    result = ["Some unexpected SurrealDB error"]
    with pytest.raises(RuntimeError, match="INSERT IGNORE failed silently"):
        _check_insert_result(result, context="test")


@patch("kreuzberg_surrealdb.ingester.extract_file")
async def test_pipeline_raises_on_chunk_dimension_mismatch(
    mock_extract: MagicMock,
    mock_client: AsyncMock,
    sample_extraction_result: MagicMock,
    sample_chunks: list[MagicMock],
) -> None:
    sample_extraction_result.chunks = sample_chunks
    mock_extract.return_value = sample_extraction_result

    # Doc insert succeeds, chunk insert returns a dimension error string
    mock_client.query = AsyncMock(
        side_effect=[
            [],
            ["Expected a vector of 768 dimensions, but got 384"],
        ]
    )

    pipeline = DocumentPipeline(db=mock_client)

    with pytest.raises(RuntimeError, match="Vector dimension mismatch during chunk insertion"):
        await pipeline.ingest_file("/tmp/test.pdf")


# --- embed_query ---


@patch("kreuzberg_surrealdb.ingester.extract_bytes")
async def test_embed_query_uses_kreuzberg(mock_extract: MagicMock, mock_client: AsyncMock) -> None:
    mock_chunk = MagicMock(spec=Chunk)
    mock_chunk.embedding = [0.1, 0.2, 0.3]
    mock_result = MagicMock(spec=ExtractionResult)
    mock_result.chunks = [mock_chunk]
    mock_extract.return_value = mock_result

    pipeline = DocumentPipeline(db=mock_client, embed=True)

    result = await pipeline.embed_query("test query")

    mock_extract.assert_called_once_with(b"test query", "text/plain", config=pipeline._config)
    assert result == [0.1, 0.2, 0.3]


@patch("kreuzberg_surrealdb.ingester.extract_bytes")
async def test_embed_query_raises_on_empty_chunks(mock_extract: MagicMock, mock_client: AsyncMock) -> None:
    mock_result = MagicMock(spec=ExtractionResult)
    mock_result.chunks = []
    mock_extract.return_value = mock_result

    pipeline = DocumentPipeline(db=mock_client, embed=True)

    with pytest.raises(RuntimeError, match="Embedding generation failed"):
        await pipeline.embed_query("test query")


@patch("kreuzberg_surrealdb.ingester.extract_bytes")
async def test_embed_query_raises_on_none_embedding(mock_extract: MagicMock, mock_client: AsyncMock) -> None:
    mock_chunk = MagicMock(spec=Chunk)
    mock_chunk.embedding = None
    mock_result = MagicMock(spec=ExtractionResult)
    mock_result.chunks = [mock_chunk]
    mock_extract.return_value = mock_result

    pipeline = DocumentPipeline(db=mock_client, embed=True)

    with pytest.raises(RuntimeError, match="Embedding generation failed"):
        await pipeline.embed_query("test query")
