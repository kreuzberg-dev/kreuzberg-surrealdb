"""Tests for configuration dataclasses."""
from kreuzberg_surrealdb.config import DatabaseConfig, IndexConfig


def test_database_config_defaults() -> None:
    cfg = DatabaseConfig(db_url="mem://")
    assert cfg.db_url == "mem://"
    assert cfg.namespace == "default"
    assert cfg.database == "default"
    assert cfg.username is None
    assert cfg.password is None
    assert cfg.table == "documents"
    assert cfg.insert_batch_size == 100


def test_database_config_custom_values() -> None:
    cfg = DatabaseConfig(
        db_url="ws://localhost:8000",
        namespace="prod",
        database="mydb",
        username="root",
        password="secret",
        table="docs",
        insert_batch_size=50,
    )
    assert cfg.db_url == "ws://localhost:8000"
    assert cfg.namespace == "prod"
    assert cfg.database == "mydb"
    assert cfg.username == "root"
    assert cfg.password == "secret"
    assert cfg.table == "docs"
    assert cfg.insert_batch_size == 50


def test_index_config_defaults() -> None:
    cfg = IndexConfig()
    assert cfg.analyzer_language == "english"
    assert cfg.bm25_k1 == 1.2
    assert cfg.bm25_b == 0.75
    assert cfg.distance_metric == "COSINE"
    assert cfg.hnsw_efc == 150
    assert cfg.hnsw_m == 12
    assert cfg.rrf_k == 60


def test_index_config_custom_values() -> None:
    cfg = IndexConfig(
        analyzer_language="german",
        bm25_k1=1.5,
        bm25_b=0.8,
        distance_metric="EUCLIDEAN",
        hnsw_efc=200,
        hnsw_m=16,
        rrf_k=30,
    )
    assert cfg.analyzer_language == "german"
    assert cfg.bm25_k1 == 1.5
    assert cfg.bm25_b == 0.8
    assert cfg.distance_metric == "EUCLIDEAN"
    assert cfg.hnsw_efc == 200
    assert cfg.hnsw_m == 16
    assert cfg.rrf_k == 30
