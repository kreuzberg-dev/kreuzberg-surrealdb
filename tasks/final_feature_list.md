# kreuzberg-surrealdb: Final Feature List

> Confirmed features only. Generated from pitch analysis, capability combination analysis, and API verification.
> Date: 2026-03-06
> Sources: initial_feature_list.md (106 items), potential_features_from_indices.md (80 items), feature_verification.md (verification verdicts)

---

## Key Architectural Decisions

### 1. Query-Time Embedding Strategy
kreuzberg has no standalone `embed_text()` function. Embeddings are generated only during chunking as part of `extract_file()`.
- **Decision**: Depend on `fastembed` directly for query-time embedding. FastEmbed is already a transitive dependency of kreuzberg. Using it directly avoids the overhead of kreuzberg's full extraction pipeline for a single query string.
- **Impact**: Adds `fastembed` as a direct (not just transitive) dependency. The connector must maintain model name parity between the kreuzberg embedding preset used at ingestion time and the FastEmbed model used at query time.

### 2. SurrealDB Server Version Target
The Python SDK v2.0.0a1 targets SurrealDB server v2.0.0 - v2.3.6. SurrealDB v3.0 introduced breaking syntax changes.
- **Decision**: Target SurrealDB v2.x for the initial release. Use `SEARCH ANALYZER` syntax (not v3.0's `FULLTEXT ANALYZER`). No file storage buckets.
- **Impact**: File/image storage buckets are excluded. Full-text index syntax must use `SEARCH ANALYZER`. Support v3.0 syntax as a future configuration option.

### 3. Hybrid Search Implementation
Three queries are required for hybrid search: vector, full-text, and RRF fusion.
- **Decision**: Use multi-statement SurrealQL with LET bindings in a single `db.query()` call: `LET $vs = (SELECT ...); LET $ft = (SELECT ...); SELECT * FROM search::rrf([$vs, $ft], $limit, 60)`.
- **Impact**: Single round-trip to the database. Requires verifying that multi-statement queries with LET bindings work correctly through the Python SDK.

### 4. HNSW In-Memory Limitation
HNSW indexes are currently in-memory structures in SurrealDB. The index is rebuilt on server restart and memory usage scales linearly with vector count.
- **Decision**: Document this limitation prominently. Recommend sufficient server memory for production deployments. Monitor SurrealDB roadmap for persistent HNSW.
- **Impact**: Large datasets (millions of vectors) may cause memory pressure. Users must plan server resources accordingly.

---

## v0.1.0 -- Core Release

### Connection & Setup

- [CONFIRMED] **SurrealDB Connection** -- Connect to SurrealDB via WebSocket URL with authentication.
  - Kreuzberg: N/A
  - SurrealDB: `AsyncSurreal(url)`, `db.signin({"username": ..., "password": ...})`, `db.use(namespace, database)`
  - Notes: WebSocket (`ws://`) is the primary connection mode. HTTP and embedded also supported.

- [CONFIRMED] **Embedded Database Mode** -- In-memory or file-backed SurrealDB for testing and development with no external server.
  - Kreuzberg: N/A
  - SurrealDB: `Surreal("memory")`, `AsyncSurreal("memory")`, `Surreal("file://path")`. Full API parity with WebSocket/HTTP.
  - Notes: Transactions are NOT supported in embedded mode (WebSocket only). HNSW in-memory nature makes embedded mode a natural fit for development.

- [CONFIRMED] **Automatic Schema Setup** -- Single `setup_schema()` call creates all tables, fields, indexes, and analyzers. No manual SurrealQL required.
  - Kreuzberg: `get_embedding_preset(name).dimensions` to determine vector dimension
  - SurrealDB: `db.query()` executing `DEFINE TABLE`, `DEFINE FIELD`, `DEFINE INDEX`, `DEFINE ANALYZER` statements
  - Notes: Schema is SCHEMAFULL (enforced types). Configurable embedding dimension (384-1024), distance metric (COSINE default).

- [CONFIRMED] **Embedding Preset to Index Configuration Mapping** -- Automatically map kreuzberg embedding presets to HNSW index dimensions.
  - Kreuzberg: `list_embedding_presets()`, `get_embedding_preset(name)` returning `EmbeddingPreset` with `.dimensions`
  - SurrealDB: `DEFINE INDEX ... HNSW DIMENSION {n}` where n comes from the preset
  - Notes: Presets: "balanced" (768d), "compact" (384d), "large" (1024d). Also supports `EmbeddingModelType.fastembed(model, dimensions)` for custom models.

### Document Ingestion

- [CONFIRMED] **Universal Document Ingestion Pipeline** -- Single `ingest_file(path)` call extracts text from any of 75+ supported formats and stores the result in SurrealDB.
  - Kreuzberg: `extract_file(path, config=...)` async / `extract_file_sync(path, config=...)` sync. Returns `ExtractionResult` with `.content`, `.mime_type`, `.metadata`, `.tables`, `.quality_score`, `.detected_languages`, `.chunks`, `.extracted_keywords`.
  - SurrealDB: `db.create("documents", {...})` or `db.insert("documents", [records])`
  - Notes: MIME auto-detection eliminates format-specific branches. Supports PDF, DOCX, XLSX, PPTX, EML, EPUB, HTML, Markdown, images, archives, etc.

- [CONFIRMED] **Directory Batch Ingestion** -- `ingest_directory(path, glob)` ingests an entire directory with glob pattern filtering.
  - Kreuzberg: `batch_extract_files(paths, config=...)` async / `batch_extract_files_sync(paths, config=...)` sync. Uses Rust rayon for parallelism. `ExtractionConfig.max_concurrent_extractions` limits concurrency.
  - SurrealDB: `db.insert("documents", [records])` for bulk insert, `db.insert("chunks", [records])` for bulk chunk insert
  - Notes: Pipeline: batch extract -> collect results -> batch insert documents -> batch insert chunks. Consider chunking SurrealDB inserts into batches of 100-500 records. Must handle partial failures (some files may fail extraction while others succeed).

- [CONFIRMED] **Document Deduplication** -- Skip re-ingestion of identical documents via unique source index and content hashing.
  - Kreuzberg: Extraction is deterministic. Connector hashes raw file bytes using `hashlib.sha256()`.
  - SurrealDB: `DEFINE INDEX idx_doc_source ON documents FIELDS source UNIQUE`. `DEFINE INDEX idx_doc_hash ON documents FIELDS content_hash UNIQUE`. `AlreadyExistsError` on duplicate.
  - Notes: Hash file bytes before extraction for efficiency (skip extraction entirely if hash matches). Near-duplicate detection (different formatting, same content) is out of scope.

### Chunking & Embeddings

- [CONFIRMED] **Automatic Chunking with Metadata** -- Extract, chunk, and store with configurable strategy, size, and overlap. Each chunk retains positional metadata.
  - Kreuzberg: `ChunkingConfig(max_chars=1000, max_overlap=200, embedding=EmbeddingConfig(...))`. `ChunkMetadata` provides `byte_start`, `byte_end`, `chunk_index`, `total_chunks`, `token_count`, `first_page`, `last_page`.
  - SurrealDB: `db.create("chunks", {...})` with fields: `document` (record link), `content`, `embedding`, `chunk_index`, `page_number`, `char_start`, `char_end`, `token_count`
  - Notes: Semantic chunking strategy available (`strategy="semantic"`). Configurable `chunk_size` (512 default) and `chunk_overlap` (64 default).

- [CONFIRMED] **Local Embedding Generation** -- Zero-cost, fully local embedding pipeline using ONNX/FastEmbed. No API keys, no network, no GPU required.
  - Kreuzberg: `ChunkingConfig(embedding=EmbeddingConfig(model=EmbeddingModelType.preset("balanced")))`. FastEmbed ONNX models run in Rust. `Chunk.embedding` is `list[float]`.
  - SurrealDB: `list[float]` maps to `array<float>` field. HNSW index on the embedding field.
  - Notes: CPU-only execution. "balanced" preset produces 768-dimensional vectors. Models range from 384d to 1024d.

- [CONFIRMED] **HNSW Vector Index on Chunks** -- Store chunk embeddings with an HNSW approximate nearest neighbor index for fast vector search.
  - Kreuzberg: `Chunk.embedding: list[float]`
  - SurrealDB: `DEFINE INDEX idx_chunk_embedding ON chunks FIELDS embedding HNSW DIMENSION 768 DIST COSINE`. Parameters: DIMENSION (required), DIST (COSINE/EUCLIDEAN/MANHATTAN), TYPE (F64), EFC (150), M (12).
  - Notes: HNSW is in-memory. Performance may degrade with very large datasets. Persistence behavior across restarts needs documentation.

- [CONFIRMED] **Full-Text Index on Chunk Content** -- BM25 full-text search index with custom analyzer for keyword retrieval.
  - Kreuzberg: `Chunk.content: str`
  - SurrealDB: `DEFINE ANALYZER chunk_analyzer TOKENIZERS class FILTERS lowercase, snowball(english)`. `DEFINE INDEX idx_chunk_content ON chunks FIELDS content SEARCH ANALYZER chunk_analyzer BM25(1.2, 0.75) HIGHLIGHTS`.
  - Notes: Uses `SEARCH ANALYZER` syntax for SurrealDB v2.x. Combined with HNSW vector index, this enables hybrid search on the same table.

- [CONFIRMED] **Configurable Embed Toggle** -- `embed: bool = True` parameter makes embeddings on by default but allows disabling for text-only storage.
  - Kreuzberg: `ChunkingConfig` with or without `embedding=EmbeddingConfig(...)`
  - SurrealDB: `DEFINE FIELD embedding ON chunks TYPE option<array<float>>` (option type permits null)
  - Notes: When disabled, chunks are stored without embeddings. Vector search is unavailable but BM25 full-text search still works.

### Search

- [CONFIRMED] **Hybrid Search (Vector + BM25 + RRF)** -- Default `search(query, limit)` method combining vector KNN, BM25 full-text, and Reciprocal Rank Fusion.
  - Kreuzberg: Provides embeddings (vector search) and text content (BM25)
  - SurrealDB: Multi-statement query: (1) `LET $vs = (SELECT id, content, vector::distance::knn() AS distance FROM chunks WHERE embedding <|K, COSINE|> $query_vec ORDER BY distance)`, (2) `LET $ft = (SELECT id, content, search::score(0) AS score FROM chunks WHERE content @0@ $query ORDER BY score DESC)`, (3) `SELECT * FROM search::rrf([$vs, $ft], $limit, 60)`. Both result sets MUST include `id` for RRF stitching.
  - Notes: This is the headline feature. Implemented as a single multi-statement `db.query()` call for efficiency. The `k` parameter in RRF (default 60) is configurable.

- [CONFIRMED] **Pure Vector Search** -- Dedicated `vector_search(query, limit)` method for embedding-only semantic retrieval.
  - Kreuzberg: N/A (query embedding via FastEmbed directly)
  - SurrealDB: `SELECT *, vector::distance::knn() AS distance FROM chunks WHERE embedding <|K, COSINE|> $query_vec ORDER BY distance LIMIT $limit`
  - Notes: Query string is embedded locally before search using FastEmbed. HNSW approximate nearest neighbor with cosine distance.

- [PARTIAL] **Query-Time Embedding** -- Embed the search query string locally before vector search.
  - Kreuzberg: No standalone `embed_text()` API. Embeddings are only generated during chunking.
  - SurrealDB: KNN search requires a pre-computed query vector.
  - Caveat: kreuzberg does not expose a standalone text embedding function.
  - Workaround: Use FastEmbed's `TextEmbedding` class directly as a peer dependency. The connector maintains model name parity between ingestion-time preset and query-time FastEmbed model.

- [CONFIRMED] **BM25 Full-Text Search** -- Standalone keyword search using SurrealDB's built-in BM25 scoring.
  - Kreuzberg: N/A
  - SurrealDB: `SELECT *, search::score(0) AS score FROM chunks WHERE content @0@ $query ORDER BY score DESC LIMIT $limit`
  - Notes: Uses the custom analyzer with class tokenizer, lowercase filter, and snowball(english) stemmer.

- [CONFIRMED] **Configurable Result Limit** -- All search methods accept a `limit` parameter controlling how many results to return.
  - Kreuzberg: N/A
  - SurrealDB: `LIMIT $limit` clause in queries
  - Notes: Sensible default (e.g., 10). Exposed as a parameter on all search methods.

- [CONFIRMED] **Search Result Format** -- Results returned as list of dict-like objects with `content` field for direct LLM context injection.
  - Kreuzberg: N/A
  - SurrealDB: Query results as list of records with named fields
  - Notes: Each result includes at minimum: `content` (chunk text), `document` (parent reference), `chunk_index`, and relevance score. Designed for `r["content"]` access pattern.

### Schema & Storage

- [CONFIRMED] **Documents Table (SCHEMAFULL)** -- Stores document-level data with enforced types.
  - Kreuzberg: `ExtractionResult` fields
  - SurrealDB: `DEFINE TABLE documents SCHEMAFULL` with fields: `source` (string), `content` (string), `mime_type` (string), `title` (option\<string\>), `authors` (option\<array\<string\>\>), `created_at` (option\<datetime\>), `ingested_at` (datetime, DEFAULT time::now()), `metadata` (object FLEXIBLE), `quality_score` (option\<float\>), `detected_languages` (option\<array\<string\>\>), `keywords` (option\<array\<object\>\>), `content_hash` (string)
  - Notes: Common metadata fields at top level for indexing/filtering. Format-specific metadata in nested `metadata` FLEXIBLE object.

- [CONFIRMED] **Chunks Table (SCHEMAFULL)** -- Stores chunk-level data with record link to parent document.
  - Kreuzberg: `Chunk` and `ChunkMetadata` fields
  - SurrealDB: `DEFINE TABLE chunks SCHEMAFULL` with fields: `document` (record\<documents\>), `content` (string), `embedding` (option\<array\<float\>\>), `chunk_index` (int), `page_number` (option\<int\>), `char_start` (option\<int\>), `char_end` (option\<int\>), `token_count` (option\<int\>), `first_page` (option\<int\>), `last_page` (option\<int\>)
  - Notes: Record link (`record<documents>`) enables traversal from chunk to parent document.

- [CONFIRMED] **Index Definitions** -- Three indexes and one custom analyzer created during schema setup.
  - Kreuzberg: N/A
  - SurrealDB: `idx_chunk_embedding` (HNSW on embedding), `idx_chunk_content` (BM25 on content), `idx_doc_source` (UNIQUE on documents.source), `chunk_analyzer` (class tokenizer + lowercase + snowball(english))
  - Notes: `idx_doc_source` prevents duplicate document ingestion. `chunk_analyzer` configures stemming and tokenization for BM25.

- [CONFIRMED] **Chunk Page Range for Citation** -- Store first and last page numbers per chunk for precise source citation.
  - Kreuzberg: `ChunkMetadata.first_page: int`, `ChunkMetadata.last_page: int`
  - SurrealDB: `DEFINE FIELD first_page ON chunks TYPE option<int>`, `DEFINE FIELD last_page ON chunks TYPE option<int>`
  - Notes: Essential for RAG citation: "Source: document.pdf, pages 5-7." Not all formats have page numbers (text files, HTML).

### Metadata & Enrichment

- [CONFIRMED] **Rich Metadata Record Storage** -- Store kreuzberg's full metadata extraction output including format-specific fields.
  - Kreuzberg: `ExtractionResult.metadata` TypedDict with common fields (title, subject, authors, keywords, language, created_at, modified_at) plus format-specific fields (PDF: pdf_version, producer, is_encrypted, page_count; Excel: sheet_count, sheet_names; Email: from_email, to_emails, message_id; HTML: open_graph, structured_data; Image: exif)
  - SurrealDB: Common fields as top-level SCHEMAFULL fields. Format-specific data in `metadata` FLEXIBLE object. Object functions: `object::keys()`, `object::entries()`, `object::values()`.
  - Notes: Metadata schema varies by format. SCHEMAFULL for common fields, FLEXIBLE for the catch-all metadata object.

- [CONFIRMED] **Quality Score Storage** -- Persist kreuzberg's extraction quality assessment for downstream filtering and ranking.
  - Kreuzberg: `ExtractionResult.quality_score: float | None`. Requires `enable_quality_processing=True` (default True).
  - SurrealDB: `DEFINE FIELD quality_score ON documents TYPE option<float>`. Usable in queries: `WHERE quality_score > 0.7`, or in scoring: `score * quality_score`.
  - Notes: Quality score semantics may vary across document formats. Not all documents produce a quality score (can be None).

- [CONFIRMED] **Language Detection Storage** -- Store detected languages from kreuzberg's language detection.
  - Kreuzberg: `ExtractionResult.detected_languages: list[str] | None`
  - SurrealDB: `DEFINE FIELD detected_languages ON documents TYPE option<array<string>>`
  - Notes: Array of language codes. Useful for routing to language-specific analyzers in v0.2.0.

- [CONFIRMED] **Keyword Extraction Storage** -- Store extracted keywords (YAKE/RAKE) for concept-level retrieval.
  - Kreuzberg: `KeywordConfig(algorithm=KeywordAlgorithm.Yake, max_keywords=10)`. Returns `ExtractedKeyword` with `.text`, `.score`, `.algorithm`, `.positions`.
  - SurrealDB: `DEFINE FIELD keywords ON documents TYPE option<array<object>>`
  - Notes: Keywords stored at document level. Graph-based keyword relationships are a v0.2.0 feature.

- [CONFIRMED] **Document Dates as SurrealDB Datetime** -- Parse kreuzberg's ISO 8601 date strings into native SurrealDB datetime types.
  - Kreuzberg: `ExtractionResult.metadata` has `created_at: str | None` and `modified_at: str | None` as ISO 8601 strings.
  - SurrealDB: `Datetime(dt: str)` accepts ISO 8601. `DEFINE FIELD created_at ON documents TYPE option<datetime>`. Time functions: `time::year()`, `time::month()`, `time::now()`.
  - Notes: Handle `None` values gracefully. `ingested_at` uses `DEFAULT time::now()` in the schema.

- [CONFIRMED] **System Metadata** -- Automatic tracking of ingestion timestamp, MIME type, source path, and flexible metadata.
  - Kreuzberg: `ExtractionResult.mime_type`, source path passed by user
  - SurrealDB: `ingested_at` with `DEFAULT time::now()`, `source`, `mime_type` fields
  - Notes: `ingested_at` is auto-set by the database. `source` serves as the unique identifier for deduplication.

---

## v0.2.0 -- Enhanced Release

### Advanced Ingestion

- [CONFIRMED] **Per-Page Document Storage** -- Store each page as its own record linked to the parent document for page-level retrieval and citation.
  - Kreuzberg: `PageConfig(extract_pages=True)` populates `ExtractionResult.pages: list[PageContent]`. `PageContent` has `page_number`, `content`, `tables`, `images`, `is_blank`.
  - SurrealDB: `db.create(RecordID("pages", f"{doc_id}_p{page_num}"), page_data)` with `DEFINE FIELD document ON pages TYPE record<documents>`.
  - Notes: Alternative to chunking for page-oriented formats (PDF, PPTX). Blank page detection (`is_blank`) allows skipping empty pages. Adds extraction overhead.

- [CONFIRMED] **Incremental Re-Indexing** -- Detect changed files and skip unchanged ones during re-ingestion via content hashing.
  - Kreuzberg: Extraction is deterministic. Connector hashes raw file bytes.
  - SurrealDB: `db.upsert()` for insert-or-update. `db.query("SELECT content_hash FROM documents WHERE source = $src", {"src": path})` checks existing hash.
  - Notes: Store `content_hash` (SHA-256 of file bytes) on document records. On re-ingestion: compute hash -> query existing hash -> skip if match -> extract and replace if different.

- [CONFIRMED] **Extraction Error Logging** -- Store extraction failures as structured records for diagnostics and retry.
  - Kreuzberg: `KreuzbergError` hierarchy: `ValidationError`, `ParsingError`, `OCRError`, `MissingDependencyError`, `CacheError`, `ImageProcessingError`, `PluginError`. `get_error_details()` returns `{message, code, type, source, line, context}`.
  - SurrealDB: `db.create("extraction_errors", {"file": path, "error_code": code, "message": msg, "type": type, "timestamp": Datetime(...)})`.
  - Notes: Create an `extraction_errors` table. Wrap extraction calls in try/except to capture and store errors. Enables diagnostics dashboards and retry logic.

- [PARTIAL] **Transactional Batch Ingestion** -- Atomic ingestion of document + chunks within a transaction to prevent partial writes.
  - Kreuzberg: `batch_extract_files()` returns `list[ExtractionResult]`
  - SurrealDB: `session = await db.new_session()`, `txn = await session.begin_transaction()`, `await txn.query(...)`, `await txn.commit()` or `await txn.cancel()`
  - Caveat: Transactions require WebSocket connection only. Embedded mode raises `NotImplementedError`.
  - Workaround: Document the WebSocket requirement. For embedded mode, implement application-level rollback (delete created records on failure). Consider breaking large batches into smaller transaction groups.

### Graph Features

- [CONFIRMED] **Keyword Concept Graph** -- Store keywords as graph nodes with scored edges to documents, enabling concept-based retrieval.
  - Kreuzberg: `KeywordConfig(algorithm=KeywordAlgorithm.Yake, max_keywords=10)`. Returns `ExtractedKeyword` with `.text`, `.score`, `.algorithm`, `.positions`.
  - SurrealDB: `db.insert_relation("mentions", {"in": RecordID("documents", doc_id), "out": RecordID("keywords", keyword_text), "score": score})`. Graph traversal: `SELECT ->mentions->keywords FROM documents:doc1`. Reverse: `SELECT <-mentions<-documents FROM keywords:machine_learning`.
  - Notes: Create `keywords` table (unique on normalized text), `mentions` edge table with score/algorithm. Requires keyword deduplication (case-insensitive normalization via `string::lowercase()`).

- [CONFIRMED] **Chunk Adjacency Graph** -- Sequential edges between adjacent chunks for context expansion after retrieval.
  - Kreuzberg: `ChunkMetadata.chunk_index` provides sequential ordering. `total_chunks` gives the total count.
  - SurrealDB: `db.insert_relation("next_chunk", {"in": RecordID("chunks", chunk_n), "out": RecordID("chunks", chunk_n_plus_1)})`. Traversal: `SELECT ->next_chunk->chunks FROM chunks:chunk5`.
  - Notes: Enables sliding-window context expansion: retrieve a chunk via vector search, then traverse edges to include surrounding chunks. Low implementation cost. Edges created after all chunks for a document are stored.

- [CONFIRMED] **Document Hierarchy as Graph** -- Store document structure (headings, paragraphs, tables) as a tree of graph nodes.
  - Kreuzberg: `ExtractionConfig(include_document_structure=True)` yields `DocumentStructure.nodes: list[DocumentNode]`. Each node has `.id`, `.content`, `.parent`, `.children`, `.content_layer`, `.page`, `.bbox`. Node types: title, heading, paragraph, list, table, image, code, quote, formula, footnote, group, page_break.
  - SurrealDB: RELATE statements or `insert_relation()` for parent-child edges. `DEFINE TABLE doc_nodes SCHEMAFULL`.
  - Notes: Advanced feature. The `parent` and `children` fields use array indices (not stable IDs), so the connector must translate to record IDs during storage. Best as a separate extraction mode, not default. Enables structural queries: "find all tables under the Results heading."

### Advanced Search

- [CONFIRMED] **Metadata-Filtered Vector Search** -- Combine vector similarity search with metadata predicates (format, language, date, quality).
  - Kreuzberg: Rich metadata extraction provides filter dimensions.
  - SurrealDB: `SELECT * FROM chunks WHERE embedding <|K, COSINE|> $vec AND document.format_type = 'pdf' AND document.created_at > '2024-01-01'`
  - Notes: SurrealDB supports subqueries and record link traversal in WHERE clauses. For best performance, denormalize frequently-filtered metadata from documents to chunks. Pre/post filter performance behavior is undocumented.

- [CONFIRMED] **Search Result Highlighting** -- BM25 search results include highlighted matching terms for UI display.
  - Kreuzberg: N/A
  - SurrealDB: `search::highlight('<b>', '</b>', 0)` wraps matched terms. `search::offsets(0)` returns position arrays. Requires `HIGHLIGHTS` clause on index definition.
  - Notes: Only works with full-text search (BM25), not vector search. The reference number in `@0@` and `search::highlight(..., 0)` must match.

- [CONFIRMED] **Quality-Weighted Search Results** -- Use kreuzberg's quality score to boost or filter search results.
  - Kreuzberg: `ExtractionResult.quality_score: float | None`
  - SurrealDB: `WHERE quality_score > 0.7` for filtering, `score * document.quality_score` for weighted ranking
  - Notes: Requires quality score to be available on the document record. Can be applied as a post-processing step or integrated into the query.

### Operational Features

- [PARTIAL] **Live Ingestion Monitoring** -- Real-time notifications as documents are created/updated/deleted via SurrealDB live queries.
  - Kreuzberg: N/A
  - SurrealDB: `db.live("documents")` returns UUID. `db.subscribe_live(uuid)` yields notifications. Format: `{"action": "CREATE", "result": {...}}`.
  - Caveat: Single-node deployment only. Not supported in multi-node clusters. Connection-dependent (drops with connection). Message ordering is best-effort. No parameter support inside live queries.
  - Workaround: Use for development dashboards and local monitoring only. Not suitable for production monitoring on distributed deployments.

- [CONFIRMED] **Multi-Language Full-Text Search** -- Language-specific analyzers using SurrealDB's snowball stemmer for 17 supported languages.
  - Kreuzberg: `OcrConfig(language="eng+fra+deu")` for multi-language OCR. `LanguageDetectionConfig(enabled=True)` for language detection.
  - SurrealDB: `DEFINE ANALYZER` supports `snowball()` with 17 languages (Arabic, Danish, Dutch, English, French, German, Greek, Hungarian, Italian, Norwegian, Portuguese, Romanian, Russian, Spanish, Swedish, Tamil, Turkish). Multiple analyzers and indexes can be defined per field.
  - Notes: Connector logic routes documents to language-specific analyzers based on detected language. Start with English-only in v0.1.0.

---

## Future / Stretch

- [CONFIRMED] **Tenant-Isolated Document Stores** -- Multi-tenant data isolation using SurrealDB namespaces.
  - Kreuzberg: Extraction is stateless (no tenant awareness needed).
  - SurrealDB: `db.use("namespace", "database")` switches context. Complete data isolation between namespaces.
  - Notes: Simple namespace-per-tenant model. Connection pooling strategy needed. Switching namespaces on a shared connection may cause race conditions in async code.

- [CONFIRMED] **Fuzzy Keyword Search** -- Approximate string matching on keywords using SurrealDB's built-in distance functions.
  - Kreuzberg: Extracted keywords provide the keyword corpus.
  - SurrealDB: `string::distance::levenshtein()`, `string::distance::damerau_levenshtein()`, `string::similarity::jaro_winkler()`, `string::similarity::fuzzy()`
  - Notes: Functions are computed at query time, not indexed. Performance degrades on large keyword sets (full scan with function evaluation). Suitable for small-to-medium keyword tables.

- [PARTIAL] **Aggregate Analytics Views** -- Pre-computed materialized views for collection-level statistics (document count, average quality, format distribution).
  - Kreuzberg: Provides quality scores, metadata, chunk counts.
  - SurrealDB: `DEFINE TABLE stats AS SELECT count() AS total, math::mean(quality_score) AS avg_quality FROM documents GROUP ALL`. Updates incrementally.
  - Caveat: Table-level views (materialized views) exist but current stability needs testing.
  - Workaround: Test materialized view behavior during development. Fall back to on-demand aggregation queries if views are unstable.

- [PARTIAL] **Archive Content Ingestion** -- Ingest ZIP/RAR/7Z/TAR archives, storing the combined extracted text.
  - Kreuzberg: Handles ZIP, RAR, 7Z, TAR, GZIP recursively. Archive metadata (file_count, file_list, total_size) available.
  - SurrealDB: Standard document storage. Graph edges via `insert_relation()` for containment.
  - Caveat: kreuzberg returns a single `ExtractionResult` for the entire archive. Individual file results within the archive are NOT separately accessible via the public API.
  - Workaround: Store combined archive content as a single document. The `file_list` metadata gives the manifest. For individual file storage, users must extract archive contents to a directory first and use `ingest_directory()`.

- [PARTIAL] **Email Thread Ingestion** -- Ingest EML/MSG files with email-specific metadata (from, to, cc, message_id, attachments).
  - Kreuzberg: EML/MSG extraction with email metadata (from_email, to_emails, cc_emails, message_id, attachments).
  - SurrealDB: Graph edges for communication relationships.
  - Caveat: Attachment content is extracted inline (not as separate `ExtractionResult` objects). Building a full communication graph requires post-processing the metadata.
  - Workaround: Store email-as-document with rich metadata. Graph modeling (person -> email -> recipient) requires connector-level logic using kreuzberg's metadata fields.

- [PARTIAL] **Multi-Model Embedding Storage** -- Store embeddings from multiple models on the same chunks for A/B testing or model comparison.
  - Kreuzberg: `EmbeddingModelType.fastembed()` and `EmbeddingModelType.custom()` support different models. But only ONE embedding config per extraction run.
  - SurrealDB: Multiple HNSW indexes on different fields of the same table.
  - Caveat: Requires running extraction TWICE with different embedding configs, or running a second embedding pass on already-extracted chunks using FastEmbed directly.
  - Workaround: Store each model's embeddings in a separate field (`embedding_384`, `embedding_768`) with separate HNSW indexes. Run FastEmbed directly for the second pass to avoid re-extraction.

- [PARTIAL] **Element-Based Knowledge Graph** -- Store document elements (headings, paragraphs, tables, images) as typed graph nodes.
  - Kreuzberg: `result_format="element_based"` yields `ExtractionResult.elements: list[Element]` with `element_id`, `element_type`, `text`, `metadata`.
  - SurrealDB: Multi-table graph or single table with type discriminator.
  - Caveat: Relationship inference (which heading contains which paragraphs) requires heuristic logic. kreuzberg provides flat elements, not a tree.
  - Workaround: Use the DocumentStructure approach (Document Hierarchy as Graph) instead, which provides a proper tree. Element-based approach is only useful when tree structure is not available.

- [PARTIAL] **Bounding Box Storage for Visual Document AI** -- Store spatial coordinates for tables, images, annotations, and document nodes.
  - Kreuzberg: `BoundingBox` on tables, images, annotations, document nodes.
  - SurrealDB: Can store as nested objects `{x, y, width, height}`.
  - Caveat: No native 2D spatial index for document coordinates. Geospatial indexes are "planned" but not yet available. Stored as plain objects -- no spatial queries.
  - Workaround: Store bounding boxes as nested objects for retrieval. Spatial querying requires application-level logic (WHERE x > ... AND x < ...).

- [PARTIAL] **SurrealDB as Agent Memory Store** -- Use the connector's document knowledge layer as the memory backend for AI agents.
  - Kreuzberg: Full extraction pipeline provides document knowledge.
  - SurrealDB: Markets itself for AI agent memory (vectors + graphs + documents). MCP server support. Live queries for reactivity.
  - Caveat: "AI agent memory" is a marketing concept, not a specific API. The agent framework (LangChain, etc.) provides the orchestration.
  - Workaround: No special implementation needed beyond the core features. The connector naturally enables this by populating SurrealDB with rich, searchable document data. Agent framework integration is the user's responsibility.

---

## Explicitly Excluded

| Feature | Status | Reason |
|---|---|---|
| **Image Extraction + File Storage Buckets** (A.2) | INFEASIBLE | SurrealDB file storage buckets are a v3.0 feature and currently experimental (requires `--allow-experimental files` flag). The Python SDK v2.0.0a1 targets server v2.x which does not have file buckets. Alternative: store image metadata in SurrealDB, store image bytes in external storage (filesystem/S3). |
| **Real-Time Search Result Streaming** (7.4) | INFEASIBLE | `LIVE SELECT` does NOT support KNN or full-text search predicates. It supports simple field matching only. Parameters inside live queries are not supported. Use polling or manual refresh for search results. |
| **Document Versioning via Time-Series** (A.20) | INFEASIBLE | SurrealDB time-series with versioned temporal tables is listed as experimental. Not suitable for production use. Alternative: implement simpler versioning via manual version fields and record history. |
| **SurrealML Integration for Re-Ranking** (A.9) | NEEDS_MORE_RESEARCH | SurrealML is a separate subsystem. The re-ranking model must be trained separately and deployed to SurrealDB. Python SDK interaction with SurrealML is unclear. Aspirational; defer to much later versions. |
| **Changefeed-Driven Embedding Updates** (A.19) | NEEDS_MORE_RESEARCH | `SHOW CHANGES FOR TABLE` changefeed exists in SurrealQL, but it is unclear if changefeeds are exposed through the Python SDK or only via raw SurrealQL queries. Advanced feature; defer. |

---

## Summary Statistics

| Metric | Count |
|---|---|
| **v0.1.0 Core features** | 25 |
| **v0.2.0 Enhanced features** | 14 |
| **Future / Stretch features** | 10 |
| **Total buildable features** | **49** |
| | |
| CONFIRMED features | 39 |
| PARTIALLY_CONFIRMED features (with workarounds) | 10 |
| INFEASIBLE features (excluded) | 3 |
| NEEDS_MORE_RESEARCH (excluded) | 2 |

### v0.1.0 Breakdown by Category

| Category | Count |
|---|---|
| Connection & Setup | 4 |
| Document Ingestion | 3 |
| Chunking & Embeddings | 5 |
| Search | 6 |
| Schema & Storage | 4 |
| Metadata & Enrichment | 6 |

### v0.2.0 Breakdown by Category

| Category | Count |
|---|---|
| Advanced Ingestion | 4 |
| Graph Features | 3 |
| Advanced Search | 3 |
| Operational Features | 2 |
| SurrealDB Features used (native) | HNSW, BM25, RRF, RELATE, LIVE SELECT, record links, transactions |
