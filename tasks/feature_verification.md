# Feature Verification: kreuzberg-surrealdb Connector

> Rigorous verification of each proposed feature against actual kreuzberg and SurrealDB APIs.
> Date: 2026-03-06
> Sources: kreuzberg-capabilities.md (v4.4.2), surrealdb-capabilities.md (SDK v2.0.0a1 / server v2.x)

## Critical Compatibility Note

The SurrealDB Python SDK v2.0.0a1 targets **SurrealDB server v2.0.0 - v2.3.6**. The stable SDK is v1.0.8.
SurrealDB server v3.0 introduced **breaking syntax changes** and **new features** (file buckets, FULLTEXT ANALYZER keyword).
For v2.x server compatibility:
- Full-text index syntax: `SEARCH ANALYZER` (not `FULLTEXT ANALYZER`)
- File storage buckets: NOT available (v3.0 only, experimental)
- `search::rrf()`: Available in v2.x

---

## Tier 1 Features (9 features -- must-have for v1)

### 1.1 Universal Document Ingestion Pipeline
- **Status**: CONFIRMED
- **Kreuzberg Evidence**: `extract_file(path, config=...)` async and `extract_file_sync(path, config=...)` sync. Accepts `str | Path`, auto-detects MIME type. Returns `ExtractionResult` with `.content`, `.mime_type`, `.metadata`, `.tables`, `.quality_score`, `.detected_languages`, `.chunks`, `.extracted_keywords`. 75+ format support (PDF, DOCX, XLSX, PPTX, EML, EPUB, HTML, images, archives, etc.).
- **SurrealDB Evidence**: `db.create("documents", {...})` or `db.insert("documents", [records])` for bulk insert. `db.query()` for raw SurrealQL including `DEFINE TABLE`, `DEFINE FIELD`, `DEFINE INDEX`. Both sync `Surreal` and async `AsyncSurreal` available.
- **Gotchas**: None significant. ExtractionResult fields map cleanly to SurrealDB record fields. The `metadata` TypedDict needs flattening or nesting strategy.
- **Notes**: This is the core pipeline. Extract via kreuzberg, map to schema, store via SDK.

### 2.1 Native Chunk Storage with Vector Index
- **Status**: CONFIRMED
- **Kreuzberg Evidence**: `ChunkingConfig(max_chars=1000, max_overlap=200, embedding=EmbeddingConfig(...))`. Returns `ExtractionResult.chunks: list[Chunk]` where `Chunk` has `.content: str` and `.embedding: list[float] | None`. `ChunkMetadata` provides `byte_start`, `byte_end`, `chunk_index`, `total_chunks`, `token_count`, `first_page`, `last_page`.
- **SurrealDB Evidence**: `DEFINE INDEX idx_chunk_embedding ON chunks FIELDS embedding HNSW DIMENSION 768 DIST COSINE` creates HNSW vector index. KNN search via `WHERE embedding <|K, COSINE|> $query_vec`. Parameters: DIMENSION (required), DIST (COSINE/EUCLIDEAN/MANHATTAN), TYPE (F64 default), EFC (150 default), M (12 default).
- **Gotchas**: HNSW is currently an **in-memory structure** in SurrealDB -- performance may degrade with very large datasets. Need to verify persistence behavior across restarts.
- **Notes**: Core feature. Chunk schema: `document` (record link), `content`, `embedding`, `chunk_index`, `page_number`, `char_start`, `char_end`.

### 2.2 Embedding Preset to Index Configuration Mapping
- **Status**: CONFIRMED
- **Kreuzberg Evidence**: `list_embedding_presets()` returns preset names. `get_embedding_preset(name)` returns `EmbeddingPreset` with `.name`, `.chunk_size`, `.overlap`, `.model_name`, `.dimensions`, `.description`. Presets: "balanced" (768d), "compact" (384d), "large" (1024d). Also `EmbeddingModelType.fastembed(model, dimensions)` and `EmbeddingModelType.custom(model_id, dimensions)` for custom models.
- **SurrealDB Evidence**: `DEFINE INDEX ... HNSW DIMENSION {n}` where n comes from the preset's `.dimensions` field. The connector auto-generates the DDL.
- **Gotchas**: None. Clean mapping from preset dimensions to HNSW DIMENSION parameter.
- **Notes**: The connector reads `get_embedding_preset(name).dimensions` and generates `DEFINE INDEX ... HNSW DIMENSION {dimensions} DIST COSINE`.

### 2.4 Full-Text Index on Chunk Content
- **Status**: CONFIRMED
- **Kreuzberg Evidence**: `Chunk.content: str` provides the text to index.
- **SurrealDB Evidence**: `DEFINE ANALYZER chunk_analyzer TOKENIZERS class FILTERS lowercase, snowball(english)`. Then `DEFINE INDEX idx_chunk_content ON chunks FIELDS content SEARCH ANALYZER chunk_analyzer BM25(1.2, 0.75) HIGHLIGHTS`. The `@@` operator matches against the index: `WHERE content @0@ $query`. `search::score(0)` retrieves BM25 relevance score. `search::highlight('<b>', '</b>', 0)` highlights matches. Snowball stemmer supports: Arabic, Danish, Dutch, English, French, German, Greek, Hungarian, Italian, Norwegian, Portuguese, Romanian, Russian, Spanish, Swedish, Tamil, Turkish.
- **Gotchas**: Syntax is `SEARCH ANALYZER` on SurrealDB v2.x. On v3.0+ it becomes `FULLTEXT ANALYZER`. The connector must target the correct syntax for the server version.
- **Notes**: Combined with HNSW vector index, this enables hybrid search on the same table.

