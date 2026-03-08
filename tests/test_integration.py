"""Integration tests requiring a live SurrealDB v3 server.

Run with: SURREALDB_URL=ws://localhost:8000 uv run pytest tests/test_integration.py -v -m integration

Requires:
- A SurrealDB v3 server (set SURREALDB_URL env var)
- ONNX Runtime installed on the system for embedding tests
"""

import os
import uuid
from pathlib import Path

import pytest

from kreuzberg_surrealdb.config import DatabaseConfig
from kreuzberg_surrealdb.ingester import DocumentConnector, DocumentPipeline
from tests.conftest import FIXTURES_DIR

pytestmark = pytest.mark.integration

_surrealdb_url = os.environ.get("SURREALDB_URL")


@pytest.fixture
def server_db_config() -> DatabaseConfig:
    """Config pointing at a real SurrealDB server with a unique database per test."""
    if not _surrealdb_url:
        pytest.skip("SURREALDB_URL not set")
    db_name = f"test_{uuid.uuid4().hex[:8]}"
    return DatabaseConfig(
        db_url=_surrealdb_url,
        namespace="test",
        database=db_name,
        username="root",
        password="root",
    )


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


@pytest.fixture
def ml_corpus(tmp_path: Path) -> Path:
    """Directory with multiple text files for batch/search tests."""
    texts = {
        "neural.txt": (
            "Neural networks are computing systems inspired by biological neural networks. "
            "They learn to perform tasks by considering examples without task-specific programming."
        ),
        "transformers.txt": (
            "Transformer models use self-attention mechanisms to process sequential data. "
            "They are the foundation of modern large language models like GPT and BERT."
        ),
        "reinforcement.txt": (
            "Reinforcement learning trains agents to make decisions by rewarding desired behaviors. "
            "It has been used to master games like chess and Go."
        ),
    }
    for name, content in texts.items():
        (tmp_path / name).write_text(content)
    return tmp_path


# --- DocumentConnector ---


async def test_connector_full_roundtrip(server_db_config: DatabaseConfig, sample_text_file: Path) -> None:
    async with DocumentConnector(db=server_db_config) as connector:
        await connector.setup_schema()
        await connector.ingest_file(sample_text_file)

        results = await connector.search("machine learning", limit=5)
        assert len(results) > 0


async def test_connector_ingest_multiple_files(
    server_db_config: DatabaseConfig,
    sample_text_file: Path,
    second_text_file: Path,
) -> None:
    async with DocumentConnector(db=server_db_config) as connector:
        await connector.setup_schema()
        await connector.ingest_files([sample_text_file, second_text_file])

        results = await connector.search("database", limit=10)
        assert len(results) > 0


async def test_connector_dedup_same_content(server_db_config: DatabaseConfig, sample_text_file: Path) -> None:
    async with DocumentConnector(db=server_db_config) as connector:
        await connector.setup_schema()
        await connector.ingest_file(sample_text_file)
        await connector.ingest_file(sample_text_file)

        all_docs = await connector._client.query(f"SELECT * FROM {server_db_config.table}")
        assert len(all_docs) == 1


async def test_connector_ingest_bytes(server_db_config: DatabaseConfig) -> None:
    async with DocumentConnector(db=server_db_config) as connector:
        await connector.setup_schema()
        content = b"Python is a programming language used for web development and data science."
        await connector.ingest_bytes(data=content, mime_type="text/plain", source="test://bytes")

        results = await connector.search("python programming", limit=5)
        assert len(results) > 0


async def test_connector_ingest_directory(server_db_config: DatabaseConfig, tmp_path: Path) -> None:
    for i in range(3):
        (tmp_path / f"doc_{i}.txt").write_text(f"Document number {i} about testing.")

    async with DocumentConnector(db=server_db_config) as connector:
        await connector.setup_schema()
        await connector.ingest_directory(tmp_path, glob="*.txt")

        all_docs = await connector._client.query(f"SELECT * FROM {server_db_config.table}")
        assert len(all_docs) == 3


async def test_connector_document_metadata_stored(server_db_config: DatabaseConfig, sample_text_file: Path) -> None:
    async with DocumentConnector(db=server_db_config) as connector:
        await connector.setup_schema()
        await connector.ingest_file(sample_text_file)

        docs = await connector._client.query(f"SELECT * FROM {server_db_config.table}")
        assert len(docs) == 1
        doc = docs[0]
        assert doc["source"] == str(sample_text_file)
        assert len(doc["content"]) > 0
        assert doc["mime_type"] == "text/plain"
        assert doc["content_hash"] is not None
        assert doc["ingested_at"] is not None


