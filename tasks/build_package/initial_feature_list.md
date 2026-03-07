# kreuzberg-surrealdb: Initial Feature List

Extracted from `kreuzberg-surrealdb-pitch.md` on 2026-03-06. This is the seed document for all downstream planning and implementation tasks.

> `[x]` = covered in `tasks/design-decisions/`
> `[ ]` = not yet covered (stretch, task, or inherent)

---

## 1. Core Features from Pitch

### 1.1 Document Ingestion

- [x] `ingest_file(path)` -- D7: on _BaseIngester, both classes
- [x] `ingest_directory(path, glob)` -- D7: on _BaseIngester, both classes
- [x] Automatic extraction via kreuzberg (PDF, DOCX, XLSX, scanned images, 75+ formats) -- D11: kreuzberg >=4.4.3 core dep
- [x] Automatic chunking of extracted content (configurable strategy, size, overlap) -- D15: delegated to kreuzberg's ChunkingConfig
- [x] Automatic local embedding generation via ONNX/FastEmbed runtime -- D11: fastembed >=0.7.4 core dep
- [x] Storage of chunks with embeddings into SurrealDB -- D18: chunks table with embedding field
- [x] Storage of document-level metadata into SurrealDB -- D17: documents table (12 fields)
- [x] `embed: bool = True` parameter -- D16: top-level on DocumentPipeline constructor
- [x] Deduplication via unique source index -- D19: idx_doc_source (UNIQUE) + idx_doc_hash (UNIQUE)

### 1.2 Search

- [x] `search(query, limit)` -- hybrid search as default -- D10: DocumentPipeline.search() = hybrid
- [x] `vector_search(query, limit)` -- pure semantic retrieval -- D2: only on DocumentPipeline
- [x] Local query embedding -- D11: fastembed handles query-time embedding locally
- [x] `search::rrf()` fusion -- D14: IndexConfig.rrf_k configurable
- [x] BM25 full-text search via SurrealDB analyzer -- D19: idx_chunk_content, chunk_analyzer
- [x] HNSW vector search with cosine distance -- D19: idx_chunk_embedding; D14: distance_metric="COSINE"
- [x] Configurable `limit` parameter -- D2: `limit: int = 10` on all search methods

### 1.3 Schema Management

- [x] `setup_schema()` -- one-call creation of tables, fields, indexes, analyzers -- D20
- [x] No manual SurrealQL required -- D20: setup_schema() handles everything
- [x] Schema is SCHEMAFULL -- D17: metadata uses `object FLEXIBLE` within SCHEMAFULL

### 1.4 Connection & Configuration

- [x] Single constructor with connection URL -- D13: `DatabaseConfig(db_url=...)`. **Changed**: class renamed from `DocumentIngester` to `DocumentConnector` / `DocumentPipeline` (D1, D2)
- [x] Minimal configuration -- URL is only mandatory param -- D13: all other fields have defaults
- [x] SurrealDB authentication -- D13: username/password in DatabaseConfig
- [x] Namespace and database selection -- D3: "default"/"default"; D13: configurable in DatabaseConfig

---

## 2. Design Principles

- [x] **Embeddings on by default** -- D16: `embed: bool = True` on DocumentPipeline
- [x] **Hybrid search by default** -- D10: DocumentPipeline.search() does hybrid
- [x] **Schema auto-setup** -- D20: setup_schema() creates everything
- [x] **`pip install` is the entire setup** -- D11: all deps are core, always installed
- [x] **Zero external API dependency** -- D11: fastembed is local ONNX, no API keys
- [x] **Three-method UX target** -- D20: setup_schema(), D7: ingest_directory(), D10: search()
- [x] **Async-first** -- D2: all methods are `async def`

---

## 3. Schema Features

### 3.1 `documents` Table