### 3.1 Local Embedding Generation + HNSW Storage
- **Status**: CONFIRMED
- **Kreuzberg Evidence**: Embeddings generated via `ChunkingConfig(embedding=EmbeddingConfig(model=EmbeddingModelType.preset("balanced")))`. FastEmbed ONNX models run locally in Rust. No API key needed. Chunk.embedding is `list[float]`.
- **SurrealDB Evidence**: `list[float]` maps to SurrealDB `array<float>` field. HNSW index on this field. KNN search via `<|K, COSINE|>` operator.
- **Gotchas**: Embedding generation happens only during chunking (no standalone `embed_text()` API). Query-time embedding requires a workaround (see 3.3).
- **Notes**: Zero-cost, fully local embedding pipeline. CPU-only, no GPU required.

### 4.1 Rich Metadata Record Storage
- **Status**: CONFIRMED
- **Kreuzberg Evidence**: `ExtractionResult.metadata` is a TypedDict with common fields (title, subject, authors, keywords, language, created_at, modified_at, created_by, modified_by, format_type) plus format-specific fields (PDF: pdf_version, producer, is_encrypted, page_count; Excel: sheet_count, sheet_names; Email: from_email, to_emails, message_id, attachments; HTML: open_graph, structured_data; Image: exif).
- **SurrealDB Evidence**: `DEFINE FIELD metadata ON documents TYPE object FLEXIBLE` allows arbitrary nested objects. Or flatten common fields: `DEFINE FIELD title ON documents TYPE option<string>`, `DEFINE FIELD authors ON documents TYPE option<array<string>>`, etc. Object functions: `object::keys()`, `object::entries()`, `object::values()`.
- **Gotchas**: Format-specific metadata varies widely. Use SCHEMAFULL for common fields, FLEXIBLE for the catch-all metadata object.
- **Notes**: Store common fields at top level for indexing/filtering, format-specific data in a nested `metadata` object.

### 8.1 High-Throughput Batch Ingestion
- **Status**: CONFIRMED
- **Kreuzberg Evidence**: `batch_extract_files(paths, config=...)` async and `batch_extract_files_sync(paths, config=...)` sync. Uses Rust rayon for parallelism. `ExtractionConfig.max_concurrent_extractions` limits concurrency. Returns `list[ExtractionResult]`.
- **SurrealDB Evidence**: `db.insert("table", [records])` bulk inserts a list of records in one call. Async `AsyncSurreal` for non-blocking operations.
- **Gotchas**: Need to handle partial failures -- some files may fail extraction while others succeed. `batch_extract_files` behavior on individual failures needs testing (does it throw or return partial results?).
- **Notes**: Pipeline: batch extract -> collect results -> batch insert documents -> batch insert chunks. Consider chunking the SurrealDB inserts into batches of ~100-500 records.

### 10.1 Hybrid Search (Vector + BM25 + RRF)
- **Status**: CONFIRMED
- **Kreuzberg Evidence**: Provides embeddings (for vector search) and text content (for BM25).
- **SurrealDB Evidence**: `search::rrf([$vs, $ft], limit, k)` combines vector and full-text search results. Requires two separate queries: (1) vector: `SELECT id, content, vector::distance::knn() AS distance FROM chunks WHERE embedding <|K, COSINE|> $query_vec ORDER BY distance`, (2) full-text: `SELECT id, content, search::score(0) AS score FROM chunks WHERE content @0@ $query ORDER BY score DESC`. Then `search::rrf([$vs, $ft], limit, 60)`. Both result sets MUST include `id` field for RRF stitching.
- **Gotchas**: RRF requires three separate queries (vector, full-text, fusion) -- cannot be done in a single statement. The Python SDK's `db.query()` can execute multi-statement queries, but the RRF input requires binding the results of previous queries as parameters. The Ratatui blog example shows binding `$vs` and `$ft` as parameters to the third query.
- **Notes**: This is the headline feature. Implementation pattern: run vector query, run full-text query, bind results, run RRF query.

### A.7 Embedded Database for Testing/Development
- **Status**: CONFIRMED
- **Kreuzberg Evidence**: All extraction functions are storage-agnostic.
- **SurrealDB Evidence**: `Surreal("memory")` for in-memory embedded DB (no server needed). `Surreal("file://path")` for persistent embedded. `AsyncSurreal("memory")` for async. Full API parity with WebSocket/HTTP connections. Live queries supported in embedded mode. Transactions NOT supported in embedded (WebSocket only).
- **Gotchas**: Transactions require WebSocket connection. Embedded mode uses the same connection URL pattern but routes to `BlockingEmbeddedSurrealConnection` / `AsyncEmbeddedSurrealConnection`. HNSW in-memory nature means embedded mode is actually a good fit.
- **Notes**: Excellent for testing. CI can use `memory` mode with no external dependencies. Development can use `file://` for persistence.

---

## Tier 2 Features (16 features -- high-value stretch/v2)