async def test_connector_search_limit_respected(server_db_config: DatabaseConfig, ml_corpus: Path) -> None:
    async with DocumentConnector(db=server_db_config) as connector:
        await connector.setup_schema()
        await connector.ingest_directory(ml_corpus, glob="*.txt")

        results_1 = await connector.search("learning", limit=1)
        results_all = await connector.search("learning", limit=10)
        assert len(results_1) <= 1
        assert len(results_all) >= len(results_1)


async def test_connector_custom_table_name(server_db_config: DatabaseConfig, sample_text_file: Path) -> None:
    cfg = DatabaseConfig(
        db_url=server_db_config.db_url,
        namespace=server_db_config.namespace,
        database=server_db_config.database,
        username=server_db_config.username,
        password=server_db_config.password,
        table="my_docs",
    )
    async with DocumentConnector(db=cfg) as connector:
        await connector.setup_schema()
        await connector.ingest_file(sample_text_file)

        docs = await connector._client.query("SELECT * FROM my_docs")
        assert len(docs) == 1

        results = await connector.search("machine learning")
        assert len(results) > 0


# --- DocumentPipeline (embed=False) ---


async def test_pipeline_full_roundtrip_embed_false(server_db_config: DatabaseConfig, sample_text_file: Path) -> None:
    async with DocumentPipeline(db=server_db_config, embed=False) as pipeline:
        await pipeline.setup_schema()
        await pipeline.ingest_file(sample_text_file)

        results = await pipeline.search("machine learning", limit=5)
        assert len(results) > 0

        chunks = await pipeline._client.query("SELECT * FROM chunks")
        assert len(chunks) > 0


async def test_pipeline_chunks_linked_to_document(server_db_config: DatabaseConfig, sample_text_file: Path) -> None:
    async with DocumentPipeline(db=server_db_config, embed=False) as pipeline:
        await pipeline.setup_schema()
        await pipeline.ingest_file(sample_text_file)

        chunks = await pipeline._client.query("SELECT * FROM chunks")
        assert len(chunks) > 0
        for chunk in chunks:
            assert "document" in chunk


async def test_pipeline_dedup_skips_chunks(server_db_config: DatabaseConfig, sample_text_file: Path) -> None:
    async with DocumentPipeline(db=server_db_config, embed=False) as pipeline:
        await pipeline.setup_schema()
        await pipeline.ingest_file(sample_text_file)
        first_chunk_count = len(await pipeline._client.query("SELECT * FROM chunks"))

        await pipeline.ingest_file(sample_text_file)
        second_chunk_count = len(await pipeline._client.query("SELECT * FROM chunks"))

        assert second_chunk_count == first_chunk_count


async def test_pipeline_fulltext_search_on_chunks(server_db_config: DatabaseConfig, sample_text_file: Path) -> None:
    async with DocumentPipeline(db=server_db_config, embed=False) as pipeline:
        await pipeline.setup_schema()
        await pipeline.ingest_file(sample_text_file)

        results = await pipeline.fulltext_search("neural networks", limit=5)
        assert len(results) > 0


async def test_pipeline_chunk_metadata_stored(server_db_config: DatabaseConfig, sample_text_file: Path) -> None:
    async with DocumentPipeline(db=server_db_config, embed=False) as pipeline:
        await pipeline.setup_schema()
        await pipeline.ingest_file(sample_text_file)

        chunks = await pipeline._client.query("SELECT * FROM chunks ORDER BY chunk_index ASC")
        assert len(chunks) > 0
        for i, chunk in enumerate(chunks):
            assert chunk["chunk_index"] == i
            assert "content" in chunk
            assert len(chunk["content"]) > 0
            assert chunk.get("token_count") is not None
            assert chunk["token_count"] > 0


async def test_pipeline_embed_false_no_embeddings(server_db_config: DatabaseConfig, sample_text_file: Path) -> None:
    async with DocumentPipeline(db=server_db_config, embed=False) as pipeline:
        await pipeline.setup_schema()
        await pipeline.ingest_file(sample_text_file)

        chunks = await pipeline._client.query("SELECT * FROM chunks")
        for chunk in chunks:
            assert chunk.get("embedding") is None


