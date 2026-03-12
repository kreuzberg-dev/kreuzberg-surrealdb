"""Kreuzberg-to-SurrealDB connector for zero-dependency RAG pipelines."""

from kreuzberg_surrealdb._base import AsyncSurrealQueryable
from kreuzberg_surrealdb.connector import DocumentConnector
from kreuzberg_surrealdb.exceptions import DimensionMismatchError, IngestionError
from kreuzberg_surrealdb.pipeline import DocumentPipeline
from kreuzberg_surrealdb.types import ChunkRecord, DocumentRecord

__all__ = [
    "AsyncSurrealQueryable",
    "ChunkRecord",
    "DimensionMismatchError",
    "DocumentConnector",
    "DocumentPipeline",
    "DocumentRecord",
    "IngestionError",
]