### 1.2 Per-Page Document Storage
- **Status**: CONFIRMED
- **Kreuzberg Evidence**: `PageConfig(extract_pages=True)` populates `ExtractionResult.pages: list[PageContent]`. `PageContent` is a TypedDict with `page_number: int` (1-indexed), `content: str`, `tables: list[ExtractedTable]`, `images: list[ExtractedImage]`, `is_blank: bool | None`.
- **SurrealDB Evidence**: `db.create(RecordID("pages", f"{doc_id}_p{page_num}"), page_data)` with `DEFINE FIELD document ON pages TYPE record<documents>` for parent link. Record links enable `SELECT * FROM pages WHERE document = $doc_id`.
- **Gotchas**: Per-page extraction adds overhead. Blank page detection (`is_blank`) allows skipping empty pages. Tables per page are included in `PageContent.tables`.
- **Notes**: Alternative to chunking for page-oriented formats (PDF, PPTX). Can do per-page chunking + embedding for finer granularity.

### 3.3 Query-Time Embedding + Vector Search
- **Status**: PARTIALLY_CONFIRMED
- **Kreuzberg Evidence**: kreuzberg does NOT have a standalone `embed_text()` function. Embeddings are generated only during chunking as part of `extract_file()`. To embed a query string, you would need to: (a) use `extract_bytes(query.encode(), "text/plain", config_with_chunking_and_embedding)` to extract+chunk+embed a text string, or (b) call FastEmbed directly, bypassing kreuzberg.
- **SurrealDB Evidence**: KNN search requires a pre-computed query vector: `WHERE embedding <|K, COSINE|> $query_vec`.
- **Gotchas**: **Major gap.** There is no clean kreuzberg API to embed an arbitrary text string. The workaround of extracting bytes as text/plain works but is inelegant. The better approach is to use FastEmbed directly as a peer dependency. FastEmbed's `TextEmbedding` class provides `embed()` for standalone text embedding.
- **Notes**: The connector will likely need to depend on `fastembed` directly (or the qdrant_fastembed equivalent) for query-time embedding. Alternatively, wrap kreuzberg's chunking pipeline with a tiny text input. This is a design decision with trade-offs.

### 4.2 Document Dates as SurrealDB Datetime
- **Status**: CONFIRMED
- **Kreuzberg Evidence**: `ExtractionResult.metadata` has `created_at: str | None` and `modified_at: str | None` as ISO 8601 strings.
- **SurrealDB Evidence**: `Datetime(dt: str)` accepts ISO 8601 strings directly. `DEFINE FIELD created_at ON documents TYPE option<datetime>`. Time functions: `time::year()`, `time::month()`, `time::now()`, etc.
- **Gotchas**: kreuzberg returns ISO 8601 strings that may or may not include timezone info. SurrealDB's Datetime handles RFC 3339 (which is ISO 8601 compatible). Need to handle `None` values gracefully.
- **Notes**: Parse kreuzberg's ISO 8601 strings into SurrealDB `Datetime` objects. `ingested_at` can use `DEFAULT time::now()` in the schema.

### 4.6 Quality Score as Computed Relevance Weight
- **Status**: CONFIRMED
- **Kreuzberg Evidence**: `ExtractionResult.quality_score: float | None`. Requires `enable_quality_processing=True` (default is True). Float value representing extraction quality.
- **SurrealDB Evidence**: `DEFINE FIELD quality_score ON documents TYPE option<float>`. Can use in queries: `WHERE quality_score > 0.7`, or in scoring: `score * quality_score`. Math functions: `math::mean()`, `math::max()`, etc.
- **Gotchas**: Quality score semantics may vary across document formats. Not all documents produce a quality score (can be None).
- **Notes**: Store as-is and use in query-time ranking or filtering.

### 6.1 Keyword Concept Graph
- **Status**: CONFIRMED
- **Kreuzberg Evidence**: `KeywordConfig(algorithm=KeywordAlgorithm.Yake, max_keywords=10)` or `KeywordAlgorithm.Rake`. Returns `ExtractionResult.extracted_keywords: list[ExtractedKeyword]` where `ExtractedKeyword` has `.text: str`, `.score: float`, `.algorithm: str`, `.positions: list[int] | None`.
- **SurrealDB Evidence**: `db.insert_relation("mentions", {"in": RecordID("documents", doc_id), "out": RecordID("keywords", keyword_text), "score": score, "algorithm": algorithm})`. Graph traversal: `SELECT ->mentions->keywords FROM documents:doc1`. Reverse: `SELECT <-mentions<-documents FROM keywords:machine_learning`.
- **Gotchas**: Keyword deduplication needed (case-insensitive). SurrealDB's `string::lowercase()` can normalize. High-frequency keywords (stopwords that leaked through) may create dense hub nodes.
- **Notes**: Create `keywords` table (unique on normalized text), `mentions` edge table with score/algorithm. Enables concept-based retrieval.

