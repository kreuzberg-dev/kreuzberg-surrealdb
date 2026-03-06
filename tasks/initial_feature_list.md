# kreuzberg-surrealdb: Initial Feature List

Extracted from `kreuzberg-surrealdb-pitch.md` on 2026-03-06. This is the seed document for all downstream planning and implementation tasks.

---

## 1. Core Features from Pitch

These are the features explicitly stated as required for v0.1.0 or demonstrated in the pitch's code examples.

### 1.1 Document Ingestion

- [ ] `ingest_file(path)` -- ingest a single file (any of kreuzberg's 75+ supported formats)
- [ ] `ingest_directory(path, glob)` -- batch ingest an entire directory with glob pattern filtering
- [ ] Automatic extraction via kreuzberg (PDF, DOCX, XLSX, scanned images, 75+ formats)
- [ ] Automatic chunking of extracted content (configurable strategy, size, overlap)
- [ ] Automatic local embedding generation via kreuzberg's ONNX/FastEmbed runtime
- [ ] Storage of chunks with embeddings into SurrealDB
- [ ] Storage of document-level metadata into SurrealDB
- [ ] `embed: bool = True` parameter -- embeddings are ON by default, not opt-in
- [ ] Deduplication via unique source index (`idx_doc_source` on `documents.source`)

### 1.2 Search

- [ ] `search(query, limit)` -- hybrid search (vector KNN + BM25 full-text + RRF fusion) as the default single method
- [ ] `vector_search(query, limit)` -- pure semantic/embedding-only retrieval escape hatch
- [ ] Local query embedding -- the search query is embedded locally before vector search (no API calls)
- [ ] `search::rrf()` fusion -- SurrealDB's built-in Reciprocal Rank Fusion for combining vector and keyword results
- [ ] BM25 full-text search via SurrealDB's built-in search analyzer
- [ ] HNSW vector search via SurrealDB's built-in HNSW index with cosine distance
- [ ] Configurable `limit` parameter for result count

### 1.3 Schema Management

- [ ] `setup_schema()` -- one-call automatic creation of all tables, fields, indexes, and analyzers
- [ ] No manual SurrealQL required from the user
- [ ] Schema is SCHEMAFULL (enforced types, not schemaless)

### 1.4 Connection & Configuration

- [ ] `DocumentIngester(url=...)` -- single constructor with SurrealDB connection URL
- [ ] Minimal configuration required -- URL is the only mandatory parameter
- [ ] SurrealDB authentication (signin with username/password shown in examples)
- [ ] Namespace and database selection (`db.use("rag", "documents")` pattern)

---

## 2. Design Principles

Extracted from the "Design principles" section and overall pitch philosophy.

- [ ] **Embeddings on by default** -- the zero-config path produces vectors; kreuzberg's "balanced" preset (768d, ONNX, local) works out of the box
- [ ] **Hybrid search by default** -- `search()` does vector KNN + BM25 + RRF fusion automatically; one method, smart behavior
- [ ] **Schema auto-setup** -- `setup_schema()` creates everything; no manual SQL
- [ ] **`pip install` is the entire setup** -- no `.env` with API keys, no external services beyond SurrealDB itself
- [ ] **Zero external API dependency** -- no OpenAI key, no Pinecone account, no Cohere, no network latency for embeddings
- [ ] **Two components only** -- kreuzberg (extract + chunk + embed) and SurrealDB (store + index + search)
- [ ] **Runs on a laptop** -- CPU-only, no GPU required
- [ ] **Three-method UX target** -- `setup_schema()`, `ingest_directory()`, `search()` covers the core workflow
- [ ] **Async-first** -- all examples use `async/await`; the connector is natively async
- [ ] **Composable** -- works standalone but also composable with LangChain/LlamaIndex on top if users want

---

## 3. Schema Features

### 3.1 `documents` Table

- [ ] `source` field -- `TYPE string`, file path or identifier of the original document
- [ ] `content` field -- `TYPE string`, full extracted text content of the document
- [ ] `mime_type` field -- `TYPE string`, MIME type of the original file
- [ ] `title` field -- `TYPE option<string>`, extracted document title (optional)
- [ ] `authors` field -- `TYPE option<array<string>>`, extracted author list (optional)
- [ ] `created_at` field -- `TYPE option<datetime>`, original document creation timestamp (optional)
- [ ] `ingested_at` field -- `TYPE datetime DEFAULT time::now()`, auto-set ingestion timestamp
- [ ] `metadata` field -- `TYPE object FLEXIBLE`, catch-all flexible metadata object for arbitrary key-value pairs
- [ ] `quality_score` field -- `TYPE option<float>`, kreuzberg's extraction quality assessment
- [ ] `detected_languages` field -- `TYPE option<array<string>>`, languages detected in the document
- [ ] `keywords` field -- `TYPE option<array<object>>`, extracted keywords (via YAKE/RAKE)

### 3.2 `chunks` Table

- [ ] `document` field -- `TYPE record<documents>`, foreign-key-like reference linking chunk to parent document
- [ ] `content` field -- `TYPE string`, the chunk text content
- [ ] `embedding` field -- `TYPE option<array<float>>`, the vector embedding (optional to allow embedding-disabled mode)
- [ ] `chunk_index` field -- `TYPE int`, ordinal position of the chunk within its parent document
- [ ] `page_number` field -- `TYPE option<int>`, page number the chunk originated from (if applicable)
- [ ] `char_start` field -- `TYPE option<int>`, character offset start position within the original document
- [ ] `char_end` field -- `TYPE option<int>`, character offset end position within the original document

### 3.3 Indexes

- [ ] `idx_chunk_embedding` -- HNSW vector index on `chunks.embedding`, DIMENSION 768, DIST COSINE
- [ ] `idx_chunk_content` -- BM25 full-text search index on `chunks.content` using custom analyzer
- [ ] `idx_doc_source` -- UNIQUE index on `documents.source` for dedup and fast source lookup
- [ ] `chunk_analyzer` -- custom analyzer with `class` tokenizer, `lowercase` filter, and `snowball(english)` stemmer

### 3.4 Schema Configuration

- [ ] Configurable embedding dimension (768 default for "balanced" preset, but must support 384-1024 range)
- [ ] Configurable distance metric (COSINE is default, but schema should allow alternatives)
- [ ] SCHEMAFULL enforcement on both tables

---

## 4. Search Features

### 4.1 Hybrid Search (Default)

- [ ] Combines vector KNN similarity search with BM25 keyword/full-text search
- [ ] Uses SurrealDB's native `search::rrf()` for Reciprocal Rank Fusion
- [ ] Single `search()` method exposes this as the default behavior
- [ ] Returns results ranked by fused score

### 4.2 Vector Search (Pure Semantic)

- [ ] Dedicated `vector_search()` method for embedding-only retrieval
- [ ] HNSW approximate nearest neighbor search
- [ ] Cosine distance metric
- [ ] Query string is embedded locally before search

### 4.3 Full-Text Search (BM25)

- [ ] BM25 scoring via SurrealDB's built-in search engine
- [ ] Custom analyzer: class tokenizer + lowercase filter + snowball(english) stemmer
- [ ] Participates in hybrid search via RRF fusion

### 4.4 Search Result Format

- [ ] Results include `content` field (chunk text) for direct LLM context injection
- [ ] Results are list/array of dict-like objects (shown as `r["content"]` in examples)
- [ ] Configurable result limit

---

## 5. Ingestion Features

### 5.1 Document Extraction

- [ ] 75+ file format support via kreuzberg's Rust core
- [ ] PDF extraction (including scanned PDFs via OCR)
- [ ] DOCX extraction
- [ ] XLSX extraction
- [ ] Scanned image extraction (OCR)
- [ ] Markdown output format from extraction (`output_format="markdown"`)
- [ ] 10-50x faster than traditional parsing libraries (kreuzberg's Rust core)

### 5.2 Chunking

- [ ] Semantic chunking strategy (`strategy="semantic"`)
- [ ] Configurable `chunk_size` (512 shown in example)
- [ ] Configurable `chunk_overlap` (64 shown in example)
- [ ] Chunk index tracking (ordinal position preserved)
- [ ] Page number tracking per chunk (when available)
- [ ] Character offset tracking per chunk (start and end positions)

### 5.3 Embedding

- [ ] Local ONNX runtime execution -- no API calls, no network latency
- [ ] FastEmbed model support (384d to 1024d models)
- [ ] "balanced" preset as default (768-dimensional vectors)
- [ ] CPU-only execution -- no GPU required
- [ ] Zero-cost embeddings ($0 vs $0.10-$0.50 per 1M tokens for API-based)

### 5.4 Batch Processing

- [ ] Directory-level ingestion with glob patterns (`glob="**/*.pdf"`)
- [ ] Batch pipeline capability (referenced as `batch_pipeline.py` example)
- [ ] Scale handling for multiple documents

---

## 6. Metadata & Enrichment

### 6.1 Kreuzberg-Extracted Metadata

- [ ] `quality_score` -- extraction quality assessment (float), signals document reliability for downstream ranking
- [ ] `detected_languages` -- language detection results (array of language codes)
- [ ] `keywords` -- keyword extraction via YAKE/RAKE algorithms (array of keyword objects)
- [ ] `title` -- document title extraction
- [ ] `authors` -- author list extraction
- [ ] `created_at` -- original document creation date extraction

### 6.2 System Metadata

- [ ] `ingested_at` -- automatic timestamp of when the document was processed
- [ ] `mime_type` -- MIME type of the source file
- [ ] `source` -- file path or identifier of the original document
- [ ] `metadata` -- flexible object for arbitrary additional metadata

### 6.3 Chunk-Level Metadata

- [ ] `chunk_index` -- position of chunk within document (ordering)
- [ ] `page_number` -- source page number (when applicable)
- [ ] `char_start` / `char_end` -- character offset positions within original document
- [ ] `document` -- record link back to parent document (SurrealDB record reference)

---

## 7. Integration Features

### 7.1 Package Distribution

- [ ] Published on PyPI as `kreuzberg-surrealdb`
- [ ] Installable via `pip install kreuzberg-surrealdb`
- [ ] Listed on SurrealDB integrations page (`surrealdb.com/docs/integrations`)
- [ ] Versioned with semver guarantees
- [ ] CI-tested to catch breakages on dependency updates

### 7.2 Dependency Management

- [ ] Only two runtime dependencies: `kreuzberg` and `surrealdb` (Python SDK)
- [ ] No OpenAI SDK dependency
- [ ] No Pinecone/Weaviate/Qdrant client dependency
- [ ] No separate embedding provider package required
- [ ] Shows in `pip list`, `uv tree`, GitHub dependency graphs

### 7.3 Composability with Ecosystem

- [ ] Works standalone as a complete RAG pipeline
- [ ] Composable with LangChain on top (users can layer orchestration)
- [ ] Composable with LlamaIndex on top
- [ ] Sits alongside existing kreuzberg integrations: `langchain-kreuzberg`, `kreuzberg-haystack`
- [ ] Positions kreuzberg across three paradigms: framework orchestrators, AI-native databases, cloud platforms

### 7.4 SurrealDB Compatibility

- [ ] WebSocket connection (`ws://localhost:8000/rpc`)
- [ ] SurrealDB authentication (signin)
- [ ] Namespace and database selection
- [ ] Uses SurrealDB Python SDK (`surrealdb` package)
- [ ] Leverages SurrealDB-native features: HNSW, BM25, `search::rrf()`, `record<>` types, SCHEMAFULL tables

### 7.5 LLM Agnosticism

- [ ] Results designed for feeding to any LLM (context string assembly shown in examples)
- [ ] No LLM provider lock-in -- connector handles retrieval, user chooses generation
- [ ] Clean `content` field extraction for context window assembly

---

## 8. Ambitious Stretch Features (v0.2.0+ / Future)

These are hinted at or explicitly mentioned as future work in the pitch.

### 8.1 Graph Features (SurrealDB Native Edges)

- [ ] `RELATE` edges between documents/chunks -- leverage SurrealDB's native graph capabilities
- [ ] Keyword graph -- graph edges based on shared keywords between documents/chunks
- [ ] Table entities -- structured entity extraction stored as graph nodes
- [ ] GraphRAG architecture -- "Tier 2 architecture" combining vector retrieval with graph traversal

### 8.2 Concept Graphs

- [ ] Concept graph construction from extracted keywords and entities
- [ ] Cross-document concept linking
- [ ] Graph-enhanced retrieval (traversing concept relationships to find related content)

### 8.3 Advanced Search (Implied)

- [ ] Filtered search (metadata-based filtering combined with vector/hybrid search)
- [ ] Re-ranking capabilities
- [ ] Search with score return (`similarity_search_with_score()` mentioned as a pattern from `langchain-surrealdb`)
- [ ] `as_retriever()` interface (mentioned as LangChain pattern that could be adopted)

### 8.4 Advanced Ingestion (Implied)

- [ ] Incremental ingestion (detect changed files, skip unchanged)
- [ ] Document update/re-ingestion (replace chunks when source document changes)
- [ ] Parallel/concurrent ingestion for large directories
- [ ] Progress reporting during batch ingestion

### 8.5 Schema Evolution

- [ ] Migration support as schema changes between versions
- [ ] Custom table/field naming
- [ ] Multi-language analyzer support (snowball currently only configured for English)
- [ ] Additional distance metrics beyond cosine (euclidean, manhattan, etc.)

### 8.6 Ecosystem Expansion (Implied from Strategic Rationale)

- [ ] Wikidata/ontology enrichment for extracted entities
- [ ] Integration with kreuzberg-cloud for managed deployments
- [ ] SurrealDB Cloud compatibility (not just local/self-hosted)

---

## 9. Examples & Documentation (Phase 1 Deliverables)

These are the example scripts planned for the `surrealdb.py` examples PR.

- [ ] `basic_ingest.py` -- extract a single PDF, store in SurrealDB (the 30-line demo)
- [ ] `vector_search.py` -- embed a query locally, perform HNSW search
- [ ] `hybrid_search.py` -- vector + BM25 fusion search demonstration
- [ ] `batch_pipeline.py` -- directory-level ingestion at scale
- [ ] `README.md` -- documentation for the examples directory
- [ ] `requirements.txt` -- minimal dependency list (kreuzberg, surrealdb)

---

## 10. Anti-Features (Explicit Non-Goals)

These are things the pitch explicitly positions as unnecessary or excluded.

- [ ] No OpenAI API key required
- [ ] No Pinecone/Weaviate/Qdrant account required
- [ ] No separate embedding service (Ollama, etc.) required
- [ ] No GPU required
- [ ] No `docker-compose.yml` with 5+ services
- [ ] No `.env` file with API keys
- [ ] No paid API for document parsing (vs. LlamaParse)
- [ ] No spaCy/transformers/pandas heavyweight dependencies (vs. existing `surrealdb-rag` example)
- [ ] No manual schema SQL from the user
- [ ] No copy-paste from examples -- installable package instead

---

## Summary Statistics

| Category | Item Count |
|---|---|
| Core Ingestion Features | 9 |
| Core Search Features | 7 |
| Schema Fields (documents) | 11 |
| Schema Fields (chunks) | 7 |
| Schema Indexes | 4 |
| Search Modes | 3 (hybrid, vector, full-text) |
| Metadata Fields | 14 |
| Integration Features | 17 |
| Stretch Features | 18 |
| Example Scripts | 6 |
| Anti-Features | 10 |
| **Total Feature Items** | **~106** |
