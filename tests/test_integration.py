"""Integration tests requiring a live SurrealDB instance.

Run with: uv run pytest tests/test_integration.py -v -m integration
Uses mem:// (embedded SurrealDB) for local testing — no external server needed.
"""
from pathlib import Path

import pytest

from kreuzberg_surrealdb.config import DatabaseConfig
from kreuzberg_surrealdb.ingester import DocumentConnector, DocumentPipeline

pytestmark = pytest.mark.integration


@pytest.fixture
def mem_db_config() -> DatabaseConfig:
    return DatabaseConfig(db_url="mem://", namespace="test", database="test")


@pytest.fixture
def sample_text_file(tmp_path: Path) -> Path:
    f = tmp_path / "sample.txt"
    f.write_text(
        "Machine learning is a subset of artificial intelligence. "
        "It involves training algorithms on data to make predictions. "
        "Deep learning is a subset of machine learning that uses neural networks."
    )
    return f


@pytest.fixture
def second_text_file(tmp_path: Path) -> Path:
    f = tmp_path / "second.txt"
    f.write_text(
        "SurrealDB is a multi-model database that supports SQL-like queries. "
        "It provides graph, document, and relational features in a single platform."
    )
    return f


# --- DocumentConnector ---


async def test_connector_full_roundtrip(mem_db_config: DatabaseConfig, sample_text_file: Path) -> None:
    async with DocumentConnector(db=mem_db_config) as connector:
        await connector.setup_schema()
        await connector.ingest_file(sample_text_file)

        results = await connector.search("machine learning", limit=5)
        assert len(results) > 0


async def test_connector_ingest_multiple_files(
    mem_db_config: DatabaseConfig, sample_text_file: Path, second_text_file: Path,
) -> None:
    async with DocumentConnector(db=mem_db_config) as connector:
        await connector.setup_schema()
        await connector.ingest_files([sample_text_file, second_text_file])

        results = await connector.search("database", limit=10)
        assert len(results) > 0


async def test_connector_dedup_same_content(mem_db_config: DatabaseConfig, sample_text_file: Path) -> None:
    async with DocumentConnector(db=mem_db_config) as connector:
        await connector.setup_schema()
        await connector.ingest_file(sample_text_file)
        await connector.ingest_file(sample_text_file)

        all_docs = await connector._client.query(f"SELECT * FROM {mem_db_config.table}")
        assert len(all_docs) == 1


async def test_connector_ingest_bytes(mem_db_config: DatabaseConfig) -> None:
    async with DocumentConnector(db=mem_db_config) as connector:
        await connector.setup_schema()
        content = b"Python is a programming language used for web development and data science."
        await connector.ingest_bytes(content, "text/plain", "test://bytes")

        results = await connector.search("python programming", limit=5)
        assert len(results) > 0


async def test_connector_ingest_directory(mem_db_config: DatabaseConfig, tmp_path: Path) -> None:
    for i in range(3):
        (tmp_path / f"doc_{i}.txt").write_text(f"Document number {i} about testing.")

    async with DocumentConnector(db=mem_db_config) as connector:
        await connector.setup_schema()
        await connector.ingest_directory(tmp_path, glob="*.txt")

        all_docs = await connector._client.query(f"SELECT * FROM {mem_db_config.table}")
        assert len(all_docs) == 3


# --- DocumentPipeline ---


async def test_pipeline_full_roundtrip_embed_false(mem_db_config: DatabaseConfig, sample_text_file: Path) -> None:
    async with DocumentPipeline(db=mem_db_config, embed=False) as pipeline:
        await pipeline.setup_schema()
        await pipeline.ingest_file(sample_text_file)

        results = await pipeline.search("machine learning", limit=5)
        assert len(results) > 0

        chunks = await pipeline._client.query("SELECT * FROM chunks")
        assert len(chunks) > 0


async def test_pipeline_chunks_linked_to_document(mem_db_config: DatabaseConfig, sample_text_file: Path) -> None:
    async with DocumentPipeline(db=mem_db_config, embed=False) as pipeline:
        await pipeline.setup_schema()
        await pipeline.ingest_file(sample_text_file)

        chunks = await pipeline._client.query("SELECT * FROM chunks")
        assert len(chunks) > 0
        for chunk in chunks:
            assert "document" in chunk


async def test_pipeline_dedup_skips_chunks(mem_db_config: DatabaseConfig, sample_text_file: Path) -> None:
    async with DocumentPipeline(db=mem_db_config, embed=False) as pipeline:
        await pipeline.setup_schema()
        await pipeline.ingest_file(sample_text_file)
        first_chunk_count = len(await pipeline._client.query("SELECT * FROM chunks"))

        await pipeline.ingest_file(sample_text_file)
        second_chunk_count = len(await pipeline._client.query("SELECT * FROM chunks"))

        assert second_chunk_count == first_chunk_count


async def test_pipeline_fulltext_search_on_chunks(mem_db_config: DatabaseConfig, sample_text_file: Path) -> None:
    async with DocumentPipeline(db=mem_db_config, embed=False) as pipeline:
        await pipeline.setup_schema()
        await pipeline.ingest_file(sample_text_file)

        results = await pipeline.fulltext_search("neural networks", limit=5)
        assert len(results) > 0