### 6.2 Document Hierarchy as Graph
- **Status**: CONFIRMED
- **Kreuzberg Evidence**: `ExtractionConfig(include_document_structure=True)` yields `ExtractionResult.document: DocumentStructure`. `DocumentStructure.nodes: list[DocumentNode]`. `DocumentNode` has `.id: str`, `.content: NodeContent`, `.parent: int | None`, `.children: list[int]`, `.content_layer: Literal["body", "header", "footer", "footnote"]`, `.page: int | None`, `.bbox: BoundingBox | None`. Node types: title, heading, paragraph, list, list_item, table, image, code, quote, formula, footnote, group, page_break.
- **SurrealDB Evidence**: RELATE statement or `insert_relation()` for parent-child edges. `DEFINE TABLE doc_nodes SCHEMAFULL`. Record links for hierarchy: `DEFINE FIELD parent ON doc_nodes TYPE option<record<doc_nodes>>`.
- **Gotchas**: The `parent` and `children` fields use indices into the `nodes` array, not stable IDs. The connector must translate array indices to record IDs during storage. Complex mapping logic required.
- **Notes**: Advanced feature. Enables structural queries: "find all tables under the 'Results' heading." Best as a separate extraction mode, not default.

### 6.4 Chunk Adjacency Graph
- **Status**: CONFIRMED
- **Kreuzberg Evidence**: `ChunkMetadata.chunk_index` provides sequential ordering. `total_chunks` gives the total count.
- **SurrealDB Evidence**: `db.insert_relation("next_chunk", {"in": RecordID("chunks", chunk_n), "out": RecordID("chunks", chunk_n_plus_1)})`. Traversal: `SELECT ->next_chunk->chunks FROM chunks:chunk5` to get the next chunk for context expansion.
- **Gotchas**: Simple sequential edges. Need to be created after all chunks for a document are stored (need to know chunk IDs).
- **Notes**: Enables sliding-window context expansion after vector retrieval. Low implementation cost.

### 7.1 Live Ingestion Monitoring
- **Status**: PARTIALLY_CONFIRMED
- **Kreuzberg Evidence**: N/A (kreuzberg side is just extraction; no special API needed).
- **SurrealDB Evidence**: `db.live("documents")` returns UUID. `db.subscribe_live(uuid)` yields notifications as documents are created/updated/deleted. WebSocket or embedded connections only (not HTTP). `{"action": "CREATE", "result": {...}}` notification format.
- **Gotchas**: **Single-node deployment only.** Live queries are not supported in multi-node clusters. Connection-dependent: if connection drops, live query disappears. No parameter support inside live queries. Message ordering is best-effort, not guaranteed.
- **Notes**: Good for development dashboards. Not suitable for production monitoring on distributed deployments.

### 8.3 Transactional Batch Ingestion
- **Status**: PARTIALLY_CONFIRMED
- **Kreuzberg Evidence**: `batch_extract_files()` returns `list[ExtractionResult]`.
- **SurrealDB Evidence**: Transactions via WebSocket sessions only: `session = await db.new_session()`, `txn = await session.begin_transaction()`, `await txn.query(...)`, `await txn.commit()` or `await txn.cancel()`. HTTP and embedded connections raise `NotImplementedError`.
- **Gotchas**: **WebSocket-only.** Embedded mode does not support transactions. Transaction size limits may apply for large batches. The session/transaction API is relatively new (v2.0.0a1).
- **Notes**: Useful for ensuring atomic ingestion. Requires WebSocket connection. Consider breaking very large batches into smaller transaction groups.

### 8.4 Incremental Re-Indexing
- **Status**: CONFIRMED
- **Kreuzberg Evidence**: Extraction is deterministic for the same input. Content hashing can be done by the connector (hash file bytes before extraction).
- **SurrealDB Evidence**: `db.upsert()` for insert-or-update. `DEFINE INDEX idx_doc_source ON documents FIELDS source UNIQUE` prevents duplicates. `db.query("SELECT content_hash FROM documents WHERE source = $src", {"src": path})` checks existing hash.
- **Gotchas**: Content hashing must happen before extraction (hash raw bytes, not extracted text) to avoid unnecessary extraction of unchanged files. The connector needs to implement the hash-check-skip logic.
- **Notes**: Store `content_hash` (SHA-256 of file bytes) on document records. On re-ingestion: compute hash, query existing hash, skip if match.

### 10.2 Metadata-Filtered Vector Search
- **Status**: CONFIRMED
- **Kreuzberg Evidence**: Rich metadata extraction provides filter dimensions (format_type, language, authors, dates, etc.).
- **SurrealDB Evidence**: WHERE clauses work with KNN: `SELECT * FROM chunks WHERE embedding <|K, COSINE|> $vec AND document.format_type = 'pdf' AND document.created_at > '2024-01-01'`. SurrealDB supports subqueries and record link traversal in WHERE clauses.
- **Gotchas**: Filter performance depends on whether pre-filtering or post-filtering is applied. SurrealDB documentation is unclear on the filtering strategy for KNN. For best performance, denormalize frequently-filtered metadata from documents to chunks.
- **Notes**: Denormalize key metadata fields (format_type, language) onto chunk records to avoid cross-table joins during vector search.

### 10.7 Search Result Highlighting
- **Status**: CONFIRMED
- **Kreuzberg Evidence**: N/A (highlighting is a SurrealDB search feature).
- **SurrealDB Evidence**: `search::highlight('<b>', '</b>', 0)` wraps matched terms in HTML tags. `search::offsets(0)` returns `{s: start, e: end}` position arrays. Requires `HIGHLIGHTS` clause on the index definition. Works with BM25 full-text indexes.
- **Gotchas**: Only works with full-text search (BM25), not vector search. The reference number (e.g., `0` in `@0@` and `search::highlight(..., 0)`) must match between the query and the function call.
- **Notes**: Expose highlighted results in the search response for UI display.