async def test_pipeline_ingest_directory(server_db_config: DatabaseConfig, ml_corpus: Path) -> None:
    async with DocumentPipeline(db=server_db_config, embed=False) as pipeline:
        await pipeline.setup_schema()
        await pipeline.ingest_directory(ml_corpus, glob="*.txt")

        docs = await pipeline._client.query("SELECT * FROM documents")
        assert len(docs) == 3

        chunks = await pipeline._client.query("SELECT * FROM chunks")
        assert len(chunks) >= 3


async def test_pipeline_ingest_files(
    server_db_config: DatabaseConfig,
    sample_text_file: Path,
    second_text_file: Path,
) -> None:
    async with DocumentPipeline(db=server_db_config, embed=False) as pipeline:
        await pipeline.setup_schema()
        await pipeline.ingest_files([sample_text_file, second_text_file])

        docs = await pipeline._client.query("SELECT * FROM documents")
        assert len(docs) == 2


async def test_pipeline_ingest_bytes(server_db_config: DatabaseConfig) -> None:
    async with DocumentPipeline(db=server_db_config, embed=False) as pipeline:
        await pipeline.setup_schema()
        content = b"Kubernetes orchestrates containerized applications across clusters of machines."
        await pipeline.ingest_bytes(data=content, mime_type="text/plain", source="test://k8s")

        docs = await pipeline._client.query("SELECT * FROM documents")
        assert len(docs) == 1
        assert docs[0]["source"] == "test://k8s"


async def test_pipeline_search_limit_respected(server_db_config: DatabaseConfig, ml_corpus: Path) -> None:
    async with DocumentPipeline(db=server_db_config, embed=False) as pipeline:
        await pipeline.setup_schema()
        await pipeline.ingest_directory(ml_corpus, glob="*.txt")

        results_1 = await pipeline.search("learning", limit=1)
        results_all = await pipeline.search("learning", limit=50)
        assert len(results_1) <= 1
        assert len(results_all) >= len(results_1)


async def test_pipeline_custom_table_names(server_db_config: DatabaseConfig, sample_text_file: Path) -> None:
    cfg = DatabaseConfig(
        db_url=server_db_config.db_url,
        namespace=server_db_config.namespace,
        database=server_db_config.database,
        username=server_db_config.username,
        password=server_db_config.password,
        table="my_docs",
    )
    async with DocumentPipeline(db=cfg, chunk_table="my_chunks", embed=False) as pipeline:
        await pipeline.setup_schema()
        await pipeline.ingest_file(sample_text_file)

        docs = await pipeline._client.query("SELECT * FROM my_docs")
        assert len(docs) == 1

        chunks = await pipeline._client.query("SELECT * FROM my_chunks")
        assert len(chunks) > 0

        results = await pipeline.search("machine learning")
        assert len(results) > 0


async def test_pipeline_vector_search_raises_when_embed_false(server_db_config: DatabaseConfig) -> None:
    async with DocumentPipeline(db=server_db_config, embed=False) as pipeline:
        await pipeline.setup_schema()
        with pytest.raises(ValueError, match="embed=True"):
            await pipeline.vector_search("test query")


# --- DocumentPipeline (embed=True) ---
# These tests require kreuzberg's ONNX runtime for embedding generation.


async def test_pipeline_embed_true_ingest_and_chunks_have_embeddings(
    server_db_config: DatabaseConfig,
    sample_text_file: Path,
) -> None:
    async with DocumentPipeline(db=server_db_config, embed=True) as pipeline:
        await pipeline.setup_schema()
        await pipeline.ingest_file(sample_text_file)

        chunks = await pipeline._client.query("SELECT * FROM chunks")
        assert len(chunks) > 0
        for chunk in chunks:
            assert chunk.get("embedding") is not None
            assert isinstance(chunk["embedding"], list)
            assert len(chunk["embedding"]) == 768


async def test_pipeline_embed_true_dedup(server_db_config: DatabaseConfig, sample_text_file: Path) -> None:
    async with DocumentPipeline(db=server_db_config, embed=True) as pipeline:
        await pipeline.setup_schema()
        await pipeline.ingest_file(sample_text_file)
        first_count = len(await pipeline._client.query("SELECT * FROM chunks"))

        await pipeline.ingest_file(sample_text_file)
        second_count = len(await pipeline._client.query("SELECT * FROM chunks"))

        assert second_count == first_count


