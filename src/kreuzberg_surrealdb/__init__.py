"""Kreuzberg-to-SurrealDB connector for zero-dependency RAG pipelines."""

from importlib import metadata

from kreuzberg_surrealdb.config import DatabaseConfig, IndexConfig
from kreuzberg_surrealdb.ingester import DocumentConnector, DocumentPipeline

try:
    __version__ = metadata.version(__package__) if __package__ else ""
except metadata.PackageNotFoundError:
    __version__ = ""
del metadata

__all__ = ["DatabaseConfig", "DocumentConnector", "DocumentPipeline", "IndexConfig", "__version__"]