### 11.1 Extraction Error Logging to SurrealDB
- **Status**: CONFIRMED
- **Kreuzberg Evidence**: `KreuzbergError` hierarchy: `ValidationError`, `ParsingError`, `OCRError`, `MissingDependencyError`, `CacheError`, `ImageProcessingError`, `PluginError`. Error has `.context: dict[str, Any]`. `get_error_details()` returns `{message, code, type, source, line, context}`. `ErrorCode` enum (0-7).
- **SurrealDB Evidence**: `db.create("extraction_errors", {"file": path, "error_code": code, "message": msg, "type": type, "timestamp": Datetime(...)})`. Time functions for analysis.
- **Gotchas**: None significant. Straightforward error logging.
- **Notes**: Create an `extraction_errors` table. Wrap extraction calls in try/except to capture and store errors.

### A.2 Image Extraction + File Storage Buckets
- **Status**: INFEASIBLE (for SurrealDB v2.x)
- **Kreuzberg Evidence**: `ImageExtractionConfig(extract_images=True)` yields `ExtractionResult.images: list[ExtractedImage]`. `ExtractedImage` has `.data: bytes`, `.format: str`, `.image_index`, `.page_number`, `.width`, `.height`, `.bounding_box`, `.ocr_result`.
- **SurrealDB Evidence**: File storage buckets (`DEFINE BUCKET`, `file::put()`, `file::get()`) are a **SurrealDB v3.0 feature** and currently **experimental** (requires `--allow-experimental files` flag). The Python SDK v2.0.0a1 targets server v2.x, which does NOT have file storage buckets.
- **Gotchas**: **Feature not available on target server version.** Would need SurrealDB v3.0+ server and an updated Python SDK. Even on v3.0, the feature is experimental.
- **Notes**: Defer to v2 when SurrealDB v3.0 support stabilizes. Alternative: store image metadata in SurrealDB, store image bytes in external storage (filesystem/S3) with a path reference.

### A.12 Document Deduplication via Content Hashing
- **Status**: CONFIRMED
- **Kreuzberg Evidence**: Extraction is deterministic. The connector can hash raw file bytes using Python's `hashlib.sha256()`.
- **SurrealDB Evidence**: `DEFINE INDEX idx_doc_hash ON documents FIELDS content_hash UNIQUE`. Also has `crypto::sha256()`, `crypto::blake3()` as SurrealQL functions, though hashing in Python before insert is more efficient. `AlreadyExistsError` raised on duplicate unique index violation.
- **Gotchas**: Content hash should be on raw file bytes (pre-extraction) for efficiency -- skip extraction entirely if hash matches. Near-duplicate detection (different formatting, same content) requires additional techniques beyond simple hashing.
- **Notes**: Core dedup strategy: hash file bytes -> check if hash exists -> skip if duplicate. Simple and effective.

### A.13 Chunk Page Range for Citation
- **Status**: CONFIRMED
- **Kreuzberg Evidence**: `ChunkMetadata` includes `first_page: int` and `last_page: int`.
- **SurrealDB Evidence**: `DEFINE FIELD first_page ON chunks TYPE option<int>`, `DEFINE FIELD last_page ON chunks TYPE option<int>`. Queryable: `WHERE first_page <= 5 AND last_page >= 5` to find chunks overlapping page 5. Could also use SurrealDB `Range` type but simple integers are more practical.
- **Gotchas**: Page numbers come from kreuzberg's chunk metadata, which requires page-aware chunking. Not all document formats have page numbers (text files, HTML).
- **Notes**: Essential for citation in RAG responses: "Source: document.pdf, pages 5-7."

---

## Tier 3 Spot-Check (most ambitious/risky features)

### 1.3 Archive Recursive Extraction + Storage
- **Status**: PARTIALLY_CONFIRMED
- **Kreuzberg Evidence**: Kreuzberg handles ZIP, RAR, 7Z, TAR, GZIP recursively. Archive metadata (file_count, file_list, total_size, compressed_size) is available. However, kreuzberg returns a **single** `ExtractionResult` for the entire archive -- individual file results within the archive are NOT separately accessible via the public API.
- **SurrealDB Evidence**: Graph edges via `insert_relation()` for containment.
- **Gotchas**: **Cannot access individual file extraction results from archives.** The combined text content is returned, but individual files' metadata and content are merged. The `file_list` metadata gives the manifest, but not per-file ExtractionResults.
- **Notes**: Feasible for storing the combined archive content. NOT feasible for storing individual files from archives as separate linked records without extracting files from the archive manually first.

### 1.4 Email Thread Ingestion
- **Status**: PARTIALLY_CONFIRMED
- **Kreuzberg Evidence**: EML/MSG extraction with email metadata (from_email, to_emails, cc_emails, message_id, attachments). However, attachment content is extracted inline (not as separate ExtractionResults).
- **SurrealDB Evidence**: Graph edges for communication graph.
- **Gotchas**: Attachments are extracted as part of the email content, not as separate addressable documents. Building a full communication graph requires post-processing the metadata.
- **Notes**: Feasible for email-as-document with metadata. Graph modeling (person -> email -> recipient) requires connector-level logic.