async def test_pipeline_fast_preset_embeddings(sample_text_file: Path) -> None:
    """Verify the 'fast' preset produces 384-dim embeddings.

    Uses kreuzberg extraction directly instead of full pipeline ingestion because
    SurrealDB v3 has a bug where HNSW vector dimension validation is server-global:
    once any HNSW index with dimension N exists, inserts with a different dimension
    fail across all namespaces and databases. Since other tests create 768-dim indexes,
    384-dim inserts would fail.
    """
    from kreuzberg import extract_file

    pipeline = DocumentPipeline(
        db=DatabaseConfig(db_url="ws://localhost:8000"),
        embed=True,
        embedding_model="fast",
    )
    result = await extract_file(str(sample_text_file), config=pipeline._config)
    assert len(result.chunks) > 0
    for chunk in result.chunks:
        assert chunk.embedding is not None
        assert len(chunk.embedding) == 384


async def test_pipeline_embed_true_fulltext_search_still_works(
    server_db_config: DatabaseConfig,
    sample_text_file: Path,
) -> None:
    """Even with embed=True, BM25 fulltext search on chunks should work."""
    async with DocumentPipeline(db=server_db_config, embed=True) as pipeline:
        await pipeline.setup_schema()
        await pipeline.ingest_file(sample_text_file)

        results = await pipeline.fulltext_search("neural networks", limit=5)
        assert len(results) > 0


async def test_pipeline_embed_true_multiple_docs_ingested(server_db_config: DatabaseConfig, ml_corpus: Path) -> None:
    async with DocumentPipeline(db=server_db_config, embed=True) as pipeline:
        await pipeline.setup_schema()
        await pipeline.ingest_directory(ml_corpus, glob="*.txt")

        docs = await pipeline._client.query("SELECT * FROM documents")
        assert len(docs) == 3

        chunks = await pipeline._client.query("SELECT * FROM chunks")
        assert len(chunks) >= 3
        for chunk in chunks:
            assert chunk.get("embedding") is not None
            assert len(chunk["embedding"]) == 768


# --- Hybrid search and vector search ---


async def test_pipeline_hybrid_search(server_db_config: DatabaseConfig, sample_text_file: Path) -> None:
    async with DocumentPipeline(db=server_db_config, embed=True) as pipeline:
        await pipeline.setup_schema()
        await pipeline.ingest_file(sample_text_file)

        results = await pipeline.search("machine learning algorithms", limit=5)
        assert len(results) > 0


async def test_pipeline_vector_search(server_db_config: DatabaseConfig, sample_text_file: Path) -> None:
    async with DocumentPipeline(db=server_db_config, embed=True) as pipeline:
        await pipeline.setup_schema()
        await pipeline.ingest_file(sample_text_file)

        results = await pipeline.vector_search("artificial intelligence", limit=5)
        assert len(results) > 0


async def test_pipeline_hybrid_search_multiple_docs(server_db_config: DatabaseConfig, ml_corpus: Path) -> None:
    async with DocumentPipeline(db=server_db_config, embed=True) as pipeline:
        await pipeline.setup_schema()
        await pipeline.ingest_directory(ml_corpus, glob="*.txt")

        results = await pipeline.search("transformer attention mechanism", limit=5)
        assert len(results) > 0


async def test_pipeline_vector_search_multiple_docs(server_db_config: DatabaseConfig, ml_corpus: Path) -> None:
    async with DocumentPipeline(db=server_db_config, embed=True) as pipeline:
        await pipeline.setup_schema()
        await pipeline.ingest_directory(ml_corpus, glob="*.txt")

        results = await pipeline.vector_search("reinforcement learning reward", limit=5)
        assert len(results) > 0


async def test_pipeline_fast_preset_vector_search() -> None:
    """Verify the 'fast' preset can embed a query for vector search.

    Tests kreuzberg embedding only (not SurrealDB vector search) due to a SurrealDB v3
    bug where HNSW dimension validation is server-global — see
    test_pipeline_fast_preset_embeddings docstring for details.
    """
    from kreuzberg import extract_bytes

    pipeline = DocumentPipeline(
        db=DatabaseConfig(db_url="ws://localhost:8000"),
        embed=True,
        embedding_model="fast",
    )
    result = await extract_bytes(b"machine learning", "text/plain", config=pipeline._config)
    assert len(result.chunks) > 0
    assert result.chunks[0].embedding is not None
    assert len(result.chunks[0].embedding) == 384


# --- Fixture-based ingestion tests ---
# These use real document fixtures (txt, html, pdf, docx) instead of synthetic text.

FIXTURE_FILES = {
    "txt": FIXTURES_DIR / "sample.txt",
    "html": FIXTURES_DIR / "sample.html",
    "pdf": FIXTURES_DIR / "sample.pdf",
    "docx": FIXTURES_DIR / "sample.docx",
}