- [x] `source` -- D17
- [x] `content` -- D17
- [x] `mime_type` -- D17
- [x] `title` -- D17
- [x] `authors` -- D17
- [x] `created_at` -- D17
- [x] `ingested_at` -- D17
- [x] `metadata` (FLEXIBLE) -- D17
- [x] `quality_score` -- D17
- [x] `detected_languages` -- D17
- [x] `keywords` -- D17

### 3.2 `chunks` Table

- [x] `document` (record link) -- D18
- [x] `content` -- D18
- [x] `embedding` -- D18
- [x] `chunk_index` -- D18
- [x] `page_number` -- D18
- [x] `char_start` -- D18
- [x] `char_end` -- D18

### 3.3 Indexes

- [x] `idx_chunk_embedding` -- HNSW on chunks.embedding -- D19
- [x] `idx_chunk_content` -- BM25 on chunks.content -- D19
- [x] `idx_doc_source` -- UNIQUE on documents.source -- D19
- [x] `chunk_analyzer` -- custom analyzer with snowball stemmer -- D19, D14: analyzer_language

### 3.4 Schema Configuration

- [x] Configurable embedding dimension -- D15: via kreuzberg's EmbeddingConfig (model choice determines dimension)
- [x] Configurable distance metric -- D14: IndexConfig.distance_metric
- [x] SCHEMAFULL enforcement -- D17: explicit in schema design

---

## 4. Search Features

### 4.1 Hybrid Search (Default)

- [x] Combines vector KNN + BM25 -- D10: DocumentPipeline.search()
- [x] Uses SurrealDB's `search::rrf()` -- D14: rrf_k configurable
- [x] Single `search()` method as default -- D10
- [x] Results ranked by fused score -- D10: implicit in hybrid implementation

### 4.2 Vector Search (Pure Semantic)

- [x] Dedicated `vector_search()` method -- D2: only on DocumentPipeline
- [x] HNSW approximate nearest neighbor -- D19: idx_chunk_embedding
- [x] Cosine distance metric -- D14: distance_metric="COSINE" default
- [x] Query embedded locally -- D11: fastembed

### 4.3 Full-Text Search (BM25)

- [x] BM25 scoring via SurrealDB -- D19: BM25 indexes; D14: bm25_k1, bm25_b
- [x] Custom analyzer: tokenizer + snowball stemmer -- D19: chunk_analyzer; D14: analyzer_language
- [x] Participates in hybrid search via RRF -- D10, D14

### 4.4 Search Result Format

- [x] Results include `content` field -- D18: chunks.content
- [x] Results are list of dict -- D2: return type `list[dict]`
- [x] Configurable result limit -- D2: `limit: int = 10`

---

## 5. Ingestion Features

### 5.1 Document Extraction

- [x] 75+ file format support via kreuzberg -- D11: kreuzberg >=4.4.3
- [x] PDF extraction (including scanned/OCR) -- D11, D6: ExtractionConfig for OCR backend
- [x] DOCX extraction -- D11
- [x] XLSX extraction -- D11
- [x] Scanned image extraction (OCR) -- D6: via ExtractionConfig
- [x] Markdown output format -- D5+D6: via ExtractionConfig (not top-level param)

### 5.2 Chunking

- [x] Semantic chunking strategy -- D15: via ChunkingConfig.chunker_type
- [x] Configurable `chunk_size` -- D15: via ChunkingConfig.max_chars (default 1000)
- [x] Configurable `chunk_overlap` -- D15: via ChunkingConfig.max_overlap (default 200)
- [x] Chunk index tracking -- D18: chunk_index field
- [x] Page number tracking -- D18: page_number field
- [x] Character offset tracking -- D18: char_start, char_end fields

### 5.3 Embedding

- [x] Local ONNX runtime -- D11: fastembed
- [x] FastEmbed model support (384d-1024d) -- D11, D15: via EmbeddingConfig
- [x] "balanced" preset as default -- D15: via kreuzberg's ChunkingConfig.preset
- [x] CPU-only execution -- D11: fastembed is CPU-native

