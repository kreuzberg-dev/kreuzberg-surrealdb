"""Tests for schema DDL generation."""

from kreuzberg_surrealdb.config import IndexConfig
from kreuzberg_surrealdb.schema import (
    build_connector_schema,
    build_document_schema,
    build_pipeline_schema,
)


def test_document_schema_generates_analyzer(index_config: IndexConfig) -> None:
    stmts = build_document_schema("documents", index_config)
    assert any("DEFINE ANALYZER" in s and "snowball(english)" in s for s in stmts)


def test_document_schema_generates_schemafull_table(index_config: IndexConfig) -> None:
    stmts = build_document_schema("documents", index_config)
    assert any("DEFINE TABLE IF NOT EXISTS documents SCHEMAFULL" in s for s in stmts)


def test_document_schema_generates_all_fields(index_config: IndexConfig) -> None:
    stmts = build_document_schema("documents", index_config)
    joined = " ".join(stmts)
    for field in [
        "source",
        "content",
        "mime_type",
        "title",
        "authors",
        "created_at",
        "ingested_at",
        "metadata",
        "quality_score",
        "content_hash",
        "detected_languages",
        "keywords",
    ]:
        assert f"FIELD IF NOT EXISTS {field}" in joined


def test_document_schema_generates_unique_indexes(index_config: IndexConfig) -> None:
    stmts = build_document_schema("documents", index_config)
    joined = " ".join(stmts)
    assert "idx_doc_source" in joined
    assert "idx_doc_hash" in joined
    assert "UNIQUE" in joined


def test_document_schema_custom_table_name(index_config: IndexConfig) -> None:
    stmts = build_document_schema("my_docs", index_config)
    assert any("DEFINE TABLE IF NOT EXISTS my_docs" in s for s in stmts)
    assert any("ON TABLE my_docs" in s for s in stmts)


def test_document_schema_custom_analyzer_language() -> None:
    cfg = IndexConfig(analyzer_language="german")
    stmts = build_document_schema("documents", cfg)
    assert any("snowball(german)" in s for s in stmts)


def test_connector_schema_includes_document_schema(index_config: IndexConfig) -> None:
    stmts = build_connector_schema("documents", index_config)
    joined = " ".join(stmts)
    assert "DEFINE TABLE IF NOT EXISTS documents SCHEMAFULL" in joined
    assert "idx_doc_source" in joined
    assert "idx_doc_hash" in joined


def test_connector_schema_adds_bm25_index_on_content(index_config: IndexConfig) -> None:
    stmts = build_connector_schema("documents", index_config)
    bm25_stmts = [s for s in stmts if "idx_doc_content" in s]
    assert len(bm25_stmts) == 1
    assert "BM25(1.2,0.75)" in bm25_stmts[0]
    assert "HIGHLIGHTS" in bm25_stmts[0]


def test_connector_schema_custom_bm25_params() -> None:
    cfg = IndexConfig(bm25_k1=1.5, bm25_b=0.8)
    stmts = build_connector_schema("documents", cfg)
    bm25_stmts = [s for s in stmts if "idx_doc_content" in s]
    assert "BM25(1.5,0.8)" in bm25_stmts[0]


def test_pipeline_schema_includes_document_and_chunk_tables(index_config: IndexConfig) -> None:
    stmts = build_pipeline_schema(
        "documents",
        "chunks",
        embed=True,
        index_config=index_config,
        embedding_dimension=768,
    )
    joined = " ".join(stmts)
    assert "DEFINE TABLE IF NOT EXISTS documents SCHEMAFULL" in joined
    assert "DEFINE TABLE IF NOT EXISTS chunks SCHEMAFULL" in joined


def test_pipeline_schema_chunk_fields(index_config: IndexConfig) -> None:
    stmts = build_pipeline_schema(
        "documents",
        "chunks",
        embed=True,
        index_config=index_config,
        embedding_dimension=768,
    )
    joined = " ".join(stmts)
    for field in [
        "document",
        "content",
        "chunk_index",
        "embedding",
        "page_number",
        "char_start",
        "char_end",
        "token_count",
        "first_page",
        "last_page",
    ]:
        assert f"FIELD IF NOT EXISTS {field} ON TABLE chunks" in joined


def test_pipeline_schema_chunk_document_record_link(index_config: IndexConfig) -> None:
    stmts = build_pipeline_schema(
        "documents",
        "chunks",
        embed=True,
        index_config=index_config,
        embedding_dimension=768,
    )
    assert any("TYPE record<documents>" in s for s in stmts)


def test_pipeline_schema_bm25_on_chunks(index_config: IndexConfig) -> None:
    stmts = build_pipeline_schema(
        "documents",
        "chunks",
        embed=True,
        index_config=index_config,
        embedding_dimension=768,
    )
    chunk_bm25 = [s for s in stmts if "idx_chunk_content" in s]
    assert len(chunk_bm25) == 1
    assert "BM25(1.2,0.75)" in chunk_bm25[0]


def test_pipeline_schema_no_bm25_on_documents(index_config: IndexConfig) -> None:
    stmts = build_pipeline_schema(
        "documents",
        "chunks",
        embed=True,
        index_config=index_config,
        embedding_dimension=768,
    )
    assert not any("idx_doc_content" in s for s in stmts)


def test_pipeline_schema_hnsw_index_when_embed_true(index_config: IndexConfig) -> None:
    stmts = build_pipeline_schema(
        "documents",
        "chunks",
        embed=True,
        index_config=index_config,
        embedding_dimension=768,
    )
    hnsw = [s for s in stmts if "idx_chunk_embedding" in s]
    assert len(hnsw) == 1
    assert "HNSW DIMENSION 768" in hnsw[0]
    assert "DIST COSINE" in hnsw[0]
    assert "EFC 150" in hnsw[0]
    assert "M 12" in hnsw[0]


def test_pipeline_schema_no_hnsw_index_when_embed_false(index_config: IndexConfig) -> None:
    stmts = build_pipeline_schema(
        "documents",
        "chunks",
        embed=False,
        index_config=index_config,
        embedding_dimension=768,
    )
    assert not any("idx_chunk_embedding" in s for s in stmts)
    assert any("idx_chunk_content" in s for s in stmts)


def test_pipeline_schema_custom_chunk_table_name(index_config: IndexConfig) -> None:
    stmts = build_pipeline_schema(
        "documents",
        "my_chunks",
        embed=True,
        index_config=index_config,
        embedding_dimension=384,
    )
    assert any("DEFINE TABLE IF NOT EXISTS my_chunks" in s for s in stmts)
    assert any("HNSW DIMENSION 384" in s for s in stmts)


def test_pipeline_schema_custom_hnsw_params() -> None:
    cfg = IndexConfig(distance_metric="EUCLIDEAN", hnsw_efc=200, hnsw_m=16)
    stmts = build_pipeline_schema(
        "documents",
        "chunks",
        embed=True,
        index_config=cfg,
        embedding_dimension=768,
    )
    hnsw = [s for s in stmts if "idx_chunk_embedding" in s]
    assert "DIST EUCLIDEAN" in hnsw[0]
    assert "EFC 200" in hnsw[0]
    assert "M 16" in hnsw[0]
