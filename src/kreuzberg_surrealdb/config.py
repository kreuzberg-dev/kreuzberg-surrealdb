"""Configuration dataclasses for kreuzberg-surrealdb."""
from dataclasses import dataclass


@dataclass
class DatabaseConfig:
    """SurrealDB connection and storage configuration."""

    db_url: str
    namespace: str = "default"
    database: str = "default"
    username: str | None = None
    password: str | None = None
    table: str = "documents"
    insert_batch_size: int = 100


@dataclass
class IndexConfig:
    """Index tuning parameters for BM25, HNSW, and RRF."""

    analyzer_language: str = "english"
    bm25_k1: float = 1.2
    bm25_b: float = 0.75
    distance_metric: str = "COSINE"
    hnsw_efc: int = 150
    hnsw_m: int = 12
    rrf_k: int = 60
