# kreuzberg-surrealdb

Kreuzberg-to-SurrealDB connector for zero-dependency RAG pipelines.

Local document extraction, local embeddings, and hybrid search in a single database — no external API keys required.

[![PyPI](https://img.shields.io/pypi/v/kreuzberg-surrealdb)](https://pypi.org/project/kreuzberg-surrealdb/)
[![Python](https://img.shields.io/pypi/pyversions/kreuzberg-surrealdb)](https://pypi.org/project/kreuzberg-surrealdb/)
[![License](https://img.shields.io/pypi/l/kreuzberg-surrealdb)](https://github.com/kreuzberg-dev/kreuzberg-surrealdb/blob/main/LICENSE)

## Features

- **Multi-format extraction** — PDF, DOCX, HTML, TXT, and more via [Kreuzberg](https://github.com/kreuzberg-dev/kreuzberg)
- **Local embeddings** — ONNX-based models via [Kreuzberg](https://github.com/kreuzberg-dev/kreuzberg), no API keys needed
- **Three search modes** — BM25 full-text, HNSW vector, and hybrid (RRF fusion)
- **Content deduplication** — SHA-256 hashing prevents duplicate documents across ingestion runs
- **Quality filtering** — filter search results by Kreuzberg's extraction quality score
- **Configurable indexing** — tune BM25, HNSW, and RRF parameters to your use case

## Installation

```bash
pip install kreuzberg-surrealdb
```

Requires Python 3.11+.

## Quickstart

### Document-level search with `DocumentConnector`

Extract full documents and search with BM25. No chunking, no embeddings — fast and simple.

```python
import asyncio
from kreuzberg_surrealdb import DatabaseConfig, DocumentConnector

async def main():
    db = DatabaseConfig(db_url="mem://")

    async with DocumentConnector(db=db) as connector:
        await connector.setup_schema()
        await connector.ingest_file("report.pdf")

        results = await connector.search("quarterly revenue", limit=5)
        for r in results:
            print(r["source"], r["score"])

asyncio.run(main())
```

### Hybrid search with `DocumentPipeline`

Chunk documents, generate embeddings, and search with vector + BM25 fused via Reciprocal Rank Fusion.

```python
import asyncio
from kreuzberg_surrealdb import DatabaseConfig, DocumentPipeline

async def main():
    db = DatabaseConfig(
        db_url="ws://localhost:8000",
        namespace="myapp",
        database="knowledge_base",
        username="root",
        password="root",
    )

    async with DocumentPipeline(db=db, embed=True, embedding_model="balanced") as pipeline:
        await pipeline.setup_schema()
        await pipeline.ingest_directory("./papers", glob="**/*.pdf")

        # Hybrid search (vector + BM25 with RRF)
        results = await pipeline.search("attention mechanisms in transformers")

        # Pure vector search
        results = await pipeline.vector_search("how neural networks learn")

        # BM25 search over chunks
        results = await pipeline.fulltext_search("error code XYZ-123")

asyncio.run(main())
```

## Start Simple, Scale Up

| | `DocumentConnector` | `DocumentPipeline` |
|---|---|---|
| Stores | Full documents | Documents + chunks |
| Embeddings | No | Yes (configurable) |
| Search | BM25 full-text | BM25, vector, hybrid (RRF) |
| Best for | Keyword search on whole docs | Semantic/hybrid search on chunks |

## API Reference

### Configuration

#### `DatabaseConfig`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `db_url` | `str` | *required* | SurrealDB URL (`"mem://"`, `"ws://localhost:8000"`) |
| `namespace` | `str` | `"default"` | Database namespace |
| `database` | `str` | `"default"` | Database name |
| `username` | `str \| None` | `None` | Auth username |
| `password` | `str \| None` | `None` | Auth password |
| `table` | `str` | `"documents"` | Documents table name |
| `insert_batch_size` | `int` | `100` | Records per INSERT batch |

#### `IndexConfig`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `analyzer_language` | `str` | `"english"` | Tokenizer/stemmer language |
| `bm25_k1` | `float` | `1.2` | BM25 term saturation |
| `bm25_b` | `float` | `0.75` | BM25 length normalization |
| `distance_metric` | `str` | `"COSINE"` | Vector distance (`"COSINE"`, `"EUCLIDEAN"`) |
| `hnsw_efc` | `int` | `150` | HNSW search quality factor |
| `hnsw_m` | `int` | `12` | HNSW graph branching factor |
| `rrf_k` | `int` | `60` | RRF fusion constant |

### `DocumentConnector`

```python
DocumentConnector(*, db: DatabaseConfig, config: ExtractionConfig | None = None, index_config: IndexConfig | None = None)
```

| Method | Description |
|---|---|
| `setup_schema()` | Create documents table and BM25 index |
| `ingest_file(path)` | Extract and store a single file |
| `ingest_files(paths)` | Extract and store multiple files |
| `ingest_directory(directory, *, glob="**/*")` | Extract and store all matching files |
| `ingest_bytes(*, data, mime_type, source)` | Extract and store from raw bytes |
| `search(query, *, limit=10)` | BM25 full-text search |

### `DocumentPipeline`

```python
DocumentPipeline(*, db: DatabaseConfig, chunk_table: str = "chunks", config: ExtractionConfig | None = None,
                 embed: bool = True, embedding_model: str | EmbeddingModelType = "balanced",
                 embedding_dimensions: int | None = None, index_config: IndexConfig | None = None)
```

All `DocumentConnector` ingestion methods are available, plus:

| Method | Description |
|---|---|
| `setup_schema()` | Create documents + chunks tables with BM25 and HNSW indexes |
| `search(query, *, limit=10, quality_threshold=None)` | Hybrid search (vector + BM25 with RRF). Falls back to BM25 when `embed=False` |
| `vector_search(query, *, limit=10, quality_threshold=None)` | Pure HNSW semantic search. Requires `embed=True` |
| `fulltext_search(query, *, limit=10)` | BM25 search over chunks |

### Embedding Models

Pass a preset name (string) or an `EmbeddingModelType` directly.

**Presets** (convenient defaults):

| Preset | Model | Dimensions | Notes |
|---|---|---|---|
| `"fast"` | all-MiniLM-L6-v2 | 384 | Fastest, lowest memory |
| `"balanced"` | bge-base-en-v1.5 | 768 | Default, good quality |
| `"quality"` | bge-large-en-v1.5 | 1024 | Best English quality |
| `"multilingual"` | multilingual-e5-base | 768 | Non-English documents |

**Direct model selection** (40+ models via kreuzberg's fastembed runtime):

```python
from kreuzberg import EmbeddingModelType

# Use any supported fastembed model
pipeline = DocumentPipeline(
    db=db,
    embedding_model=EmbeddingModelType.fastembed("NomicEmbedTextV15", 768),
    embedding_dimensions=768,
)

# Use a custom ONNX model
pipeline = DocumentPipeline(
    db=db,
    embedding_model=EmbeddingModelType.custom("my-model", 512),
    embedding_dimensions=512,
)
```

## Ingestion Methods

All four methods are available on both classes:

```python
# Single file
await connector.ingest_file("report.pdf")

# Multiple files
await connector.ingest_files(["doc1.pdf", "doc2.docx", "notes.txt"])

# Directory with glob
await connector.ingest_directory("./documents", glob="**/*.pdf")

# Raw bytes (e.g., from an API response or file upload)
await connector.ingest_bytes(data=pdf_bytes, mime_type="application/pdf", source="upload://invoice.pdf")
```

## Deduplication

Documents are deduplicated by content. The SHA-256 hash of extracted text serves as the record ID. Re-ingesting the same content — even from different file paths — is a safe no-op.

```python
await connector.ingest_file("report.pdf")       # inserted
await connector.ingest_file("report.pdf")       # skipped (same content)
await connector.ingest_file("report_copy.pdf")  # skipped if content matches
```

## Quality Filtering

Kreuzberg assigns a `quality_score` (0.0–1.0) to each extraction. Use `quality_threshold` to exclude low-quality results at search time:

```python
results = await pipeline.search("budget projections", quality_threshold=0.7)
results = await pipeline.vector_search("budget projections", quality_threshold=0.7)
```

## Connection Lifecycle

Both classes support async context managers (recommended) or manual lifecycle management:

```python
# Context manager (recommended)
async with DocumentConnector(db=db) as connector:
    await connector.setup_schema()
    ...

# Manual
connector = DocumentConnector(db=db)
await connector.connect()
try:
    await connector.setup_schema()
    ...
finally:
    await connector.close()
```

## Stored Fields

Each **document** record contains: `source`, `content`, `mime_type`, `title`, `authors`, `created_at`, `ingested_at`, `metadata`, `quality_score`, `content_hash`, `detected_languages`, `keywords`.

Each **chunk** record (pipeline only) contains: `document` (record link), `content`, `chunk_index`, `embedding`, `token_count`, `page_number`, `char_start`, `char_end`, `first_page`, `last_page`.

## Development

```bash
# Install dev dependencies
uv sync

# Run unit tests
uv run pytest

# Run integration tests (uses embedded SurrealDB via mem://)
uv run pytest -m integration

# Lint and type check
uv run ruff check .
uv run mypy src/
```

## License

[MIT](LICENSE)
