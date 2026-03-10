"""Document ingestion interface."""

import hashlib
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from kreuzberg import (
    ChunkingConfig,
    EmbeddingConfig,
    EmbeddingModelType,
    ExtractionConfig,
    ExtractionResult,
    extract_bytes,
    extract_file,
    get_embedding_preset,
)
from surrealdb import RecordID, Value

from kreuzberg_surrealdb.schema import build_connector_schema, build_pipeline_schema


@runtime_checkable
class AsyncSurrealConnection(Protocol):
    """Protocol for async SurrealDB connections.

    Satisfied by AsyncWsSurrealConnection, AsyncHttpSurrealConnection,
    AsyncEmbeddedSurrealConnection (returned by AsyncSurreal factory),
    and AsyncSurrealTransaction (for transactional ingestion).
    """

    async def query(self, query: str, vars: dict[str, Value] | None = None) -> Value: ...


def _content_hash(content: str) -> str:
    """Compute SHA-256 hash of content for dedup."""
    return hashlib.sha256(content.encode()).hexdigest()


def _parse_datetime(value: Any) -> datetime | None:
    """Parse a datetime value from metadata, returning None if invalid.

    Args:
        value: A datetime, ISO-format string, or None.

    Returns:
        A timezone-aware datetime, or None if the value is missing or unparseable.

    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value)
        except ValueError:
            return None
        else:
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return None


def _map_result_to_doc(result: ExtractionResult, source: str, table: str) -> dict[str, Value]:
    """Map an ExtractionResult to a SurrealDB document record.

    Args:
        result: The extraction result from Kreuzberg.
        source: Identifier for the document origin (e.g. file path).
        table: SurrealDB table name, used to build the deterministic RecordID.

    Returns:
        A dict ready for INSERT into SurrealDB, keyed by ``RecordID(table, content_hash)``.

    """
    content_hash = _content_hash(result.content)
    return {
        "id": RecordID(table, content_hash),
        "source": source,
        "content": result.content,
        "mime_type": result.mime_type,
        "title": result.metadata.get("title"),
        "authors": result.metadata.get("authors"),
        "created_at": _parse_datetime(result.metadata.get("created_at")),
        "metadata": result.metadata,
        "quality_score": result.quality_score,
        "content_hash": content_hash,
        "detected_languages": result.detected_languages,
        "keywords": result.extracted_keywords,
    }


def _check_insert_result(result: Value, *, context: str) -> None:
    """Check INSERT IGNORE results for silent errors and raise if found.

    SurrealDB's INSERT IGNORE swallows certain errors — returning error strings
    in the result list instead of raising exceptions. This catches dimension
    mismatches and other silent failures that would otherwise leave tables
    empty with no user-visible error.

    Args:
        result: The raw return value from ``client.query()`` for an INSERT IGNORE.
        context: A human-readable label (e.g. ``"document insertion"``) included
            in error messages.

    Raises:
        RuntimeError: If the result list contains error strings.

    """
    if not isinstance(result, list):
        return
    errors = [item for item in result if isinstance(item, str)]
    if not errors:
        return

    dim_errors = [e for e in errors if "dimension" in e.lower()]
    if dim_errors:
        msg = (
            f"Vector dimension mismatch during {context}. "
            "SurrealDB v3 enforces HNSW dimensions server-globally — "
            "once an index with dimension N exists anywhere on the server, "
            "inserts with a different dimension fail even across namespaces and databases. "
            "Use the same embedding model for all pipelines on the same server, "
            f"or use separate SurrealDB instances. Server error: {dim_errors[0]}"
        )
        raise RuntimeError(msg)

    msg = f"INSERT IGNORE failed silently during {context}: {errors[0]}"
    raise RuntimeError(msg)


def _collect_files(directory: str | Path, glob: str) -> list[Path]:
    """Collect matching file paths from a directory (sync helper).

    Args:
        directory: Root directory to search.
        glob: Glob pattern for file matching (e.g. ``"**/*.pdf"``).

    Returns:
        Sorted list of matching file paths.

    """
    return sorted(p for p in Path(directory).glob(glob) if p.is_file())


class DocumentConnector:
    """Full-document extraction and BM25 search. No chunking or embedding."""

    ANALYZER_NAME: str = "doc_analyzer"

    def __init__(
        self,
        *,
        db: AsyncSurrealConnection,
        table: str = "documents",
        insert_batch_size: int = 100,
        config: ExtractionConfig | None = None,
    ) -> None:
        """Initialize the connector.

        Args:
            db: An active SurrealDB async connection.
            table: Name of the documents table.
            insert_batch_size: Max records per INSERT IGNORE batch.
            config: Optional Kreuzberg ExtractionConfig for extraction tuning.

        """
        self._client = db
        self._table = table
        self._insert_batch_size = insert_batch_size
        self._config = config

    @property
    def client(self) -> AsyncSurrealConnection:
        """The underlying SurrealDB connection."""
        return self._client

    @property
    def table(self) -> str:
        """The documents table name."""
        return self._table

    @property
    def analyzer_name(self) -> str:
        """The BM25 analyzer name used in the schema."""
        return self.ANALYZER_NAME

    async def setup_schema(
        self,
        *,
        analyzer_language: str = "english",
        bm25_k1: float = 1.2,
        bm25_b: float = 0.75,
    ) -> None:
        """Create the documents table with BM25 index.

        Args:
            analyzer_language: Snowball stemmer language for the BM25 analyzer.
            bm25_k1: BM25 term-frequency saturation parameter.
            bm25_b: BM25 document-length normalization parameter.

        """
        stmts = build_connector_schema(
            table=self._table,
            analyzer_language=analyzer_language,
            bm25_k1=bm25_k1,
            bm25_b=bm25_b,
        )
        for stmt in stmts:
            await self._client.query(stmt)

    async def _insert_documents(self, records: list[dict[str, Value]]) -> list[Value]:
        """Insert documents with dedup via INSERT IGNORE.

        Args:
            records: Document dicts to insert, each keyed by a deterministic RecordID.

        Returns:
            Raw INSERT IGNORE results from SurrealDB, one entry per batch.

        """
        results: list[Value] = []
        table = self._table
        for i in range(0, len(records), self._insert_batch_size):
            batch = records[i : i + self._insert_batch_size]
            res = await self._client.query(
                f"INSERT IGNORE INTO {table} $records",
                {"records": batch},  # type: ignore[dict-item]
            )
            _check_insert_result(res, context="document insertion")
            results.append(res)
        return results

    async def _ingest_result(self, result: ExtractionResult, source: str) -> None:
        """Process a single extraction result.

        Args:
            result: The extraction result from Kreuzberg.
            source: Identifier for the document origin (e.g. file path).

        """
        doc = _map_result_to_doc(result, source, self._table)
        await self._insert_documents([doc])

    async def ingest_file(self, path: str | Path) -> None:
        """Extract and ingest a single file.

        Args:
            path: Path to the file to extract and store.

        """
        result = await extract_file(str(path), config=self._config)
        await self._ingest_result(result, str(path))

    async def ingest_files(self, paths: Sequence[str | Path]) -> None:
        """Extract and ingest multiple files.

        Args:
            paths: Sequence of file paths to extract and store.

        """
        for path in paths:
            result = await extract_file(str(path), config=self._config)
            await self._ingest_result(result, str(path))

    async def ingest_directory(self, directory: str | Path, *, glob: str = "**/*") -> None:
        """Extract and ingest all matching files in a directory.

        Args:
            directory: Root directory to search.
            glob: Glob pattern for file matching. Defaults to all files recursively.

        """
        await self.ingest_files(_collect_files(directory, glob))

    async def ingest_bytes(self, *, data: bytes, mime_type: str, source: str) -> None:
        """Extract and ingest from raw bytes.

        Args:
            data: Raw file content.
            mime_type: MIME type of the data (e.g. ``"application/pdf"``).
            source: Identifier for the document origin.

        """
        result = await extract_bytes(data, mime_type, config=self._config)
        await self._ingest_result(result, source)


class DocumentPipeline:
    """Chunked extraction with optional embedding for RAG pipelines."""

    def __init__(
        self,
        *,
        db: AsyncSurrealConnection,
        table: str = "documents",
        insert_batch_size: int = 100,
        chunk_table: str = "chunks",
        config: ExtractionConfig | None = None,
        embed: bool = True,
        embedding_model: str | EmbeddingModelType = "balanced",
        embedding_dimensions: int | None = None,
    ) -> None:
        """Initialize the pipeline.

        Args:
            db: An active SurrealDB async connection.
            table: Name of the documents table.
            insert_batch_size: Max records per INSERT IGNORE batch.
            chunk_table: Name of the chunks table.
            config: Optional Kreuzberg ExtractionConfig. If it includes a
                ChunkingConfig, the chunking parameters are preserved and only
                the embedding config is injected.
            embed: Whether to generate embeddings for vector search.
            embedding_model: Preset name (e.g. ``"balanced"``, ``"fast"``) or
                an ``EmbeddingModelType`` instance.
            embedding_dimensions: Vector dimensions. Required when passing an
                ``EmbeddingModelType`` directly; inferred from presets otherwise.

        Raises:
            ValueError: If the embedding preset is unknown or dimensions are
                missing for a custom model type.

        """
        self._client = db
        self._table = table
        self._insert_batch_size = insert_batch_size
        self._config = config
        self._chunk_table = chunk_table
        self._embed = embed

        if isinstance(embedding_model, str):
            preset_info = get_embedding_preset(embedding_model)
            if preset_info is None:
                msg = f"Unknown embedding preset: {embedding_model}"
                raise ValueError(msg)
            self._embedding_dimensions: int = embedding_dimensions or preset_info.dimensions
            self._embedding_model_type: EmbeddingModelType = EmbeddingModelType.preset(embedding_model)
        else:
            if embedding_dimensions is None:
                msg = "embedding_dimensions is required when passing an EmbeddingModelType directly"
                raise ValueError(msg)
            self._embedding_dimensions = embedding_dimensions
            self._embedding_model_type = embedding_model

        self._config = self._build_extraction_config()

    @property
    def client(self) -> AsyncSurrealConnection:
        """The underlying SurrealDB connection."""
        return self._client

    @property
    def table(self) -> str:
        """The documents table name."""
        return self._table

    @property
    def chunk_table(self) -> str:
        """The chunks table name."""
        return self._chunk_table

    @property
    def embedding_dimensions(self) -> int:
        """The vector embedding dimensions."""
        return self._embedding_dimensions

    def _build_extraction_config(self) -> ExtractionConfig:
        """Build ExtractionConfig with chunking and optional embedding.

        If the user provided an ExtractionConfig with a ChunkingConfig,
        preserve their chunking parameters (max_chars, max_overlap) and
        only inject the embedding configuration.

        Returns:
            A fully configured ExtractionConfig with chunking (and optionally
            embedding) enabled.

        """
        embedding = EmbeddingConfig(model=self._embedding_model_type) if self._embed else None

        if self._config is not None and self._config.chunking is not None:
            user_chunking = self._config.chunking
            self._config.chunking = ChunkingConfig(
                max_chars=user_chunking.max_chars,
                max_overlap=user_chunking.max_overlap,
                preset=user_chunking.preset,
                embedding=embedding,
            )
            return self._config

        chunking = ChunkingConfig(embedding=embedding)
        if self._config is not None:
            self._config.chunking = chunking
            return self._config
        return ExtractionConfig(chunking=chunking)

    async def setup_schema(
        self,
        *,
        analyzer_language: str = "english",
        bm25_k1: float = 1.2,
        bm25_b: float = 0.75,
        distance_metric: str = "COSINE",
        hnsw_efc: int = 150,
        hnsw_m: int = 12,
    ) -> None:
        """Create documents + chunks tables with BM25 and HNSW indexes.

        Args:
            analyzer_language: Snowball stemmer language for the BM25 analyzer.
            bm25_k1: BM25 term-frequency saturation parameter.
            bm25_b: BM25 document-length normalization parameter.
            distance_metric: HNSW distance function (e.g. ``"COSINE"``, ``"EUCLIDEAN"``).
            hnsw_efc: HNSW construction-time search width (higher = slower build, better recall).
            hnsw_m: HNSW max edges per node (higher = more memory, better recall).

        """
        stmts = build_pipeline_schema(
            table=self._table,
            chunk_table=self._chunk_table,
            embed=self._embed,
            embedding_dimension=self._embedding_dimensions,
            analyzer_language=analyzer_language,
            bm25_k1=bm25_k1,
            bm25_b=bm25_b,
            distance_metric=distance_metric,
            hnsw_efc=hnsw_efc,
            hnsw_m=hnsw_m,
        )
        for stmt in stmts:
            await self._client.query(stmt)

    async def _insert_documents(self, records: list[dict[str, Value]]) -> list[Value]:
        """Insert documents with dedup via INSERT IGNORE.

        Args:
            records: Document dicts to insert, each keyed by a deterministic RecordID.

        Returns:
            Raw INSERT IGNORE results from SurrealDB, one entry per batch.

        """
        results: list[Value] = []
        table = self._table
        for i in range(0, len(records), self._insert_batch_size):
            batch = records[i : i + self._insert_batch_size]
            res = await self._client.query(
                f"INSERT IGNORE INTO {table} $records",
                {"records": batch},  # type: ignore[dict-item]
            )
            _check_insert_result(res, context="document insertion")
            results.append(res)
        return results

    async def _ingest_result(self, result: ExtractionResult, source: str) -> None:
        """Extract, store document, then store chunks with record links.

        Both documents and chunks use deterministic record IDs and INSERT IGNORE,
        making the entire pipeline idempotent and resilient to partial failures.

        Args:
            result: The extraction result from Kreuzberg, including chunks.
            source: Identifier for the document origin (e.g. file path).

        """
        table = self._table
        content_hash = _content_hash(result.content)
        doc = _map_result_to_doc(result, source, table)
        doc_id = doc["id"]

        res = await self._client.query(
            f"INSERT IGNORE INTO {table} $records",
            {"records": [doc]},
        )
        _check_insert_result(res, context="document insertion")

        chunk_records: list[dict[str, Value]] = []
        for i, chunk in enumerate(result.chunks):
            chunk_rec: dict[str, Value] = {
                "id": RecordID(self._chunk_table, f"{content_hash}_{i}"),
                "document": doc_id,
                "content": chunk.content,
                "chunk_index": i,
                "embedding": chunk.embedding if self._embed else None,
                "token_count": len(chunk.content.split()),
            }
            if chunk.metadata:
                chunk_rec["page_number"] = chunk.metadata.get("page_number")
                chunk_rec["char_start"] = chunk.metadata.get("char_start")
                chunk_rec["char_end"] = chunk.metadata.get("char_end")
                chunk_rec["first_page"] = chunk.metadata.get("first_page")
                chunk_rec["last_page"] = chunk.metadata.get("last_page")
            chunk_records.append(chunk_rec)

        ct = self._chunk_table
        if chunk_records:
            for i in range(0, len(chunk_records), self._insert_batch_size):
                batch = chunk_records[i : i + self._insert_batch_size]
                res = await self._client.query(
                    f"INSERT IGNORE INTO {ct} $records",
                    {"records": batch},  # type: ignore[dict-item]
                )
                _check_insert_result(res, context="chunk insertion")

    async def ingest_file(self, path: str | Path) -> None:
        """Extract and ingest a single file.

        Args:
            path: Path to the file to extract and store.

        """
        result = await extract_file(str(path), config=self._config)
        await self._ingest_result(result, str(path))

    async def ingest_files(self, paths: Sequence[str | Path]) -> None:
        """Extract and ingest multiple files.

        Args:
            paths: Sequence of file paths to extract and store.

        """
        for path in paths:
            result = await extract_file(str(path), config=self._config)
            await self._ingest_result(result, str(path))

    async def ingest_directory(self, directory: str | Path, *, glob: str = "**/*") -> None:
        """Extract and ingest all matching files in a directory.

        Args:
            directory: Root directory to search.
            glob: Glob pattern for file matching. Defaults to all files recursively.

        """
        await self.ingest_files(_collect_files(directory, glob))

    async def ingest_bytes(self, *, data: bytes, mime_type: str, source: str) -> None:
        """Extract and ingest from raw bytes.

        Args:
            data: Raw file content.
            mime_type: MIME type of the data (e.g. ``"application/pdf"``).
            source: Identifier for the document origin.

        """
        result = await extract_bytes(data, mime_type, config=self._config)
        await self._ingest_result(result, source)

    async def embed_query(self, query: str) -> list[float]:
        """Embed a query string using kreuzberg's extraction pipeline.

        Args:
            query: The text to embed.

        Returns:
            The embedding vector as a list of floats.

        Raises:
            RuntimeError: If Kreuzberg returns no embedding for the query.

        """
        result = await extract_bytes(query.encode(), "text/plain", config=self._config)
        if not result.chunks or result.chunks[0].embedding is None:
            msg = "Embedding generation failed: no embedding returned for query"
            raise RuntimeError(msg)
        embedding: list[float] = result.chunks[0].embedding
        return embedding
