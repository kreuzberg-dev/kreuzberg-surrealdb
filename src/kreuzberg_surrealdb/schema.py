"""SurrealDB schema definitions and DDL generation."""

from kreuzberg_surrealdb.config import IndexConfig


def _build_analyzer(index_config: IndexConfig) -> list[str]:
    """Generate the shared BM25 analyzer definition."""
    return [
        f"DEFINE ANALYZER IF NOT EXISTS doc_analyzer TOKENIZERS class "
        f"FILTERS snowball({index_config.analyzer_language});",
    ]


def build_document_schema(table: str, index_config: IndexConfig) -> list[str]:
    """Generate DDL for the documents table (used by both classes)."""
    stmts = _build_analyzer(index_config)
    stmts.extend(
        [
            f"DEFINE TABLE IF NOT EXISTS {table} SCHEMAFULL;",
            f"DEFINE FIELD IF NOT EXISTS source ON TABLE {table} TYPE string;",
            f"DEFINE FIELD IF NOT EXISTS content ON TABLE {table} TYPE string;",
            f"DEFINE FIELD IF NOT EXISTS mime_type ON TABLE {table} TYPE string;",
            f"DEFINE FIELD IF NOT EXISTS title ON TABLE {table} TYPE option<string>;",
            f"DEFINE FIELD IF NOT EXISTS authors ON TABLE {table} TYPE option<array<string>>;",
            f"DEFINE FIELD IF NOT EXISTS created_at ON TABLE {table} TYPE option<datetime>;",
            f"DEFINE FIELD IF NOT EXISTS ingested_at ON TABLE {table} TYPE datetime DEFAULT time::now();",
            f"DEFINE FIELD IF NOT EXISTS metadata ON TABLE {table} TYPE object FLEXIBLE;",
            f"DEFINE FIELD IF NOT EXISTS quality_score ON TABLE {table} TYPE option<float>;",
            f"DEFINE FIELD IF NOT EXISTS content_hash ON TABLE {table} TYPE string;",
            f"DEFINE FIELD IF NOT EXISTS detected_languages ON TABLE {table} TYPE option<array<object>>;",
            f"DEFINE FIELD IF NOT EXISTS keywords ON TABLE {table} TYPE option<array<object>>;",
            f"DEFINE INDEX IF NOT EXISTS idx_doc_source ON TABLE {table} FIELDS source UNIQUE;",
            f"DEFINE INDEX IF NOT EXISTS idx_doc_hash ON TABLE {table} FIELDS content_hash UNIQUE;",
        ]
    )
    return stmts


def build_connector_schema(table: str, index_config: IndexConfig) -> list[str]:
    """Generate DDL for DocumentConnector: documents table + BM25 on documents.content."""
    stmts = build_document_schema(table, index_config)
    stmts.append(
        f"DEFINE INDEX IF NOT EXISTS idx_doc_content ON TABLE {table} "
        f"FIELDS content SEARCH ANALYZER doc_analyzer BM25({index_config.bm25_k1},{index_config.bm25_b}) HIGHLIGHTS;",
    )
    return stmts


def _build_chunk_schema(chunk_table: str, table: str) -> list[str]:
    """Generate DDL for the chunks table."""
    return [
        f"DEFINE TABLE IF NOT EXISTS {chunk_table} SCHEMAFULL;",
        f"DEFINE FIELD IF NOT EXISTS document ON TABLE {chunk_table} TYPE record<{table}>;",
        f"DEFINE FIELD IF NOT EXISTS content ON TABLE {chunk_table} TYPE string;",
        f"DEFINE FIELD IF NOT EXISTS chunk_index ON TABLE {chunk_table} TYPE int;",
        f"DEFINE FIELD IF NOT EXISTS embedding ON TABLE {chunk_table} TYPE option<array<float>>;",
        f"DEFINE FIELD IF NOT EXISTS page_number ON TABLE {chunk_table} TYPE option<int>;",
        f"DEFINE FIELD IF NOT EXISTS char_start ON TABLE {chunk_table} TYPE option<int>;",
        f"DEFINE FIELD IF NOT EXISTS char_end ON TABLE {chunk_table} TYPE option<int>;",
        f"DEFINE FIELD IF NOT EXISTS token_count ON TABLE {chunk_table} TYPE option<int>;",
        f"DEFINE FIELD IF NOT EXISTS first_page ON TABLE {chunk_table} TYPE option<int>;",
        f"DEFINE FIELD IF NOT EXISTS last_page ON TABLE {chunk_table} TYPE option<int>;",
    ]


def build_pipeline_schema(
    table: str,
    chunk_table: str,
    *,
    embed: bool,
    index_config: IndexConfig,
    embedding_dimension: int,
) -> list[str]:
    """Generate DDL for DocumentPipeline: documents + chunks tables, conditional HNSW."""
    stmts = build_document_schema(table, index_config)
    stmts.extend(_build_chunk_schema(chunk_table, table))
    stmts.append(
        f"DEFINE INDEX IF NOT EXISTS idx_chunk_content ON TABLE {chunk_table} "
        f"FIELDS content SEARCH ANALYZER doc_analyzer BM25({index_config.bm25_k1},{index_config.bm25_b}) HIGHLIGHTS;",
    )
    if embed:
        stmts.append(
            f"DEFINE INDEX IF NOT EXISTS idx_chunk_embedding ON TABLE {chunk_table} "
            f"FIELDS embedding HNSW DIMENSION {embedding_dimension} TYPE F32 "
            f"DIST {index_config.distance_metric} EFC {index_config.hnsw_efc} M {index_config.hnsw_m};",
        )
    return stmts
