"""Document ingestion and search interface."""

import hashlib
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Self

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
from surrealdb import AsyncSurreal, RecordID

from kreuzberg_surrealdb.config import DatabaseConfig, IndexConfig
from kreuzberg_surrealdb.schema import build_connector_schema, build_pipeline_schema


def _content_hash(content: str) -> str:
    """Compute SHA-256 hash of content for dedup."""
    return hashlib.sha256(content.encode()).hexdigest()


def _parse_datetime(value: Any) -> datetime | None:
    """Parse a datetime value from metadata, returning None if invalid."""
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
            return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    return None


def _map_result_to_doc(result: ExtractionResult, source: str, table: str) -> dict[str, Any]:
    """Map an ExtractionResult to a SurrealDB document record."""
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


def _check_insert_result(result: Any, *, context: str) -> None:
    """Check INSERT IGNORE results for silent errors and raise if found.

    SurrealDB's INSERT IGNORE swallows certain errors — returning error strings
    in the result list instead of raising exceptions. This catches dimension
    mismatches and other silent failures that would otherwise leave tables
    empty with no user-visible error.
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
    """Collect matching file paths from a directory (sync helper)."""
    return sorted(p for p in Path(directory).glob(glob) if p.is_file())


class _BaseIngester:
    """Shared connection lifecycle, extraction, and ingestion logic."""

    def __init__(
        self,
        *,
        db: DatabaseConfig,
        config: ExtractionConfig | None = None,
        index_config: IndexConfig | None = None,
    ) -> None:
        self._db_config = db
        self._config = config
        self._index_config = index_config or IndexConfig()
        self._client: Any = None

    async def connect(self) -> None:
        """Connect to SurrealDB, authenticate, and select namespace/database."""
        self._client = AsyncSurreal(url=self._db_config.db_url)
        await self._client.connect()
        if self._db_config.username and self._db_config.password:
            await self._client.signin(
                {
                    "username": self._db_config.username,
                    "password": self._db_config.password,
                }
            )
        await self._client.use(self._db_config.namespace, self._db_config.database)

    async def close(self) -> None:
        """Close the SurrealDB connection."""
        if self._client:
            await self._client.close()
            self._client = None

    async def __aenter__(self) -> Self:
        await self.connect()
        return self

    async def __aexit__(self, *_args: object) -> None:
        await self.close()

    async def setup_schema(self) -> None:
        """Create tables and indexes. Overridden by subclasses."""
        raise NotImplementedError

    @property
    def _search_table(self) -> str:
        """Table to run fulltext search against. Overridden by subclasses."""
        return self._db_config.table

    async def _insert_documents(self, records: list[dict[str, Any]]) -> list[Any]:
        """Insert documents with dedup via INSERT IGNORE."""
        results = []
        table = self._db_config.table
        for i in range(0, len(records), self._db_config.insert_batch_size):
            batch = records[i : i + self._db_config.insert_batch_size]
            res = await self._client.query(
                f"INSERT IGNORE INTO {table} $records",
                {"records": batch},
            )
            _check_insert_result(res, context="document insertion")
            results.append(res)
        return results

    async def _ingest_result(self, result: ExtractionResult, source: str) -> None:
        """Process a single extraction result. Overridden by DocumentPipeline."""
        doc = _map_result_to_doc(result, source, self._db_config.table)
        await self._insert_documents([doc])

    async def ingest_file(self, path: str | Path) -> None:
        """Extract and ingest a single file."""
        result = await extract_file(str(path), config=self._config)
        await self._ingest_result(result, str(path))

    async def ingest_files(self, paths: Sequence[str | Path]) -> None:
        """Extract and ingest multiple files."""
        for path in paths:
            result = await extract_file(str(path), config=self._config)
            await self._ingest_result(result, str(path))

    async def ingest_directory(self, directory: str | Path, *, glob: str = "**/*") -> None:
        """Extract and ingest all matching files in a directory."""
        await self.ingest_files(_collect_files(directory, glob))

    async def ingest_bytes(self, *, data: bytes, mime_type: str, source: str) -> None:
        """Extract and ingest from raw bytes."""
        result = await extract_bytes(data, mime_type, config=self._config)
        await self._ingest_result(result, source)

    async def fulltext_search(self, query: str, *, limit: int = 10) -> list[dict[str, Any]]:
        """BM25 fulltext search over the search table."""
        table = self._search_table
        return await self._client.query(  # type: ignore[no-any-return]
            f"SELECT *, search::score(1) AS score FROM {table} "
            f"WHERE content @1@ $query ORDER BY score DESC LIMIT $limit",
            {"query": query, "limit": limit},
        )


class DocumentConnector(_BaseIngester):
    """Full-document extraction and BM25 search. No chunking or embedding."""

    async def setup_schema(self) -> None:
        """Create the documents table with BM25 index."""
        stmts = build_connector_schema(self._db_config.table, self._index_config)
        for stmt in stmts:
            await self._client.query(stmt)

    async def search(self, query: str, *, limit: int = 10) -> list[dict[str, Any]]:
        """BM25 search over full document content."""
        return await self.fulltext_search(query, limit=limit)


class DocumentPipeline(_BaseIngester):
    """Chunked extraction with optional embedding, hybrid search, and vector search."""

    def __init__(  # noqa: D107
        self,
        *,
        db: DatabaseConfig,
        chunk_table: str = "chunks",
        config: ExtractionConfig | None = None,
        embed: bool = True,
        embedding_model: str | EmbeddingModelType = "balanced",
        embedding_dimensions: int | None = None,
        index_config: IndexConfig | None = None,
    ) -> None:
        super().__init__(db=db, config=config, index_config=index_config)
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

    def _build_extraction_config(self) -> ExtractionConfig:
        """Build ExtractionConfig with chunking and optional embedding.

        If the user provided an ExtractionConfig with a ChunkingConfig,
        preserve their chunking parameters (max_chars, max_overlap) and
        only inject the embedding configuration.
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

    @property
    def _search_table(self) -> str:
        return self._chunk_table

    async def setup_schema(self) -> None:
        """Create documents + chunks tables with appropriate indexes."""
        stmts = build_pipeline_schema(
            table=self._db_config.table,
            chunk_table=self._chunk_table,
            embed=self._embed,
            index_config=self._index_config,
            embedding_dimension=self._embedding_dimensions,
        )
        for stmt in stmts:
            await self._client.query(stmt)

    async def _ingest_result(self, result: ExtractionResult, source: str) -> None:
        """Extract, store document, then store chunks with record links.

        Both documents and chunks use deterministic record IDs and INSERT IGNORE,
        making the entire pipeline idempotent and resilient to partial failures.
        """
        table = self._db_config.table
        doc = _map_result_to_doc(result, source, table)
        doc_id = doc["id"]
        content_hash = doc["content_hash"]

        res = await self._client.query(
            f"INSERT IGNORE INTO {table} $records",
            {"records": [doc]},
        )
        _check_insert_result(res, context="document insertion")

        chunk_records: list[dict[str, Any]] = []
        for i, chunk in enumerate(result.chunks):
            chunk_rec: dict[str, Any] = {
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
            for i in range(0, len(chunk_records), self._db_config.insert_batch_size):
                batch = chunk_records[i : i + self._db_config.insert_batch_size]
                res = await self._client.query(
                    f"INSERT IGNORE INTO {ct} $records",
                    {"records": batch},
                )
                _check_insert_result(res, context="chunk insertion")

    @staticmethod
    def _quality_clause(quality_threshold: float | None) -> str:
        """Build the WHERE clause fragment for quality filtering."""
        return "document.quality_score >= $quality_threshold AND " if quality_threshold is not None else ""

    async def _embed_query(self, query: str) -> list[float]:
        """Embed a query string using kreuzberg's extraction pipeline."""
        result = await extract_bytes(query.encode(), "text/plain", config=self._config)
        if not result.chunks or result.chunks[0].embedding is None:
            msg = "Embedding generation failed: no embedding returned for query"
            raise RuntimeError(msg)
        embedding: list[float] = result.chunks[0].embedding
        return embedding

    async def search(
        self,
        query: str,
        *,
        limit: int = 10,
        quality_threshold: float | None = None,
    ) -> list[dict[str, Any]]:
        """Hybrid search: vector + BM25 with RRF fusion. Falls back to BM25 when embed=False."""
        if not self._embed:
            return await self.fulltext_search(query, limit=limit)

        embedding = await self._embed_query(query)
        ct = self._chunk_table
        dist = self._index_config.distance_metric
        rrf_k = self._index_config.rrf_k
        quality_filter = self._quality_clause(quality_threshold)
        rrf_query = (
            f"SELECT * FROM search::rrf(["
            f"(SELECT id FROM {ct} WHERE {quality_filter}embedding <|{limit},{dist}|> $embedding),"
            f"(SELECT id, search::score(1) AS score FROM {ct} "
            f"WHERE {quality_filter}content @1@ $query ORDER BY score DESC LIMIT {limit})"
            f"], {limit}, {rrf_k});"
        )
        params: dict[str, Any] = {
            "embedding": embedding,
            "query": query,
        }
        if quality_threshold is not None:
            params["quality_threshold"] = quality_threshold
        return await self._client.query(rrf_query, params)  # type: ignore[no-any-return]

    async def vector_search(
        self,
        query: str,
        *,
        limit: int = 10,
        quality_threshold: float | None = None,
    ) -> list[dict[str, Any]]:
        """Pure HNSW semantic search over chunks. Requires embed=True."""
        if not self._embed:
            msg = "vector_search requires embed=True"
            raise ValueError(msg)

        embedding = await self._embed_query(query)
        ct = self._chunk_table
        dist = self._index_config.distance_metric
        quality_filter = self._quality_clause(quality_threshold)
        params: dict[str, Any] = {"embedding": embedding}
        if quality_threshold is not None:
            params["quality_threshold"] = quality_threshold
        return await self._client.query(  # type: ignore[no-any-return]
            f"SELECT *, vector::distance::knn() AS distance FROM {ct} "
            f"WHERE {quality_filter}embedding <|{limit},{dist}|> $embedding ORDER BY distance",
            params,
        )
