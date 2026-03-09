# Examples

Runnable examples demonstrating kreuzberg-surrealdb usage patterns.

## Prerequisites

Install the package with dev dependencies:

```bash
uv sync
```

Start a SurrealDB server:

```bash
docker run --rm -p 8000:8000 surrealdb/surrealdb:latest start --user root --pass root
```

## Examples

### `basic_ingest.py` — Document ingestion and BM25 search

Uses `DocumentConnector` with a SurrealDB server. Demonstrates:

- Connecting to SurrealDB via the SDK
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

## Connection Pattern

All examples connect to a local SurrealDB server using the SDK:

```python
from surrealdb import AsyncSurreal

async with AsyncSurreal("ws://localhost:8000") as db:
    await db.signin({"username": "root", "password": "root"})
    await db.use("default", "default")

    connector = DocumentConnector(db=db)
    ...
```