### 3.2 Multi-Model Embedding Storage
- **Status**: PARTIALLY_CONFIRMED
- **Kreuzberg Evidence**: `EmbeddingModelType.fastembed()` and `EmbeddingModelType.custom()` support different models. But only ONE embedding config per extraction run.
- **SurrealDB Evidence**: Multiple HNSW indexes on different fields of the same table should work (each on a different embedding field).
- **Gotchas**: Requires running extraction TWICE with different embedding configs. Expensive. Or the connector could run a second embedding pass on already-extracted chunks using FastEmbed directly.
- **Notes**: Defer to later version. Single-model embedding is sufficient for v1.

### 6.6 Element-Based Knowledge Graph
- **Status**: PARTIALLY_CONFIRMED
- **Kreuzberg Evidence**: `result_format="element_based"` yields `ExtractionResult.elements: list[Element]`. Each `Element` has `element_id`, `element_type`, `text`, `metadata` (page_number, coordinates, element_index).
- **SurrealDB Evidence**: Multi-table graph or single table with type discriminator.
- **Gotchas**: Relationship inference (which heading contains which paragraphs) requires heuristic logic based on element order and type. kreuzberg provides flat elements, not a tree.
- **Notes**: Complex implementation. The DocumentStructure approach (6.2) provides a tree, which is better for graph construction.

### 7.4 Real-Time Search Result Streaming
- **Status**: INFEASIBLE
- **Kreuzberg Evidence**: N/A.
- **SurrealDB Evidence**: `LIVE SELECT` does NOT support KNN or full-text search predicates. It supports simple field matching only. "It is not possible to use parameters inside of Live Queries."
- **Gotchas**: **Cannot do live vector search or live full-text search.** LIVE SELECT is limited to basic CRUD notifications, not complex search queries.
- **Notes**: Not feasible with current SurrealDB capabilities. Use polling or manual refresh for search results.

### A.2 Image Extraction + File Storage Buckets
- **Status**: INFEASIBLE (see Tier 2 verification above)

### A.9 SurrealML Integration for Re-Ranking
- **Status**: NEEDS_MORE_RESEARCH
- **Kreuzberg Evidence**: Provides chunk content and quality scores.
- **SurrealDB Evidence**: SurrealML supports ONNX-backed inference and `.surml` model format. However, the Python SDK's interaction with SurrealML is unclear -- it may require SurrealDB server-side configuration, not SDK-level API calls.
- **Gotchas**: SurrealML is a separate subsystem. The re-ranking model must be trained separately and deployed to SurrealDB. The connector's role is providing data, not managing ML models.
- **Notes**: Aspirational. Defer to much later versions.

### A.14 Bounding Box Storage for Visual Document AI
- **Status**: PARTIALLY_CONFIRMED
- **Kreuzberg Evidence**: `BoundingBox` on tables, images, annotations, document nodes. Available from kreuzberg.
- **SurrealDB Evidence**: Can store as nested objects. Using GeoJSON Polygon for document coordinates is unconventional and would misuse geographic operators.
- **Gotchas**: No native 2D spatial index for document coordinates. Geospatial indexes are "planned" (not yet available). Bounding boxes stored as plain objects work for storage/retrieval but not spatial queries.
- **Notes**: Store as nested objects `{x, y, width, height}`. Spatial querying would need application-level logic.

### A.15 SurrealDB as Agent Memory Store
- **Status**: PARTIALLY_CONFIRMED
- **Kreuzberg Evidence**: Full extraction pipeline provides document knowledge.
- **SurrealDB Evidence**: SurrealDB markets itself for AI agent memory (vectors + graphs + documents). MCP server support. Live queries for reactivity.
- **Gotchas**: "AI agent memory" is a marketing concept, not a specific API. The connector provides the document knowledge layer; the agent framework (LangChain, etc.) provides the orchestration.
- **Notes**: The connector naturally enables this by populating SurrealDB with rich document data. No special implementation needed beyond the core features.

### A.18 Aggregate Indexed Views for Analytics
- **Status**: PARTIALLY_CONFIRMED
- **Kreuzberg Evidence**: Provides quality scores, metadata, chunk counts.
- **SurrealDB Evidence**: Pre-computed table views (materialized views) exist: `DEFINE TABLE stats AS SELECT count() AS total, math::mean(quality_score) AS avg_quality FROM documents GROUP ALL`. These update incrementally as records are added/removed.
- **Gotchas**: These are table-level views, not index-level. The syntax and current stability need testing.
- **Notes**: Useful for dashboards. Define views during `setup_schema()`.

### A.19 Changefeed-Driven Embedding Updates
- **Status**: NEEDS_MORE_RESEARCH
- **Kreuzberg Evidence**: Re-extraction capability.
- **SurrealDB Evidence**: `SHOW CHANGES FOR TABLE` changefeed exists in SurrealQL. Table events can trigger actions. However, it is unclear if changefeeds are exposed through the Python SDK or only via raw SurrealQL queries.
- **Gotchas**: Changefeed and table event functionality may not be fully exposed via the Python SDK.
- **Notes**: Advanced feature. Defer to later versions.

