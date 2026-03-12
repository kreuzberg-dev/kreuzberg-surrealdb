"""Tests for DocumentPipeline."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from kreuzberg import Chunk, ExtractionResult

from kreuzberg_surrealdb._base import _check_insert_result
from kreuzberg_surrealdb.exceptions import DimensionMismatchError, IngestionError, SchemaNotInitializedError
from kreuzberg_surrealdb.pipeline import DocumentPipeline


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


@patch("kreuzberg_surrealdb._base.extract_file")
async def test_pipeline_chunk_without_metadata(
    mock_extract: MagicMock,
    mock_client: AsyncMock,
    sample_extraction_result: MagicMock,
) -> None:
    """Chunks with None metadata should set page_number/char_start/etc to None."""
    chunk = MagicMock(spec=Chunk)
    chunk.content = "Chunk without metadata."
    chunk.embedding = [0.1] * 768
    chunk.metadata = None

    sample_extraction_result.chunks = [chunk]
    mock_extract.return_value = sample_extraction_result

    pipeline = DocumentPipeline(db=mock_client)
    pipeline._schema_ready = True

    await pipeline.ingest_file("/tmp/test.pdf")

    chunk_call = mock_client.query.call_args_list[1]
    chunk_records = chunk_call[0][1]["records"]
    rec = chunk_records[0]
    assert rec["page_number"] is None
    assert rec["char_start"] is None
    assert rec["char_end"] is None
    assert rec["first_page"] is None
    assert rec["last_page"] is None
    assert rec["content"] == "Chunk without metadata."
    assert rec["chunk_index"] == 0


@patch("kreuzberg_surrealdb._base.extract_file")
async def test_pipeline_ingest_file_no_chunks_skips_chunk_insert(
    mock_extract: MagicMock,
    mock_client: AsyncMock,
    sample_extraction_result: MagicMock,
) -> None:
    sample_extraction_result.chunks = []
    mock_extract.return_value = sample_extraction_result

    pipeline = DocumentPipeline(db=mock_client)
    pipeline._schema_ready = True

    await pipeline.ingest_file("/tmp/test.pdf")

    assert mock_client.query.call_count == 1
    assert "INSERT IGNORE INTO documents" in mock_client.query.call_args[0][0]


@patch("kreuzberg_surrealdb._base.extract_file")
async def test_pipeline_chunk_batch_splitting(
    mock_extract: MagicMock,
    mock_client: AsyncMock,
    sample_extraction_result: MagicMock,
    sample_chunks: list[MagicMock],
) -> None:
    """With insert_batch_size=2 and 3 chunks, chunks should be split into 2 INSERT queries."""
    sample_extraction_result.chunks = sample_chunks
    mock_extract.return_value = sample_extraction_result

    pipeline = DocumentPipeline(db=mock_client, insert_batch_size=2)
    pipeline._schema_ready = True

    await pipeline.ingest_file("/tmp/test.pdf")

    assert mock_client.query.call_count == 3
    chunk_call_1 = mock_client.query.call_args_list[1]
    chunk_call_2 = mock_client.query.call_args_list[2]
    assert len(chunk_call_1[0][1]["records"]) == 2
    assert len(chunk_call_2[0][1]["records"]) == 1


def test_check_insert_result_passes_on_normal_results() -> None:
    _check_insert_result([], context="test")
    _check_insert_result([{"id": "rec:1"}], context="test")
    _check_insert_result(None, context="test")


def test_check_insert_result_raises_on_dimension_error() -> None:
    result = ["Expected a vector of 768 dimensions, but got 384"]
    with pytest.raises(DimensionMismatchError, match="Vector dimension mismatch"):
        _check_insert_result(result, context="chunk insertion")


def test_check_insert_result_raises_on_generic_string_error() -> None:
    result = ["Some unexpected SurrealDB error"]
    with pytest.raises(IngestionError, match="INSERT IGNORE failed silently"):
        _check_insert_result(result, context="test")


@patch("kreuzberg_surrealdb._base.extract_file")
async def test_pipeline_raises_on_chunk_dimension_mismatch(
    mock_extract: MagicMock,
    mock_client: AsyncMock,
    sample_extraction_result: MagicMock,
    sample_chunks: list[MagicMock],
) -> None:
    sample_extraction_result.chunks = sample_chunks
    mock_extract.return_value = sample_extraction_result

    mock_client.query = AsyncMock(
        side_effect=[
            [],
            ["Expected a vector of 768 dimensions, but got 384"],
        ]
    )

    pipeline = DocumentPipeline(db=mock_client)
    pipeline._schema_ready = True

    with pytest.raises(DimensionMismatchError, match="Vector dimension mismatch during chunk insertion"):
        await pipeline.ingest_file("/tmp/test.pdf")


@patch("kreuzberg_surrealdb.pipeline.extract_bytes")
async def test_embed_query_raises_on_empty_chunks(mock_extract: MagicMock, mock_client: AsyncMock) -> None:
    mock_result = MagicMock(spec=ExtractionResult)
    mock_result.chunks = []
    mock_extract.return_value = mock_result

    pipeline = DocumentPipeline(db=mock_client, embed=True)

    with pytest.raises(RuntimeError, match="Embedding generation failed"):
        await pipeline.embed_query("test query")


@patch("kreuzberg_surrealdb.pipeline.extract_bytes")
async def test_embed_query_raises_on_none_embedding(mock_extract: MagicMock, mock_client: AsyncMock) -> None:
    mock_chunk = MagicMock(spec=Chunk)
    mock_chunk.embedding = None
    mock_result = MagicMock(spec=ExtractionResult)
    mock_result.chunks = [mock_chunk]
    mock_extract.return_value = mock_result

    pipeline = DocumentPipeline(db=mock_client, embed=True)

    with pytest.raises(RuntimeError, match="Embedding generation failed"):
        await pipeline.embed_query("test query")


async def test_fast_preset_produces_384_dim_embeddings(mock_client: AsyncMock, tmp_path: Path) -> None:
    """Verify the 'fast' preset produces 384-dim embeddings via real kreuzberg extraction."""
    from kreuzberg import extract_file

    sample = tmp_path / "sample.txt"
    sample.write_text("Machine learning is a subset of artificial intelligence.")

    pipeline = DocumentPipeline(db=mock_client, embed=True, embedding_model="fast")
    result = await extract_file(str(sample), config=pipeline._config)

    assert len(result.chunks) > 0
    for chunk in result.chunks:
        assert chunk.embedding is not None
        assert len(chunk.embedding) == 384


async def test_fast_preset_embed_query_produces_384_dim(mock_client: AsyncMock) -> None:
    """Verify the 'fast' preset can embed a query string with correct dimensions."""
    from kreuzberg import extract_bytes

    pipeline = DocumentPipeline(db=mock_client, embed=True, embedding_model="fast")
    result = await extract_bytes(b"machine learning", "text/plain", config=pipeline._config)

    assert len(result.chunks) > 0
    assert result.chunks[0].embedding is not None
    assert len(result.chunks[0].embedding) == 384


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
async def test_pipeline_raises_without_schema(
    mock_client: AsyncMock,
    method: str,
    args: list,
    kwargs: dict,
) -> None:
    pipeline = DocumentPipeline(db=mock_client, embed=False)

    with pytest.raises(SchemaNotInitializedError, match="setup_schema"):
        await getattr(pipeline, method)(*args, **kwargs)