_MIME_FALLBACK = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _mime_for(path: Path) -> str:
    """Derive MIME type from file extension."""
    import mimetypes

    mime, _ = mimetypes.guess_type(path.name)
    if mime is None:
        mime = _MIME_FALLBACK.get(path.suffix, "application/octet-stream")
    return mime


# --- DocumentConnector: file path ingestion ---


@pytest.mark.parametrize("fmt", ["txt", "html", "pdf", "docx"])
async def test_connector_ingest_file_fixture(server_db_config: DatabaseConfig, fmt: str) -> None:
    path = FIXTURE_FILES[fmt]
    async with DocumentConnector(db=server_db_config) as connector:
        await connector.setup_schema()
        await connector.ingest_file(path)

        docs = await connector._client.query(f"SELECT * FROM {server_db_config.table}")
        assert len(docs) == 1
        assert docs[0]["source"] == str(path)
        assert len(docs[0]["content"]) > 0
        assert docs[0]["content_hash"] is not None


# --- DocumentConnector: bytes ingestion ---


@pytest.mark.parametrize("fmt", ["txt", "html", "pdf", "docx"])
async def test_connector_ingest_bytes_fixture(server_db_config: DatabaseConfig, fmt: str) -> None:
    path = FIXTURE_FILES[fmt]
    data = path.read_bytes()

    async with DocumentConnector(db=server_db_config) as connector:
        await connector.setup_schema()
        await connector.ingest_bytes(data=data, mime_type=_mime_for(path), source=f"fixture://{fmt}")

        docs = await connector._client.query(f"SELECT * FROM {server_db_config.table}")
        assert len(docs) == 1
        assert docs[0]["source"] == f"fixture://{fmt}"
        assert len(docs[0]["content"]) > 0


# --- DocumentConnector: ingest_files with all fixtures ---


async def test_connector_ingest_files_all_fixtures(server_db_config: DatabaseConfig) -> None:
    paths = list(FIXTURE_FILES.values())
    async with DocumentConnector(db=server_db_config) as connector:
        await connector.setup_schema()
        await connector.ingest_files(paths)

        docs = await connector._client.query(f"SELECT * FROM {server_db_config.table}")
        assert len(docs) == len(paths)


# --- DocumentConnector: ingest_directory with fixtures ---


async def test_connector_ingest_directory_fixtures(server_db_config: DatabaseConfig) -> None:
    async with DocumentConnector(db=server_db_config) as connector:
        await connector.setup_schema()
        await connector.ingest_directory(FIXTURES_DIR, glob="*.*")

        docs = await connector._client.query(f"SELECT * FROM {server_db_config.table}")
        assert len(docs) == 4


# --- DocumentConnector: search over fixture content ---


async def test_connector_search_fixture_content(server_db_config: DatabaseConfig) -> None:
    async with DocumentConnector(db=server_db_config) as connector:
        await connector.setup_schema()
        await connector.ingest_directory(FIXTURES_DIR, glob="*.*")

        results = await connector.search("sample document testing", limit=10)
        assert len(results) > 0


# --- DocumentPipeline (embed=False): file path ingestion ---


@pytest.mark.parametrize("fmt", ["txt", "html", "pdf", "docx"])
async def test_pipeline_ingest_file_fixture_embed_false(server_db_config: DatabaseConfig, fmt: str) -> None:
    path = FIXTURE_FILES[fmt]
    async with DocumentPipeline(db=server_db_config, embed=False) as pipeline:
        await pipeline.setup_schema()
        await pipeline.ingest_file(path)

        docs = await pipeline._client.query("SELECT * FROM documents")
        assert len(docs) == 1
        assert docs[0]["source"] == str(path)

        chunks = await pipeline._client.query("SELECT * FROM chunks ORDER BY chunk_index ASC")
        assert len(chunks) > 0
        for i, chunk in enumerate(chunks):
            assert chunk["chunk_index"] == i
            assert len(chunk["content"]) > 0
            assert chunk.get("embedding") is None


# --- DocumentPipeline (embed=False): bytes ingestion ---