### 5.4 Batch Processing

- [x] Directory-level ingestion with glob -- D7: ingest_directory(dir, glob)
- [x] Batch pipeline capability -- D7: ingest_files(paths) for explicit lists
- [x] Scale handling for multiple documents -- D13: insert_batch_size in DatabaseConfig

---

## 6. Metadata & Enrichment

### 6.1 Kreuzberg-Extracted Metadata

- [x] `quality_score` -- D17
- [x] `detected_languages` -- D17
- [x] `keywords` -- D17
- [x] `title` -- D17
- [x] `authors` -- D17
- [x] `created_at` -- D17

### 6.2 System Metadata

- [x] `ingested_at` -- D17
- [x] `mime_type` -- D17
- [x] `source` -- D17
- [x] `metadata` (flexible) -- D17

### 6.3 Chunk-Level Metadata

- [x] `chunk_index` -- D18
- [x] `page_number` -- D18
- [x] `char_start` / `char_end` -- D18
- [x] `document` (record link) -- D18

---

## 7. Integration Features

### 7.1 Package Distribution

- [x] Published on PyPI as `kreuzberg-surrealdb` -- Phase 2 task in todo.md
- [x] CI-tested to catch breakages -- Phase 2 task in todo.md

### 7.2 Dependency Management

- [x] Runtime dependencies defined -- D11: kreuzberg >=4.4.3, surrealdb >=1.0.8, fastembed >=0.7.4
- [x] No OpenAI SDK dependency -- D11: no external API deps
- [x] No Pinecone/Weaviate/Qdrant dependency -- D11
- [x] No separate embedding provider -- D11: fastembed bundled

### 7.3 SurrealDB Compatibility

- [x] WebSocket connection -- D13: db_url accepts ws://
- [x] SurrealDB authentication -- D13: username/password
- [x] Namespace and database selection -- D3, D13
- [x] Uses SurrealDB Python SDK -- D11: surrealdb >=1.0.8
- [x] Leverages SurrealDB-native features (HNSW, BM25, RRF, record<>, SCHEMAFULL) -- D14, D17, D18, D19

---

## 8. Promoted Stretch Features (now in v0.1.0)

- [x] Custom table/field naming -- D4: moved to v0.1.0
- [x] Multi-language analyzer support -- D14: IndexConfig.analyzer_language
- [x] Additional distance metrics beyond cosine -- D14: IndexConfig.distance_metric

> Remaining stretch features moved to `tasks/feature-lists/stretch_features.md`

---

## 9. Examples & Documentation (Phase 2 Deliverables)

- [x] `basic_ingest.py` -- Phase 2 task in todo.md
- [x] `vector_search.py` -- Phase 2 task in todo.md
- [x] `hybrid_search.py` -- Phase 2 task in todo.md
- [x] `batch_pipeline.py` -- Phase 2 task in todo.md
- [x] `README.md` -- Phase 2 task in todo.md
- [x] `requirements.txt` -- not needed, deps in pyproject.toml

---

## 10. Anti-Features (Explicit Non-Goals)

- [x] No OpenAI API key required -- D11
- [x] No Pinecone/Weaviate/Qdrant account required -- D11
- [x] No separate embedding service required -- D11: fastembed bundled
- [x] No .env file with API keys -- D11: no external APIs
- [x] No manual schema SQL from user -- D20: setup_schema()

---

## Summary Statistics

| Category | Total | Covered |
|---|---|---|
| Core Features from Pitch | 23 | 23 |
| Design Principles | 7 | 7 |
| Schema Features | 25 | 25 |
| Search Features | 14 | 14 |
| Ingestion Features | 19 | 19 |
| Metadata & Enrichment | 14 | 14 |
| Integration Features | 11 | 11 |
| Promoted Stretch Features | 3 | 3 |
| Examples & Docs | 6 | 6 |
| Anti-Features | 5 | 5 |
| **Total** | **127** | **127** |