### A.20 Document Versioning via Time-Series
- **Status**: INFEASIBLE (currently)
- **Kreuzberg Evidence**: Re-extraction produces new results.
- **SurrealDB Evidence**: Time-series with versioned temporal tables is listed as **experimental** in SurrealDB.
- **Gotchas**: **Experimental feature.** Not suitable for production use.
- **Notes**: Implement simpler versioning via manual version fields and record history.

### 5.2 Multi-Language OCR + Language-Specific Analyzers
- **Status**: CONFIRMED
- **Kreuzberg Evidence**: `OcrConfig(language="eng+fra+deu")` supports multi-language OCR. `LanguageDetectionConfig(enabled=True)` detects document language. EasyOCR supports 80+ languages.
- **SurrealDB Evidence**: `DEFINE ANALYZER` supports `snowball()` filter with 17 languages (Arabic through Turkish). Multiple analyzers can be defined, one per language. Multiple full-text indexes can be created on the same field using different analyzers.
- **Gotchas**: Need to pre-define analyzers for target languages. Routing documents to language-specific analyzers requires connector logic based on detected language.
- **Notes**: Feasible but adds complexity. Start with English-only in v1, add multi-language in v2.

### 9.1 Tenant-Isolated Document Stores
- **Status**: CONFIRMED
- **Kreuzberg Evidence**: Extraction is stateless.
- **SurrealDB Evidence**: `db.use("namespace", "database")` switches context. Each tenant can have their own namespace or database. Complete data isolation between namespaces.
- **Gotchas**: Connection pooling strategy needed. Switching namespaces on a shared connection may cause race conditions in async code.
- **Notes**: Simple namespace-per-tenant model. The connector accepts a tenant identifier and routes to the correct namespace.

### 10.5 Fuzzy Keyword Search with String Distance
- **Status**: CONFIRMED
- **Kreuzberg Evidence**: Extracted keywords provide the keyword corpus.
- **SurrealDB Evidence**: `string::distance::levenshtein()`, `string::distance::damerau_levenshtein()`, `string::similarity::jaro_winkler()`, `string::similarity::fuzzy()` are all built-in SurrealQL functions.
- **Gotchas**: These functions are computed at query time, not indexed. Performance on large keyword sets may be poor (full scan with function evaluation).
- **Notes**: Works for small-to-medium keyword tables. For large corpora, consider pre-computing fuzzy groups.

---

## Summary Table

| Feature | Tier | Status | Key Risk |
|---|---|---|---|
| 1.1 Universal Document Ingestion Pipeline | 1 | CONFIRMED | None |
| 2.1 Native Chunk Storage with Vector Index | 1 | CONFIRMED | HNSW is in-memory; persistence behavior unclear |
| 2.2 Embedding Preset to Index Config Mapping | 1 | CONFIRMED | None |
| 2.4 Full-Text Index on Chunk Content | 1 | CONFIRMED | Syntax differs between SurrealDB v2.x and v3.0 |
| 3.1 Local Embedding Generation + HNSW Storage | 1 | CONFIRMED | No standalone embed_text() API |
| 4.1 Rich Metadata Record Storage | 1 | CONFIRMED | Metadata schema varies by format |
| 8.1 High-Throughput Batch Ingestion | 1 | CONFIRMED | Partial failure handling needed |
| 10.1 Hybrid Search (Vector + BM25 + RRF) | 1 | CONFIRMED | Requires 3 sequential queries |
| A.7 Embedded Database for Testing/Dev | 1 | CONFIRMED | No transactions in embedded mode |
| 1.2 Per-Page Document Storage | 2 | CONFIRMED | Additional extraction overhead |
| 3.3 Query-Time Embedding + Vector Search | 2 | PARTIALLY_CONFIRMED | No standalone embed API in kreuzberg; needs FastEmbed direct |
| 4.2 Document Dates as SurrealDB Datetime | 2 | CONFIRMED | Timezone handling edge cases |
| 4.6 Quality Score as Relevance Weight | 2 | CONFIRMED | None |
| 6.1 Keyword Concept Graph | 2 | CONFIRMED | Keyword deduplication needed |
| 6.2 Document Hierarchy as Graph | 2 | CONFIRMED | Complex index-to-RecordID mapping |
| 6.4 Chunk Adjacency Graph | 2 | CONFIRMED | None |
| 7.1 Live Ingestion Monitoring | 2 | PARTIALLY_CONFIRMED | Single-node only; connection-dependent |
| 8.3 Transactional Batch Ingestion | 2 | PARTIALLY_CONFIRMED | WebSocket-only |
| 8.4 Incremental Re-Indexing | 2 | CONFIRMED | Connector must implement hash logic |
| 10.2 Metadata-Filtered Vector Search | 2 | CONFIRMED | Pre/post filter performance unclear |
| 10.7 Search Result Highlighting | 2 | CONFIRMED | BM25 only, not vector search |
| 11.1 Extraction Error Logging | 2 | CONFIRMED | None |
| A.2 Image Extraction + File Buckets | 2 | INFEASIBLE | SurrealDB v3.0 only; experimental |
| A.12 Document Deduplication via Hashing | 2 | CONFIRMED | Near-duplicate detection not covered |
| A.13 Chunk Page Range for Citation | 2 | CONFIRMED | Not all formats have page numbers |
| 1.3 Archive Recursive Extraction | 3 | PARTIALLY_CONFIRMED | Cannot access individual file results |
| 1.4 Email Thread Ingestion | 3 | PARTIALLY_CONFIRMED | Attachments not separately addressable |
| 3.2 Multi-Model Embedding Storage | 3 | PARTIALLY_CONFIRMED | Requires double extraction |
| 5.2 Multi-Language OCR + Analyzers | 3 | CONFIRMED | Complexity; defer to v2 |
| 6.6 Element-Based Knowledge Graph | 3 | PARTIALLY_CONFIRMED | Relationship inference is heuristic |
| 7.4 Real-Time Search Result Streaming | 3 | INFEASIBLE | LIVE SELECT does not support KNN/FTS |
| 9.1 Tenant-Isolated Document Stores | 3 | CONFIRMED | Connection pooling strategy needed |
| 10.5 Fuzzy Keyword Search | 3 | CONFIRMED | Not indexed; full scan at query time |
| A.9 SurrealML Re-Ranking | 3 | NEEDS_MORE_RESEARCH | Separate subsystem; unclear SDK support |
| A.14 Bounding Box Storage | 3 | PARTIALLY_CONFIRMED | No spatial index for doc coordinates |
| A.15 Agent Memory Store | 3 | PARTIALLY_CONFIRMED | Marketing concept; no special API |
| A.18 Aggregate Indexed Views | 3 | PARTIALLY_CONFIRMED | Materialized views need stability testing |
| A.19 Changefeed Embedding Updates | 3 | NEEDS_MORE_RESEARCH | SDK exposure unclear |
| A.20 Document Versioning Time-Series | 3 | INFEASIBLE | Experimental SurrealDB feature |