@pytest.mark.parametrize("fmt", ["txt", "html", "pdf", "docx"])
async def test_pipeline_ingest_bytes_fixture_embed_false(server_db_config: DatabaseConfig, fmt: str) -> None:
    path = FIXTURE_FILES[fmt]
    data = path.read_bytes()

    async with DocumentPipeline(db=server_db_config, embed=False) as pipeline:
        await pipeline.setup_schema()
        await pipeline.ingest_bytes(data=data, mime_type=_mime_for(path), source=f"fixture://{fmt}")

        docs = await pipeline._client.query("SELECT * FROM documents")
        assert len(docs) == 1
        assert docs[0]["source"] == f"fixture://{fmt}"

        chunks = await pipeline._client.query("SELECT * FROM chunks")
        assert len(chunks) > 0


# --- DocumentPipeline (embed=False): ingest_files + ingest_directory ---


async def test_pipeline_ingest_files_all_fixtures_embed_false(server_db_config: DatabaseConfig) -> None:
    paths = list(FIXTURE_FILES.values())
    async with DocumentPipeline(db=server_db_config, embed=False) as pipeline:
        await pipeline.setup_schema()
        await pipeline.ingest_files(paths)

        docs = await pipeline._client.query("SELECT * FROM documents")
        assert len(docs) == len(paths)

        chunks = await pipeline._client.query("SELECT * FROM chunks")
        assert len(chunks) >= len(paths)


async def test_pipeline_ingest_directory_fixtures_embed_false(server_db_config: DatabaseConfig) -> None:
    async with DocumentPipeline(db=server_db_config, embed=False) as pipeline:
        await pipeline.setup_schema()
        await pipeline.ingest_directory(FIXTURES_DIR, glob="*.*")

        docs = await pipeline._client.query("SELECT * FROM documents")
        assert len(docs) == 4

        chunks = await pipeline._client.query("SELECT * FROM chunks")
        assert len(chunks) >= 4


# --- DocumentPipeline (embed=False): search over fixture content ---


async def test_pipeline_search_fixture_content_embed_false(server_db_config: DatabaseConfig) -> None:
    async with DocumentPipeline(db=server_db_config, embed=False) as pipeline:
        await pipeline.setup_schema()
        await pipeline.ingest_directory(FIXTURES_DIR, glob="*.*")

        results = await pipeline.search("sample document", limit=10)
        assert len(results) > 0


# --- DocumentPipeline (embed=True): file path ingestion ---


@pytest.mark.parametrize("fmt", ["txt", "html", "pdf", "docx"])
async def test_pipeline_ingest_file_fixture_embed_true(server_db_config: DatabaseConfig, fmt: str) -> None:
    path = FIXTURE_FILES[fmt]
    async with DocumentPipeline(db=server_db_config, embed=True) as pipeline:
        await pipeline.setup_schema()
        await pipeline.ingest_file(path)

        docs = await pipeline._client.query("SELECT * FROM documents")
        assert len(docs) == 1

        chunks = await pipeline._client.query("SELECT * FROM chunks")
        assert len(chunks) > 0
        for chunk in chunks:
            assert chunk.get("embedding") is not None
            assert len(chunk["embedding"]) == 768


# --- DocumentPipeline (embed=True): bytes ingestion ---


@pytest.mark.parametrize("fmt", ["txt", "html", "pdf", "docx"])
async def test_pipeline_ingest_bytes_fixture_embed_true(server_db_config: DatabaseConfig, fmt: str) -> None:
    path = FIXTURE_FILES[fmt]
    data = path.read_bytes()

    async with DocumentPipeline(db=server_db_config, embed=True) as pipeline:
        await pipeline.setup_schema()
        await pipeline.ingest_bytes(data=data, mime_type=_mime_for(path), source=f"fixture://{fmt}")

        docs = await pipeline._client.query("SELECT * FROM documents")
        assert len(docs) == 1

        chunks = await pipeline._client.query("SELECT * FROM chunks")
        assert len(chunks) > 0
        for chunk in chunks:
            assert chunk.get("embedding") is not None
            assert len(chunk["embedding"]) == 768


# --- DocumentPipeline (embed=True): batch ingestion ---


async def test_pipeline_ingest_all_fixtures_embed_true(server_db_config: DatabaseConfig) -> None:
    async with DocumentPipeline(db=server_db_config, embed=True) as pipeline:
        await pipeline.setup_schema()
        await pipeline.ingest_directory(FIXTURES_DIR, glob="*.*")

        docs = await pipeline._client.query("SELECT * FROM documents")
        assert len(docs) == 4

        chunks = await pipeline._client.query("SELECT * FROM chunks")
        assert len(chunks) >= 4
        for chunk in chunks:
            assert chunk.get("embedding") is not None
            assert len(chunk["embedding"]) == 768
