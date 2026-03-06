"""Kreuzberg-to-SurrealDB connector for zero-dependency RAG pipelines."""

from importlib import metadata

try:
    __version__ = metadata.version(__package__) if __package__ else ""
except metadata.PackageNotFoundError:
    __version__ = ""
del metadata

__all__ = ["__version__"]