---

## Key Architectural Decisions Required

### 1. Query-Time Embedding Strategy
kreuzberg has no standalone `embed_text()` function. Options:
- **Option A**: Depend on `fastembed` directly for query embedding. Clean API but adds a direct dependency.
- **Option B**: Use kreuzberg's extraction pipeline on a text/plain bytes input. Inelegant but avoids extra dependency.
- **Option C**: Store a reference to the model name in the connector config and instantiate FastEmbed ourselves.
- **Recommendation**: Option A. FastEmbed is already a transitive dependency of kreuzberg. Using it directly for query embedding is natural and avoids the overhead of kreuzberg's full extraction pipeline.

### 2. SurrealDB Server Version Target
- **v2.x**: Stable, well-tested Python SDK (v1.0.8). Use `SEARCH ANALYZER` syntax. No file buckets.
- **v3.0**: New features (file buckets, FULLTEXT ANALYZER). Python SDK v2.0.0a1 is alpha. Syntax breaking changes.
- **Recommendation**: Target v2.x for v1 release. Support v3.0 syntax as a configuration option for early adopters. Track SDK stability.

### 3. Hybrid Search Implementation
Three queries required (vector, full-text, RRF fusion). Options:
- **Option A**: Three separate `db.query()` calls, binding results between them.
- **Option B**: Multi-statement SurrealQL query using LET bindings: `LET $vs = (SELECT ...); LET $ft = (SELECT ...); SELECT * FROM search::rrf([$vs, $ft], $limit, 60)`.
- **Recommendation**: Option B is more efficient (single round-trip). Test whether multi-statement queries work correctly with the Python SDK.

### 4. HNSW In-Memory Limitation
HNSW indexes are currently in-memory in SurrealDB. This means:
- Index is rebuilt on server restart
- Memory usage scales with vector count
- Large datasets may cause memory pressure
- **Recommendation**: Document this limitation. For production, recommend sufficient server memory. Monitor SurrealDB roadmap for persistent HNSW.

---

## Infeasible Features Summary

| Feature | Reason |
|---|---|
| A.2 Image Extraction + File Storage Buckets | SurrealDB v3.0 only, experimental |
| 7.4 Real-Time Search Result Streaming | LIVE SELECT does not support KNN/FTS predicates |
| A.20 Document Versioning via Time-Series | SurrealDB time-series is experimental |

---

## Web Research Sources

- [DEFINE INDEX statement](https://surrealdb.com/docs/surrealql/statements/define/indexes)
- [SurrealDB Vector Search](https://surrealdb.com/docs/surrealdb/models/vector)
- [Hybrid Search with RRF](https://surrealdb.com/blog/hybrid-vector-text-search-in-the-terminal-with-surrealdb-and-ratatui)
- [RELATE statement](https://surrealdb.com/docs/surrealql/statements/relate)
- [Python SDK insert_relation](https://surrealdb.com/docs/sdk/python/methods/insert-relation)
- [File support in SurrealDB 3.0](https://surrealdb.com/blog/file-support-in-surrealdb-3-0)
- [LIVE SELECT limitations](https://surrealdb.com/docs/surrealql/statements/live)
- [Python SDK streaming](https://surrealdb.com/docs/sdk/python/concepts/streaming)
- [DEFINE ANALYZER](https://surrealdb.com/docs/surrealql/statements/define/analyzer)
- [SurrealDB Full-Text Search](https://surrealdb.com/blog/create-a-search-engine-with-surrealdb-full-text-search)
- [Search functions](https://surrealdb.com/docs/surrealql/functions/database/search)
- [Kreuzberg features](https://docs.kreuzberg.dev/features/)
- [SurrealDB Features](https://surrealdb.com/features)
- [surrealdb PyPI](https://pypi.org/project/surrealdb/)
