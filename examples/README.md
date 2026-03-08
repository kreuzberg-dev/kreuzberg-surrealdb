# Examples

Runnable examples demonstrating kreuzberg-surrealdb usage patterns.

## Prerequisites

Install the package with dev dependencies:

```bash
uv sync
```

## Examples

### `basic_ingest.py` — Document ingestion and BM25 search

Uses `DocumentConnector` with an in-memory SurrealDB instance. Demonstrates:

- Configuring a database connection
- Setting up the schema
- Ingesting a single file
- Running BM25 full-text search

```bash
uv run python examples/basic_ingest.py <path-to-file>
```

### `rag_pipeline.py` — Hybrid RAG pipeline with LLM integration

Uses `DocumentPipeline` with embeddings and hybrid search, then feeds results to an LLM for answer generation. Demonstrates:

- Chunked ingestion with local embeddings
- Hybrid search (vector + BM25 with RRF fusion)
- Passing retrieved chunks as context to an LLM API
- Quality threshold filtering

```bash
# Requires an API key for the LLM provider
export ANTHROPIC_API_KEY="your-key"

uv run python examples/rag_pipeline.py <path-to-directory>
```

## Database Modes

All examples default to `mem://` (in-memory embedded SurrealDB) for zero-setup usage. To use a remote instance:

```python
db = DatabaseConfig(
    db_url="ws://localhost:8000",
    username="root",
    password="root",
)
```
