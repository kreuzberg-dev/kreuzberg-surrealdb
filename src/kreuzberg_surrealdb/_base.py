"""Base ingester and shared helpers for document ingestion."""

import hashlib
from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from kreuzberg import ExtractionConfig, ExtractionResult, extract_bytes, extract_file
from surrealdb import RecordID, Value

from kreuzberg_surrealdb.exceptions import DimensionMismatchError, IngestionError


@runtime_checkable
class AsyncSurrealQueryable(Protocol):
    """Protocol for any async SurrealDB object that can execute queries.

    Satisfied by connections (AsyncWsSurrealConnection, AsyncHttpSurrealConnection,
    AsyncEmbeddedSurrealConnection), transactions (AsyncSurrealTransaction),
    and sessions returned by the AsyncSurreal factory.
    """

    async def query(self, query: str, vars: dict[str, Value] | None = None) -> Value: ...  # noqa: A002


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
        DimensionMismatchError: If the error indicates a vector dimension conflict.
        IngestionError: If the result list contains other error strings.

    """
    if not isinstance(result, list):
        return
    errors = [item for item in result if isinstance(item, str)]
    if not errors:
        return

    dim_errors = [e for e in errors if "dimension" in e.lower()]
    if dim_errors:
        raise DimensionMismatchError(context, dim_errors[0])

    raise IngestionError(context, errors[0])


def _collect_files(directory: str | Path, glob: str) -> list[Path]:
    """Collect matching file paths from a directory (sync helper).

    Args:
        directory: Root directory to search.
        glob: Glob pattern for file matching (e.g. ``"**/*.pdf"``).

    Returns:
        Sorted list of matching file paths.

    """
    root = Path(directory).resolve()
    return sorted(p for p in root.glob(glob) if p.is_file() and p.resolve().is_relative_to(root))


class BaseIngester(ABC):
    """Abstract base for document ingestion into SurrealDB.

    Provides shared constructor, properties, batched insertion, and the four
    ``ingest_*`` entry points.  Subclasses implement ``_ingest_result`` to
    control how an ``ExtractionResult`` is mapped and stored.
    """

    def __init__(
        self,
        *,
        db: AsyncSurrealQueryable,
        table: str = "documents",
        insert_batch_size: int = 100,
        config: ExtractionConfig | None = None,
    ) -> None:
        """Initialize the ingester.

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
    def client(self) -> AsyncSurrealQueryable:
        """The underlying SurrealDB connection."""
        return self._client

    @property
    def table(self) -> str:
        """The documents table name."""
        return self._table

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
                {"records": batch},
            )
            _check_insert_result(res, context="document insertion")
            results.append(res)
        return results

    @abstractmethod
    async def _ingest_result(self, result: ExtractionResult, source: str) -> None:
        """Process a single extraction result.

        Args:
            result: The extraction result from Kreuzberg.
            source: Identifier for the document origin (e.g., file path).

        """

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
