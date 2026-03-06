# Potential Features: Kreuzberg + SurrealDB Connector

> Brainstorming document: combinations of kreuzberg and SurrealDB capabilities
> that create valuable connector features for RAG pipeline builders.
> Generated: 2026-03-06

---

## 1. Document Extraction + Storage

### 1.1 Universal Document Ingestion Pipeline

- **Kreuzberg Capability**: 75+ format support via `extract_file_sync/async` with MIME auto-detection (Section 2.1, Section 3)
- **SurrealDB Capability**: Schemaless document storage with `create()` / `insert()` (Section 5, Section 14 Multi-Model)
- **What it enables for RAG builders**: A single `ingest(path)` call that extracts text from any supported format (PDF, DOCX, XLSX, PPTX, EML, EPUB, HTML, Markdown, images, archives, etc.) and stores the result as a SurrealDB record with content, metadata, and provenance. Users never write extraction-to-storage glue code.
- **Feasibility Notes**: Straightforward. ExtractionResult maps cleanly to a SurrealDB document record. Need to define the canonical schema (table name, field mapping). MIME auto-detection eliminates format-specific branches.

### 1.2 Per-Page Document Storage

- **Kreuzberg Capability**: `PageConfig(extract_pages=True)` yields `list[PageContent]` with per-page content, tables, images (Section 4.11, Section 5.3)
- **SurrealDB Capability**: RecordID with structured IDs, record links between parent document and pages (Section 9 RecordID, Section 5 CRUD)
- **What it enables for RAG builders**: Each page stored as its own record (`page:doc123_p5`) linked to the parent document record. Enables page-level retrieval, page-level vector search, and precise citation with page numbers. Blank page detection (`is_blank`) allows skipping empty pages.
- **Feasibility Notes**: Need to design RecordID scheme for pages. The parent-child link can use SurrealDB record references (`record<document>`). Page numbering is 1-indexed from kreuzberg.

### 1.3 Archive Recursive Extraction + Storage

- **Kreuzberg Capability**: ZIP, RAR, 7Z, TAR, GZIP recursive extraction with archive metadata (file_count, file_list, total_size, compressed_size) (Section 3, Section 6 Archive-specific metadata)
- **SurrealDB Capability**: Graph edges via `insert_relation()` to model archive-contains-file relationships (Section 5 insert_relation, Section 14 Graph)
- **What it enables for RAG builders**: Ingest an entire archive and automatically extract + store every file inside it, with graph edges showing the containment hierarchy. Users can query "all documents from archive X" or traverse the archive structure.
- **Feasibility Notes**: Kreuzberg handles recursive extraction internally. Need to verify whether individual file results are accessible or only the combined result. Archive metadata (file_list) gives the manifest.

### 1.4 Email Thread Ingestion

- **Kreuzberg Capability**: EML/MSG extraction with email-specific metadata: from_email, to_emails, cc_emails, bcc_emails, message_id, attachments (Section 3, Section 6 Email-specific)
- **SurrealDB Capability**: Graph edges for sender->email->recipient relationships, attachment record links (Section 5 insert_relation, Section 14 Graph)
- **What it enables for RAG builders**: Ingest email files and automatically create a graph of communication: person nodes, email nodes, attachment nodes, with edges for sent/received/cc/attached. Enables queries like "all documents person X sent" or "all attachments in thread Y."
- **Feasibility Notes**: Email metadata extraction is well-supported in kreuzberg. The graph modeling is natural for SurrealDB. Need to handle duplicate person detection (same email address = same node).

### 1.5 Encrypted PDF Ingestion

- **Kreuzberg Capability**: `PdfConfig(passwords=["secret"])` for encrypted PDF extraction (Section 4.9)
- **SurrealDB Capability**: Field-level access control, namespace isolation (Section 14 Security & Auth)
- **What it enables for RAG builders**: Ingest password-protected PDFs and store the extracted content in access-controlled SurrealDB records. The password never needs to be stored; only the extracted content is persisted with appropriate access restrictions.
- **Feasibility Notes**: Straightforward combination. The connector would accept passwords at ingestion time, use them for extraction, then discard. SurrealDB's RBAC handles post-ingestion access control.

### 1.6 Multi-Format Output Storage

- **Kreuzberg Capability**: OutputFormat enum: plain, markdown, djot, html, structured (Section 4.1 OutputFormat)
- **SurrealDB Capability**: Multiple fields per record, schemaless flexibility (Section 14 Schema Options)
- **What it enables for RAG builders**: Store multiple representations of the same document simultaneously (plain text for embedding, markdown for display, HTML for rendering). A single extraction pass with `output_format="structured"` can populate different fields, or the connector can run multiple extractions.
- **Feasibility Notes**: Running multiple extractions is expensive. Better approach: extract once as markdown (richest text format), then derive plain text by stripping formatting. Or use structured output if it provides all needed representations. Need to verify what `OutputFormat.STRUCTURED` returns.

---

## 2. Chunking + Indexing

### 2.1 Native Chunk Storage with Vector Index

- **Kreuzberg Capability**: Native Rust chunking via `ChunkingConfig(max_chars, max_overlap)` with `ChunkMetadata` (byte offsets, chunk_index, total_chunks, token_count, page range) (Section 4.6, Section 5.2)
- **SurrealDB Capability**: HNSW vector embedding index with configurable distance metrics (euclidean/cosine/manhattan) (Section 14 Indexing)
- **What it enables for RAG builders**: Extract + chunk + embed + index in a single pipeline call. Kreuzberg produces chunks with embeddings; the connector stores each chunk as a SurrealDB record with a vector index for similarity search. ChunkMetadata provides byte offsets for source attribution.
- **Feasibility Notes**: Core feature. Need to define the chunk record schema. The HNSW index must be created via `DEFINE INDEX` SurrealQL statement. Chunk metadata (page range, byte offsets) enables precise citations.

### 2.2 Embedding Preset to Index Configuration Mapping

- **Kreuzberg Capability**: Embedding presets (balanced/compact/large) with known dimensions, plus custom FastEmbed models (Section 4.7 EmbeddingConfig, Section 2.7 list_embedding_presets)
- **SurrealDB Capability**: HNSW index definition requires dimension specification (Section 14 Indexing)
- **What it enables for RAG builders**: The connector auto-configures the SurrealDB HNSW index dimensions to match the kreuzberg embedding preset. Users pick a preset name ("balanced") and the connector handles both the embedding model setup and the index DDL.
- **Feasibility Notes**: Need to map preset names to dimensions. `get_embedding_preset(name)` returns `EmbeddingPreset` with `dimensions` field. The connector can generate `DEFINE INDEX ... HNSW DIMENSION {n} DIST COSINE` automatically.

### 2.3 Overlapping Chunk Deduplication via Compound Index

- **Kreuzberg Capability**: `max_overlap` in ChunkingConfig creates overlapping chunks for context continuity (Section 4.6)
- **SurrealDB Capability**: Unique compound indexes on multiple fields (Section 14 Indexing)
- **What it enables for RAG builders**: When re-ingesting a document, use a compound unique index on (document_id, chunk_index) to upsert chunks rather than creating duplicates. The overlap parameter can change between runs without creating orphan chunks.
- **Feasibility Notes**: Straightforward. Use `DEFINE INDEX chunk_unique ON chunk FIELDS document, chunk_index UNIQUE`. The `upsert()` SDK method handles insert-or-update.

### 2.4 Full-Text Index on Chunk Content

- **Kreuzberg Capability**: Extracted text content per chunk (Section 5.2 Chunk.content)
- **SurrealDB Capability**: Full-text indexing with BM25 ranking, relevance scoring, highlighting (Section 14 Indexing, Section 17 Search Functions)
- **What it enables for RAG builders**: Hybrid search: combine vector similarity (HNSW) with BM25 keyword relevance on the same chunk records. SurrealDB's `search::rrf()` (reciprocal rank fusion) can merge results from both search modes.
- **Feasibility Notes**: Define two indexes on the chunk table: one HNSW for embeddings, one full-text on content. Use `search::score()` and vector KNN together in a single query. This is a headline RAG feature.

### 2.5 Token-Count-Aware Chunk Sizing

- **Kreuzberg Capability**: ChunkMetadata includes `token_count` per chunk (Section 5.2)
- **SurrealDB Capability**: Computed fields in schema definitions (Section 14 Schema Options)
- **What it enables for RAG builders**: Store token counts alongside chunks so retrieval can respect LLM context window budgets. A query can select chunks where `SUM(token_count) < budget`, enabling precise context assembly.
- **Feasibility Notes**: Token count is already computed by kreuzberg. The connector just needs to persist it. SurrealDB math functions (`math::sum`) enable aggregation queries on token counts.

---

## 3. Embeddings + Vector Search

### 3.1 Local Embedding Generation + HNSW Storage

- **Kreuzberg Capability**: Per-chunk embeddings via FastEmbed models, computed in Rust (Section 4.7 EmbeddingConfig, Section 11)
- **SurrealDB Capability**: HNSW vector index, KNN operator `<|K,METRIC|>` (Section 14 Indexing, Section 16 Search Operators)
- **What it enables for RAG builders**: Fully local, no-API-key embedding pipeline. Kreuzberg generates embeddings locally using FastEmbed; the connector stores them in SurrealDB's vector index. No OpenAI/Cohere API calls needed.
- **Feasibility Notes**: Core feature. FastEmbed models run locally in Rust. The generated `list[float]` embeddings map directly to SurrealDB's vector field type. KNN search via `<|K, COSINE|>` provides retrieval.

### 3.2 Multi-Model Embedding Storage

- **Kreuzberg Capability**: `EmbeddingModelType.fastembed()` and `EmbeddingModelType.custom()` allow multiple embedding models (Section 4.7)
- **SurrealDB Capability**: Multiple HNSW indexes on different fields of the same table (Section 14 Indexing)
- **What it enables for RAG builders**: Store embeddings from multiple models (e.g., a compact model for fast search and a large model for high-accuracy re-ranking) on the same chunk record. Users can query either index depending on latency vs. accuracy needs.
- **Feasibility Notes**: Requires running extraction twice with different embedding configs, or extending the connector to support multi-pass embedding. Each embedding field gets its own `DEFINE INDEX`. Need to verify SurrealDB supports multiple HNSW indexes per table.

### 3.3 Query-Time Embedding + Vector Search

- **Kreuzberg Capability**: Embedding generation can be used standalone on query text (Section 4.7, Section 11)
- **SurrealDB Capability**: KNN search operator in SurrealQL queries (Section 16 Search Operators)
- **What it enables for RAG builders**: The connector provides a `search(query_text, top_k)` method that embeds the query using the same model used for indexing, then runs KNN search against the HNSW index. Ensures query-document embedding consistency.
- **Feasibility Notes**: Need to verify that kreuzberg's embedding API can embed arbitrary text strings (not just extracted document content). If it only embeds during chunking, we may need to extract-from-bytes a text string to generate its embedding, or call FastEmbed directly.

### 3.4 Cosine/Euclidean/Manhattan Distance Selection

- **Kreuzberg Capability**: EmbeddingConfig.normalize controls vector normalization (Section 4.7)
- **SurrealDB Capability**: HNSW supports euclidean, cosine, manhattan distance metrics (Section 14 Indexing)
- **What it enables for RAG builders**: Normalized embeddings (default) work best with cosine distance. The connector can auto-select the distance metric based on the normalization setting: normalized = cosine, unnormalized = euclidean.
- **Feasibility Notes**: Simple config mapping. Cosine is the standard choice for normalized embeddings. Expose distance metric as a connector option with a sensible default.

---

## 4. Metadata + Enrichment

### 4.1 Rich Metadata Record Storage

- **Kreuzberg Capability**: Format-discriminated Metadata TypedDict with common fields (title, authors, language, dates) and format-specific fields (PDF: version/encryption/page_count, Excel: sheet_names, Email: addresses, HTML: open_graph/structured_data) (Section 6)
- **SurrealDB Capability**: Schemaless nested object storage, field-level querying (Section 14 Schema Options, Section 17 Object Functions)
- **What it enables for RAG builders**: All extracted metadata stored as queryable fields. Filter documents by author, date range, language, format type, page count, or any format-specific field. Enables faceted search over the document corpus.
- **Feasibility Notes**: Straightforward. Kreuzberg's Metadata TypedDict maps directly to a SurrealDB nested object. Format-specific fields are naturally handled by schemaless storage. Consider schemafull mode for common fields to ensure consistency.

### 4.2 Document Dates as SurrealDB Datetime

- **Kreuzberg Capability**: Metadata fields `created_at`, `modified_at` as ISO 8601 strings (Section 6 Common Fields)
- **SurrealDB Capability**: Native `datetime` type with RFC 3339, temporal operators, `time::*` functions (Section 9 Datetime, Section 18 Temporal Types, Section 17 Time Functions)
- **What it enables for RAG builders**: Store document dates as native SurrealDB datetimes, enabling temporal queries: "documents modified in the last 30 days", "documents created between 2024-01 and 2024-06", "sort by creation date." Time functions like `time::year()`, `time::month()` enable grouping.
- **Feasibility Notes**: Parse kreuzberg's ISO 8601 strings into SurrealDB `Datetime` objects during ingestion. The SDK's `Datetime(dt: str)` accepts ISO 8601 directly.

### 4.3 PDF Annotation Storage + Search

- **Kreuzberg Capability**: `PdfConfig(extract_annotations=True)` yields `list[PdfAnnotation]` with type, content, page_number, bounding_box (Section 4.9, Section 5.8)
- **SurrealDB Capability**: Nested array storage, full-text search on annotation content (Section 14 Indexing)
- **What it enables for RAG builders**: Store PDF annotations (highlights, comments, stamps, links) as searchable records linked to their source document and page. Users can search across all highlights/comments in a corpus, or find annotations on specific pages.
- **Feasibility Notes**: Annotations can be stored as separate records with graph edges to their source document/page, or as nested arrays within the document record. Separate records enable independent full-text search on annotation content.

### 4.4 HTML Structured Data Preservation

- **Kreuzberg Capability**: HTML metadata includes open_graph, twitter_card, meta_tags, structured_data (JSON-LD/Microdata), headers, links, images (Section 6 HTML-specific)
- **SurrealDB Capability**: Deep nested object storage, object functions (`object::keys`, `object::entries`) (Section 17 Object Functions)
- **What it enables for RAG builders**: Ingest web pages and preserve their structured data (Open Graph, Schema.org JSON-LD) as queryable SurrealDB fields. Enables queries like "find all pages with og:type = article" or "pages with Schema.org Product data."
- **Feasibility Notes**: Straightforward JSON-to-document mapping. Schema.org structured data can be particularly valuable for knowledge graph construction.

### 4.5 Image EXIF Metadata + Geolocation

- **Kreuzberg Capability**: Image metadata includes EXIF data with GPS coordinates (Section 6 Image-specific, `exif: dict`)
- **SurrealDB Capability**: GeoJSON GeometryPoint type, geo functions (`geo::distance`, `geo::hash::encode`), geo operators (`OUTSIDE`, `INTERSECTS`) (Section 9 Geometry Types, Section 14 Geospatial, Section 17 Geo Functions)
- **What it enables for RAG builders**: Extract GPS coordinates from photo EXIF data and store them as SurrealDB GeometryPoint values. Enables geospatial queries: "find documents with photos taken within 5km of this location." Useful for field reports, site inspections, geotagged documentation.
- **Feasibility Notes**: Need to parse EXIF GPS data into latitude/longitude. Not all images have GPS data. The connector should handle missing EXIF gracefully. SurrealDB's `GeometryPoint(longitude, latitude)` matches GeoJSON convention.

### 4.6 Quality Score as Computed Relevance Weight

- **Kreuzberg Capability**: `quality_score: float` from `enable_quality_processing=True` (default on) (Section 5.1 ExtractionResult)
- **SurrealDB Capability**: Computed/derived fields, math functions in queries (Section 14 Schema Options, Section 17 Math Functions)
- **What it enables for RAG builders**: Store kreuzberg's quality score and use it as a relevance weight during retrieval. Low-quality extractions (corrupted PDFs, poor OCR) get down-ranked. Queries can filter `WHERE quality_score > 0.7` or weight vector scores by quality.
- **Feasibility Notes**: Quality score is a float between 0 and 1. Can be stored directly and used in scoring formulas. Define a computed field or use it in query-time ranking.

### 4.7 Processing Warnings as Diagnostic Records

- **Kreuzberg Capability**: `processing_warnings: list[ProcessingWarning]` with source and message (Section 5.9)
- **SurrealDB Capability**: Nested array storage, string search functions (Section 17 String Functions)
- **What it enables for RAG builders**: Store extraction warnings alongside documents for quality monitoring. Dashboard queries like "documents with OCR warnings", "documents where table detection failed", "count of warnings by source." Enables pipeline health monitoring.
- **Feasibility Notes**: Straightforward. Warnings are small text records. Can be stored as nested arrays or as separate diagnostic records linked to the document.

---

## 5. OCR + Search

### 5.1 OCR-Extracted Text with Full-Text Index

- **Kreuzberg Capability**: OCR backends (tesseract/paddleocr/easyocr) extract text from images, with configurable confidence thresholds (Section 7, Section 4.2, Section 4.3)
- **SurrealDB Capability**: Full-text indexing with BM25 ranking (Section 14 Indexing)
- **What it enables for RAG builders**: Scanned documents and images become full-text searchable. The connector OCRs images, stores the extracted text, and creates a BM25 full-text index. Users search across both native-text and OCR-extracted documents with a single query.
- **Feasibility Notes**: Core use case. OCR quality varies; the confidence threshold in TesseractConfig can filter low-confidence results. The `force_ocr=True` option handles PDFs that contain only images.

### 5.2 Multi-Language OCR + Language-Specific Analyzers

- **Kreuzberg Capability**: OCR language parameter `"eng+fra+deu"`, language detection with confidence (Section 4.2, Section 4.12 LanguageDetectionConfig), 80+ EasyOCR languages (Section 7.4)
- **SurrealDB Capability**: Full-text indexing with per-field analyzers (via `DEFINE ANALYZER`) (Section 14 Indexing)
- **What it enables for RAG builders**: Documents in different languages get language-appropriate full-text analysis (stemming, stopword removal). Kreuzberg detects the language; the connector routes the content to a language-specific SurrealDB analyzer. Enables multilingual corpus search.
- **Feasibility Notes**: Need to verify SurrealDB analyzer configuration for different languages. The `DEFINE ANALYZER` statement supports tokenizers and filters. Language detection from kreuzberg provides the routing signal. May need to pre-define analyzers for common languages.

### 5.3 OCR Confidence Filtering for Quality Control

- **Kreuzberg Capability**: TesseractConfig.min_confidence, table_min_confidence (Section 4.3)
- **SurrealDB Capability**: Record-level access control, conditional indexing (Section 14 Security & Auth)
- **What it enables for RAG builders**: Only index OCR results that meet a confidence threshold. Low-confidence extractions are stored but flagged, preventing garbage text from polluting search results. A quality gate between extraction and indexing.
- **Feasibility Notes**: Implement as a connector option: `min_ocr_confidence`. Results below threshold are stored with a flag (`ocr_quality: "low"`) but excluded from the full-text/vector index via conditional queries.

### 5.4 Table OCR with Structured Storage

- **Kreuzberg Capability**: OCR table detection with bounding boxes, table inlining in markdown (Section 4.3 TesseractConfig table detection, v4.4.1 changes), `ExtractedTable` with cells grid and markdown (Section 5.1)
- **SurrealDB Capability**: Nested object/array storage, querying into nested structures (Section 14 Schema Options, Section 17 Array Functions)
- **What it enables for RAG builders**: Tables detected via OCR in scanned documents are stored as structured 2D arrays in SurrealDB, not just flattened text. Users can query individual cell values, filter rows, or reconstruct the table for display.
- **Feasibility Notes**: The `cells: list[list[str]]` structure maps directly to SurrealDB nested arrays. Bounding boxes (from v4.4.1) can be stored for visual document reconstruction.

### 5.5 Image Preprocessing Pipeline + OCR Storage

- **Kreuzberg Capability**: ImagePreprocessingConfig: DPI, rotation, deskew, denoise, contrast, binarization (Section 4.4)
- **SurrealDB Capability**: Document storage with processing provenance (Section 5 CRUD)
- **What it enables for RAG builders**: Configure image preprocessing for optimal OCR quality and store the preprocessing parameters alongside the result. Enables reproducibility: re-process with different settings if quality is poor. The connector can store which preprocessing was applied.
- **Feasibility Notes**: Preprocessing config is metadata about the extraction, not the content. Store it in a `processing_config` field on the document record for audit/reproducibility.

---

## 6. Graph Features

### 6.1 Keyword Concept Graph

- **Kreuzberg Capability**: YAKE/RAKE keyword extraction with scores, ngram range, positions (Section 4.13 KeywordConfig, Section 5.7 ExtractedKeyword)
- **SurrealDB Capability**: Graph edges via RELATE/insert_relation, bi-directional traversal (Section 5 insert_relation, Section 14 Graph)
- **What it enables for RAG builders**: Automatically build a concept graph: document nodes linked to keyword nodes via weighted edges (keyword score as edge weight). Enables concept-based retrieval: "find all documents about 'machine learning'" traverses the keyword graph. Shared keywords create implicit document similarity.
- **Feasibility Notes**: Create a `keyword` table and `mentions` edge table. Each extracted keyword becomes a node; each document-keyword relationship becomes an edge with score and algorithm as edge properties. Keyword deduplication (case-insensitive matching) is important.

### 6.2 Document Hierarchy as Graph

- **Kreuzberg Capability**: `DocumentStructure` with `DocumentNode` tree: parent/children indices, node_type (title/heading/paragraph/list/table/image/code/quote/formula), content_layer, page range, bounding boxes (Section 5.6)
- **SurrealDB Capability**: Record links, recursive graph traversal, graph RAG (Section 14 Graph, Section 14 AI Agent Support)
- **What it enables for RAG builders**: Store document internal structure as a navigable graph. Each heading, paragraph, table, and image becomes a node with parent-child edges. Enables structural queries: "find all tables under the 'Results' heading", "get the paragraph after this figure." Graph RAG can traverse document structure for context-aware retrieval.
- **Feasibility Notes**: The DocumentNode tree maps naturally to SurrealDB graph structure. Nodes have `parent` and `children` references. Node types become record fields or discriminated by table (one table per type vs. one table with type field). The `content_layer` field (body/header/footer/footnote) adds another dimension.

### 6.3 Cross-Document Reference Graph

- **Kreuzberg Capability**: HTML metadata includes links (Section 6 HTML-specific), PDF annotations include links (Section 5.8 PdfAnnotation link type)
- **SurrealDB Capability**: Graph edges between document records, recursive traversal (Section 14 Graph)
- **What it enables for RAG builders**: When documents reference each other (HTML links, PDF link annotations), create graph edges between document records. Enables citation graph traversal, PageRank-style importance scoring, and "related documents" features.
- **Feasibility Notes**: Link resolution is tricky: the target URL/path must match an existing document in the store. The connector would need a URL-to-document mapping. PDF links may be internal (page references) or external (URLs).

### 6.4 Chunk Adjacency Graph

- **Kreuzberg Capability**: ChunkMetadata with chunk_index, total_chunks, byte offsets (Section 5.2)
- **SurrealDB Capability**: Graph edges with ordering, RELATE statement (Section 5 insert_relation, Section 14 Graph)
- **What it enables for RAG builders**: Create `next_chunk` and `prev_chunk` edges between sequential chunks. During retrieval, after finding a relevant chunk via vector search, the system can traverse to adjacent chunks for expanded context (sliding window retrieval).
- **Feasibility Notes**: Simple sequential edges based on chunk_index. The overlap region between chunks can be represented as edge metadata. This pattern is common in RAG systems for context expansion.

### 6.5 Author/Creator Collaboration Graph

- **Kreuzberg Capability**: Metadata fields: authors (list), created_by, modified_by (Section 6 Common Fields)
- **SurrealDB Capability**: Graph modeling with person and document nodes (Section 14 Graph)
- **What it enables for RAG builders**: Build an author collaboration graph: person nodes connected to document nodes via "authored" edges. Multiple authors on a document create implicit co-authorship edges. Enables queries like "all documents by this author", "co-authors of person X", "most prolific authors."
- **Feasibility Notes**: Author name normalization is challenging (different name formats, aliases). Start with exact string matching; advanced implementations could use string similarity functions (`string::similarity::fuzzy`) for fuzzy matching.

### 6.6 Element-Based Knowledge Graph

- **Kreuzberg Capability**: Element-based result format with typed elements: title, narrative_text, heading, list_item, table, image, code_block, block_quote (Section 5.5 Element)
- **SurrealDB Capability**: Multi-table graph with typed edges (Section 14 Graph, Multi-Model)
- **What it enables for RAG builders**: Each document element becomes a graph node with typed relationships: heading -> contains -> paragraphs, table -> follows -> paragraph, code_block -> illustrates -> narrative_text. Enables fine-grained structural retrieval and element-type filtering.
- **Feasibility Notes**: Requires `result_format="element_based"`. The element_type field provides natural node typing. Relationship inference (which elements belong under which heading) needs heuristic logic based on document order and element hierarchy.

---

## 7. Real-Time Features

### 7.1 Live Ingestion Monitoring

- **Kreuzberg Capability**: Batch extraction functions with per-file results (Section 2.1 batch_extract_files)
- **SurrealDB Capability**: Live queries (`LIVE SELECT`) with real-time notifications (Section 7, Section 14 Real-Time)
- **What it enables for RAG builders**: Subscribe to a live query on the document table to get real-time notifications as documents are ingested. Dashboard showing ingestion progress, newly added documents, extraction failures. Frontend apps can update their UI without polling.
- **Feasibility Notes**: Requires WebSocket or embedded connection (HTTP does not support live queries). The connector would create records during ingestion, and any client subscribed via `LIVE SELECT` sees them appear instantly.

### 7.2 Index Rebuild Notifications

- **Kreuzberg Capability**: Re-extraction with different configs (e.g., new chunking parameters) (Section 4.1 ExtractionConfig)
- **SurrealDB Capability**: Live queries on chunk/index tables, table events (Section 7, Section 14 Real-Time)
- **What it enables for RAG builders**: When a document is re-indexed (different chunk size, new embedding model), live queries notify dependent systems. A search frontend can display "index updating..." and refresh when complete. Event-driven pipeline orchestration.
- **Feasibility Notes**: Table events can trigger downstream processing. The connector would update chunk records during re-indexing, and live query subscribers see the changes. Need to handle the transition period where old and new chunks coexist.

### 7.3 Document Change Feed for Pipeline Triggers

- **Kreuzberg Capability**: Document re-extraction capability (same file, different config or updated file) (Section 2.1)
- **SurrealDB Capability**: Change feeds via `SHOW` statement (Section 15 SurrealQL Statements)
- **What it enables for RAG builders**: Track document changes over time. When a document is re-ingested (updated version), the change feed shows what changed. Enables incremental pipeline processing: only re-embed chunks that actually changed, not the entire document.
- **Feasibility Notes**: Change feeds are a SurrealDB feature for auditing table modifications. Need to verify if `SHOW CHANGES FOR TABLE` is exposed through the Python SDK. The connector would compare old vs. new extraction results to identify changed chunks.

### 7.4 Real-Time Search Result Streaming

- **Kreuzberg Capability**: Async extraction functions for non-blocking operation (Section 2.1, Section 10)
- **SurrealDB Capability**: Live queries with diff mode (`diff=True` returns JSON Patch) (Section 7)
- **What it enables for RAG builders**: As new documents are ingested and indexed, search results update in real time. A user running a search sees new matches appear as documents are added to the corpus. Useful for monitoring/alerting scenarios.
- **Feasibility Notes**: This requires the search query to be expressed as a `LIVE SELECT` with a WHERE clause. Need to verify if SurrealDB supports live queries with KNN/full-text predicates. May be limited to simple field matching.

---

## 8. Batch/Scale Features

### 8.1 High-Throughput Batch Ingestion

- **Kreuzberg Capability**: `batch_extract_files_sync/async` with Rust rayon parallelism, `max_concurrent_extractions` config (Section 2.1, Section 4.1, Section 10)
- **SurrealDB Capability**: `insert(table, [records])` bulk insert (Section 5 CRUD)
- **What it enables for RAG builders**: Ingest thousands of documents with maximum throughput. Kreuzberg extracts in parallel (Rust rayon), the connector batches results, and SurrealDB bulk-inserts them. A `max_concurrent_extractions` parameter prevents resource exhaustion.
- **Feasibility Notes**: Core feature for production use. Need to handle partial failures (some files fail extraction). The connector should collect results and errors, bulk-insert successes, and report failures. Consider batch size tuning for SurrealDB insert.

### 8.2 Batch Bytes Ingestion (API/Stream Sources)

- **Kreuzberg Capability**: `batch_extract_bytes_sync/async` with parallel MIME type lists (Section 2.1)
- **SurrealDB Capability**: Bulk insert with parameterized queries (Section 5, Section 6)
- **What it enables for RAG builders**: Ingest documents from API responses, message queues, or streams where content arrives as bytes (not files). The connector accepts `list[tuple[bytes, str]]` (data + MIME type) and processes them in batch.
- **Feasibility Notes**: MIME type is required for bytes input. The connector should accept MIME types explicitly or auto-detect via `detect_mime_type()`. Useful for webhook-based ingestion (Slack attachments, email APIs, S3 events).

### 8.3 Transactional Batch Ingestion

- **Kreuzberg Capability**: Batch extraction returns `list[ExtractionResult]` (Section 2.1)
- **SurrealDB Capability**: Transactions via WebSocket sessions: BEGIN, INSERT, COMMIT/CANCEL (Section 8)
- **What it enables for RAG builders**: Wrap a batch ingestion in a transaction so either all documents are stored or none are (atomic ingestion). If any document fails post-processing validation, the entire batch is rolled back. Prevents partial/inconsistent corpus state.
- **Feasibility Notes**: Transactions require WebSocket connection. The connector would: extract all files (kreuzberg), begin transaction, insert all records (SurrealDB), commit. If any insert fails, cancel the transaction. Need to handle the case where extraction succeeds but storage fails.

### 8.4 Incremental Re-Indexing

- **Kreuzberg Capability**: Content hashing (via quality_score / content comparison), MIME detection (Section 2.2, Section 5.1)
- **SurrealDB Capability**: Upsert operation, compound unique indexes (Section 5 upsert, Section 14 Indexing)
- **What it enables for RAG builders**: Re-ingest a directory and only update changed documents. The connector computes a content hash (e.g., from file bytes), checks if the hash matches the stored record, and skips unchanged files. Only changed documents get re-extracted and re-embedded.
- **Feasibility Notes**: Content hashing is not a kreuzberg feature per se; the connector would hash the raw bytes before extraction. Store the hash in a `content_hash` field with a unique index. Check hash before extraction to skip unchanged files.

### 8.5 Concurrent Extraction + Storage Pipeline

- **Kreuzberg Capability**: True async extraction via Rust tokio (Section 10)
- **SurrealDB Capability**: Async SDK (`AsyncSurreal`) with full API parity (Section 1, Section 3)
- **What it enables for RAG builders**: Fully async pipeline: extract and store concurrently using `asyncio.gather()` or task groups. While one document is being extracted, another is being stored. Maximizes throughput on I/O-bound workloads.
- **Feasibility Notes**: Both libraries support true async. The connector can use an async producer-consumer pattern: extraction tasks produce results into a queue, storage tasks consume and persist them. Backpressure management is important.

---

## 9. Security & Auth

### 9.1 Tenant-Isolated Document Stores

- **Kreuzberg Capability**: Document extraction is stateless (no auth context) (Section 2.1)
- **SurrealDB Capability**: Namespace/database-level isolation, multi-tenant with separate compute/storage (Section 14 Security & Auth)
- **What it enables for RAG builders**: Each tenant gets their own SurrealDB namespace or database. The connector accepts a tenant identifier and routes documents to the correct namespace. Documents from different tenants are completely isolated with no cross-tenant search leakage.
- **Feasibility Notes**: Use SurrealDB's `db.use(namespace, database)` to switch tenant context before operations. The connector wraps this with a tenant-aware API. Consider connection pooling per tenant vs. namespace switching on a shared connection.

### 9.2 Record-Level Access Control on Documents

- **Kreuzberg Capability**: Metadata extraction includes authors, sensitivity indicators (Section 6)
- **SurrealDB Capability**: Record-level access control with field-level permissions, RBAC (Section 14 Security & Auth)
- **What it enables for RAG builders**: Restrict document access based on user roles. Documents tagged with certain metadata (e.g., "confidential" in keywords) can have access rules that limit who can read them. Scoped record authentication ensures users only see documents they have access to.
- **Feasibility Notes**: Requires SurrealDB access definitions (`DEFINE ACCESS`). The connector would set access control during ingestion based on metadata signals. This is primarily a SurrealDB schema/security configuration concern; the connector provides the metadata.

### 9.3 JWT-Scoped Search

- **Kreuzberg Capability**: N/A (extraction side has no auth concept)
- **SurrealDB Capability**: Scoped record authentication, JWT with custom claims (Section 4 Authentication)
- **What it enables for RAG builders**: Search API endpoints authenticate with JWT tokens that carry user/role claims. SurrealDB enforces access rules on the records: a user's search results only include documents they're authorized to see. No application-level filtering needed.
- **Feasibility Notes**: This is primarily a SurrealDB feature. The connector's role is to set up the access definitions and document metadata that enable this filtering. The search function would pass through the authenticated connection.

---

## 10. Advanced Search

### 10.1 Hybrid Search (Vector + BM25 + RRF)

- **Kreuzberg Capability**: Chunk embeddings (Section 4.7, Section 11) + extracted text content (Section 5.2)
- **SurrealDB Capability**: HNSW vector index + BM25 full-text index + `search::rrf()` reciprocal rank fusion (Section 14 Indexing, Section 17 Search Functions)
- **What it enables for RAG builders**: Combine semantic similarity (vector) with lexical matching (BM25) for best-of-both-worlds retrieval. `search::rrf()` fuses the two ranked lists. Handles both "conceptually similar" and "exact keyword match" queries.
- **Feasibility Notes**: Headline feature. Define two indexes on the chunk table. Write a SurrealQL query that runs both searches and merges results via RRF. The connector provides a `hybrid_search(query, top_k, alpha)` method where `alpha` controls the vector/keyword balance.

### 10.2 Metadata-Filtered Vector Search

- **Kreuzberg Capability**: Rich metadata extraction: format_type, language, authors, dates, page_count (Section 6)
- **SurrealDB Capability**: WHERE clauses combined with KNN operator (Section 16 Operators)
- **What it enables for RAG builders**: Vector search with metadata filters: "find similar chunks, but only from PDF documents authored by 'Smith' after 2024." Combines semantic retrieval with structured filtering. Essential for enterprise RAG where corpus partitioning matters.
- **Feasibility Notes**: SurrealDB's query language supports WHERE clauses alongside KNN. Need to verify if pre-filtering or post-filtering is used (affects performance). Store metadata on chunk records (denormalized from parent document) for efficient filtered search.

### 10.3 Multilingual Hybrid Search

- **Kreuzberg Capability**: Language detection (`detected_languages`), multi-language OCR (Section 4.12, Section 7), keyword extraction with language param (Section 4.13)
- **SurrealDB Capability**: Per-field analyzers via `DEFINE ANALYZER`, multiple full-text indexes (Section 14 Indexing)
- **What it enables for RAG builders**: Define language-specific analyzers (English stemmer, German compound word splitter, CJK tokenizer) and route documents to the appropriate analyzer based on detected language. Multilingual corpus with language-appropriate search.
- **Feasibility Notes**: Requires pre-defining analyzers for target languages. The connector detects the language during ingestion and stores content in a language-tagged field or selects the appropriate analyzer. May need separate content fields per language or a single field with a dynamic analyzer.

### 10.4 Table Content Search

- **Kreuzberg Capability**: ExtractedTable with cells grid and markdown representation (Section 5.1)
- **SurrealDB Capability**: Full-text search on nested fields, array containment operators (Section 16 Containment Operators)
- **What it enables for RAG builders**: Search within extracted tables specifically. "Find tables containing 'revenue' in any cell." Tables are structured data, so users can also query by position: "find tables where the header row contains 'Price'."
- **Feasibility Notes**: Store tables as separate records (not just nested in document records) with their own full-text index on the markdown field. Cell-level querying requires array access patterns. SurrealDB's `CONTAINS` operators work on arrays.

### 10.5 Fuzzy Keyword Search with String Distance

- **Kreuzberg Capability**: Extracted keywords with scores (Section 5.7 ExtractedKeyword)
- **SurrealDB Capability**: String distance/similarity functions: `string::distance::levenshtein`, `string::similarity::jaro_winkler`, `string::similarity::fuzzy` (Section 17 String Functions)
- **What it enables for RAG builders**: Search for keywords with fuzzy matching to handle typos and variations. "Find documents about 'machne learning'" matches "machine learning" via Levenshtein distance. Combines with the keyword concept graph for powerful concept search.
- **Feasibility Notes**: String similarity functions are SurrealQL built-ins. Use them in WHERE clauses on the keyword table: `WHERE string::distance::levenshtein(text, $query) < 3`. Performance may be a concern for large keyword sets without indexing.

### 10.6 Geospatial Document Search

- **Kreuzberg Capability**: Image EXIF GPS extraction (Section 6 Image-specific), document metadata with location-relevant fields
- **SurrealDB Capability**: GeoJSON types, geo functions (`geo::distance`, `geo::hash`), INTERSECTS/OUTSIDE operators (Section 9 Geometry Types, Section 14 Geospatial, Section 17 Geo Functions)
- **What it enables for RAG builders**: Search documents by geographic location: "find all documents with images taken within 10km of this point." Useful for field reports, construction documentation, geographic research. Geo hash encoding enables efficient spatial indexing.
- **Feasibility Notes**: Depends on EXIF GPS data being present. Not all documents have geographic metadata. The connector should extract GPS data when available and store as GeometryPoint. Geospatial indexes are listed as "planned" in SurrealDB, so current support may rely on function-based filtering.

### 10.7 Search Result Highlighting

- **Kreuzberg Capability**: Text content extraction (Section 5.1 content field)
- **SurrealDB Capability**: `search::highlight()` and `search::offsets()` functions (Section 17 Search Functions)
- **What it enables for RAG builders**: Full-text search results include highlighted snippets showing where the match occurred. Essential for user-facing search interfaces. The `search::offsets()` function provides exact character positions for custom highlighting.
- **Feasibility Notes**: Requires BM25 full-text index. `search::highlight()` returns HTML-marked-up text. `search::offsets()` returns position arrays. The connector's search method can return both the raw content and highlighted snippets.

---

## 11. Observability

### 11.1 Extraction Error Logging to SurrealDB

- **Kreuzberg Capability**: ErrorCode enum (SUCCESS through MISSING_DEPENDENCY), exception hierarchy (KreuzbergError subtypes), `get_error_details()`, `classify_error()` (Section 2.5, Section 9)
- **SurrealDB Capability**: Record creation with timestamps, querying for error patterns (Section 5 CRUD, Section 17 Time Functions)
- **What it enables for RAG builders**: Log extraction errors as SurrealDB records: error code, message, file path, timestamp, exception type. Enables pipeline health dashboards: "X% OCR failures this week", "most common error codes", "files that consistently fail."
- **Feasibility Notes**: Create an `extraction_error` table. Each failed extraction creates a record with error details. SurrealDB's time functions enable temporal analysis. Consider whether to store in the same database as documents or a separate diagnostics database.

### 11.2 OpenTelemetry Tracing Across Extraction + Storage

- **Kreuzberg Capability**: Extraction timing (implicit in async operations) (Section 10)
- **SurrealDB Capability**: Pydantic Logfire integration, OpenTelemetry tracing (Section 19 Observability)
- **What it enables for RAG builders**: End-to-end tracing from document extraction through storage. See how long each phase takes: file read, OCR, chunking, embedding, database insert. Identify bottlenecks in the pipeline. Traces export to Jaeger, DataDog, or Honeycomb.
- **Feasibility Notes**: SurrealDB has native Logfire/OTel integration. Kreuzberg does not have built-in tracing, but the connector can wrap extraction calls in OTel spans. The connector is the tracing bridge between the two libraries.

### 11.3 Ingestion Pipeline Metrics

- **Kreuzberg Capability**: quality_score, processing_warnings, detected_languages, chunk counts (Section 5.1 ExtractionResult)
- **SurrealDB Capability**: Aggregate queries, math functions (`math::mean`, `math::sum`, `math::stddev`) (Section 17 Math Functions)
- **What it enables for RAG builders**: Query pipeline metrics directly from SurrealDB: average quality score, total documents ingested, documents per format type, average chunks per document, language distribution. No separate metrics system needed for basic analytics.
- **Feasibility Notes**: Store metrics as fields on document records. Aggregate queries provide real-time analytics. For high-volume systems, consider pre-computed aggregate indexed views (SurrealDB feature) to avoid slow full-table scans.

### 11.4 Panic Context Diagnostics

- **Kreuzberg Capability**: `get_last_panic_context()` returns JSON with file, line, function, message, timestamp from Rust panics (Section 2.5, Section 9.3 PanicContext)
- **SurrealDB Capability**: Record storage with structured error data (Section 5 CRUD)
- **What it enables for RAG builders**: When kreuzberg's Rust core panics (rare but possible with corrupted files), capture the panic context and store it in SurrealDB for debugging. Enables post-mortem analysis of Rust-level crashes.
- **Feasibility Notes**: Panic context is thread-local and may not always be available. The connector should try-catch around extraction calls and capture panic context on failure. Store in a `panic_log` table for developer review.

---

## 12. Plugin/Extension

### 12.1 Custom OCR Backend with SurrealDB-Backed Model Config

- **Kreuzberg Capability**: `register_ocr_backend()` with OcrBackendProtocol (Section 2.4, Section 8.2)
- **SurrealDB Capability**: Configuration storage as records, key-value lookup (Section 5 CRUD, Section 14 Multi-Model Key-Value)
- **What it enables for RAG builders**: Store OCR backend configurations (model paths, language settings, confidence thresholds) in SurrealDB. Register custom OCR backends that read their config from the database. Enables runtime OCR configuration changes without code deployment.
- **Feasibility Notes**: The OcrBackendProtocol's `initialize()` method can read config from SurrealDB. The custom backend wraps any OCR engine and pulls its settings from the database. Niche feature but valuable for managed deployments.

### 12.2 Post-Processor for SurrealDB Enrichment

- **Kreuzberg Capability**: `register_post_processor()` with PostProcessorProtocol: process(result) -> result, processing stages (early/middle/late) (Section 2.4, Section 8.1)
- **SurrealDB Capability**: Query existing records for enrichment data (Section 6 Query Methods)
- **What it enables for RAG builders**: Register a post-processor that enriches extraction results with data from SurrealDB before storage. Example: look up the author in a person table to add department/role metadata. Or check if the document already exists for deduplication.
- **Feasibility Notes**: The post-processor would need a SurrealDB connection. It runs during extraction (before the connector's storage step), so it can modify the ExtractionResult. Processing stage "late" runs after all extraction is complete.

### 12.3 Validator for Schema Enforcement

- **Kreuzberg Capability**: `register_validator()` with ValidatorProtocol: validate(result) raises on failure, priority-ordered (Section 2.4, Section 8.3)
- **SurrealDB Capability**: Schemafull table definitions with field type constraints (Section 14 Schema Options)
- **What it enables for RAG builders**: Register validators that enforce business rules before storage: minimum content length, required metadata fields, allowed languages, quality score thresholds. Failed validation prevents storage and logs the reason.
- **Feasibility Notes**: Validators run during extraction. The connector can register a validator that checks if the result meets storage requirements (e.g., non-empty content, valid MIME type). This is a quality gate before database insertion.

### 12.4 Custom Embedding Model via Plugin

- **Kreuzberg Capability**: `EmbeddingModelType.custom(model_id, dimensions)` (Section 4.7)
- **SurrealDB Capability**: HNSW index with configurable dimensions (Section 14 Indexing)
- **What it enables for RAG builders**: Use any ONNX-compatible embedding model, not just the built-in presets. The connector auto-configures the HNSW index dimensions to match the custom model. Enables domain-specific embedding models (legal, medical, scientific).
- **Feasibility Notes**: Custom models must be ONNX-compatible and FastEmbed-loadable. The connector needs the dimension count to create the correct HNSW index. `EmbeddingModelType.custom()` requires `model_id` and `dimensions` parameters.

---

## Additional Cross-Cutting Combinations

### A.1 Token Reduction + Storage Optimization

- **Kreuzberg Capability**: TokenReductionConfig with modes: off/light/moderate/aggressive/maximum (Section 4.14)
- **SurrealDB Capability**: Storage efficiency with schemaless records (Section 14 Storage & Scalability)
- **What it enables for RAG builders**: Apply token reduction before storage to reduce database size. "Maximum" reduction strips all non-essential tokens. Useful for cost-sensitive deployments where storage size matters more than full content preservation. Store the original format in file storage, reduced text in the search index.
- **Feasibility Notes**: Token reduction is lossy. The connector could store both the full content and a reduced version: full content for display, reduced content for embedding/search. This doubles storage per document but improves retrieval precision.

### A.2 Image Extraction + File Storage Buckets

- **Kreuzberg Capability**: ImageExtractionConfig extracts images from documents as bytes with metadata (format, dimensions, page_number, bounding_box, OCR result) (Section 4.8, Section 5.4)
- **SurrealDB Capability**: File storage buckets (memory/filesystem/S3/GCS/Azure), `file::put/get/delete` functions (Section 14 File Storage, Section 17 File Functions)
- **What it enables for RAG builders**: Extract images from PDFs/DOCX/PPTX and store them in SurrealDB file storage buckets. Each image record links to its source document and page. Enables image retrieval, thumbnail generation, and multimodal RAG where images are retrieved alongside text.
- **Feasibility Notes**: Image data is `bytes` in ExtractedImage. Use `file::put()` to store in a bucket, then link the file reference to the document record. Bucket type selection (S3 for production, filesystem for development, memory for testing) is a deployment concern.

### A.3 Document Structure + Hierarchical Records

- **Kreuzberg Capability**: `include_document_structure=True` yields DocumentStructure with typed nodes (title, heading, paragraph, list, table, image, code, quote, formula, footnote, group, page_break) (Section 4.1, Section 5.6)
- **SurrealDB Capability**: Nested objects, record links for hierarchical modeling (Section 14 Multi-Model, Section 5 CRUD)
- **What it enables for RAG builders**: Store document structure as navigable hierarchical records. Query by structure: "find all code blocks in chapter 3", "get the table of contents (all heading nodes)", "extract formulas from section 2.1." Enables structured document navigation in RAG-powered apps.
- **Feasibility Notes**: Two storage strategies: (1) flat records with parent/child record links (graph approach), or (2) deeply nested objects preserving the tree structure. The graph approach is more queryable. Node `content_layer` (body/header/footer/footnote) enables filtering by document region.

### A.4 Math/Formula Extraction + Structured Storage

- **Kreuzberg Capability**: OMML-to-LaTeX conversion for DOCX math equations (v4.4.2), DocumentNode.node_type = "formula" (Section 5.6, Section 16 v4.4.2)
- **SurrealDB Capability**: String storage with search, regex type (Section 18 Specialized Types)
- **What it enables for RAG builders**: Extract mathematical formulas from documents as LaTeX strings and store them as searchable records. Researchers can search for specific equations across a corpus. Formula nodes link to their containing section for context.
- **Feasibility Notes**: LaTeX strings are plain text and store easily. Searching for formulas by content requires exact or fuzzy string matching. SurrealDB's regex type could enable pattern-based formula search (e.g., "equations containing integral signs").

### A.5 Spreadsheet Sheet-Level Storage

- **Kreuzberg Capability**: Excel-specific metadata: sheet_count, sheet_names (Section 6 Excel-specific), per-page extraction can map to per-sheet (Section 4.11)
- **SurrealDB Capability**: Record creation with structured data, array functions (Section 5 CRUD, Section 17 Array Functions)
- **What it enables for RAG builders**: Store each spreadsheet sheet as a separate record with the sheet name as metadata. Tables within each sheet are stored as structured cell grids. Enables queries like "find sheets named 'Revenue'" across all spreadsheets in the corpus.
- **Feasibility Notes**: Kreuzberg's per-page mode may map to per-sheet for spreadsheets (need to verify). Sheet names from metadata provide natural record identifiers. Table extraction from spreadsheets should produce well-structured cell grids.

### A.6 PowerPoint Slide-Level Storage

- **Kreuzberg Capability**: PowerPoint-specific metadata: slide_count, slide_names (Section 6 PowerPoint-specific), per-page extraction maps to per-slide (Section 4.11)
- **SurrealDB Capability**: Record creation with linked records (Section 5 CRUD)
- **What it enables for RAG builders**: Each presentation slide becomes a searchable record linked to the parent presentation. Slide titles, speaker notes, and embedded tables are individually searchable. Enables "find all slides about topic X across all presentations."
- **Feasibility Notes**: Similar to per-page PDF storage. Slide names provide natural titles. Speaker notes may or may not be captured by kreuzberg (need to verify). Images from slides can be stored via file storage buckets.

### A.7 Embedded Database for Testing/Development

- **Kreuzberg Capability**: All extraction functions work identically regardless of storage backend (Section 2.1)
- **SurrealDB Capability**: Embedded in-memory (`Surreal("memory")`) and embedded file (`Surreal("file://path")`) connections (Section 3)
- **What it enables for RAG builders**: The connector works identically with an embedded SurrealDB (no server needed) for development/testing and a remote WebSocket server for production. Users can prototype locally with `memory` mode and deploy to a distributed cluster without code changes.
- **Feasibility Notes**: Excellent developer experience. The connector should accept a connection URL and work with any SurrealDB connection mode. Embedded mode has live query support but no transactions. Test suites can use `memory` for fast, isolated tests.

### A.8 Annotation-Based Knowledge Extraction

- **Kreuzberg Capability**: PDF annotations (highlight, text, link, stamp, underline, strike_out) with content and bounding boxes (Section 5.8)
- **SurrealDB Capability**: Full-text search on annotation content, graph edges to source document (Section 14 Indexing, Section 14 Graph)
- **What it enables for RAG builders**: Treat human annotations (highlights, comments) as first-class knowledge artifacts. A researcher's highlighted passages and comments become searchable, linkable records. Multiple reviewers' annotations on the same document create a discussion graph.
- **Feasibility Notes**: Annotations with content (text type and comments) are most valuable. Highlights without text content would need the underlying text extracted via bounding box + page content correlation. This is a premium feature for academic/legal use cases.

### A.9 SurrealML Integration for Re-Ranking

- **Kreuzberg Capability**: Chunk extraction with quality scores (Section 5.1, Section 5.2)
- **SurrealDB Capability**: SurrealML ONNX-backed inference, `.surml` model format (Section 14 ML Integration)
- **What it enables for RAG builders**: Deploy a re-ranking model as a `.surml` model in SurrealDB. After initial vector retrieval, the model re-ranks results considering the query, chunk content, quality score, and metadata. Re-ranking happens server-side, reducing round trips.
- **Feasibility Notes**: SurrealML is an advanced feature. The re-ranking model would need to be trained separately and exported to ONNX format. The connector's role is providing well-structured chunk data that the model can consume. This is aspirational for v1.

### A.10 Configuration Discovery + Storage

- **Kreuzberg Capability**: `ExtractionConfig.discover()` searches cwd + parents, `.from_file()` loads from TOML/YAML/JSON, `config_to_json()` serialization (Section 2.3)
- **SurrealDB Capability**: Key-value record storage (Section 14 Multi-Model Key-Value)
- **What it enables for RAG builders**: Store extraction configurations in SurrealDB as named records. Users can switch between configs ("ocr_heavy", "fast_text_only", "full_enrichment") by name. Config history tracked as record versions. Share configs across pipeline instances via the database.
- **Feasibility Notes**: `config_to_json()` serializes the config. Store the JSON in a `config` table with a name key. `ExtractionConfig` cannot be constructed from JSON directly (need to verify), so the connector may need to parse the JSON back into the config class.

### A.11 MIME Type Registry in SurrealDB

- **Kreuzberg Capability**: `detect_mime_type()`, `get_extensions_for_mime()`, format-specific metadata (Section 2.2, Section 2.7)
- **SurrealDB Capability**: Set operations (`set::union`, `set::intersect`), aggregate queries (Section 17 Set Functions)
- **What it enables for RAG builders**: Track which MIME types are present in the corpus, how many documents of each type, which extensions map to which types. Enables format-aware pipeline routing: "apply OCR config to image types, text config to text types."
- **Feasibility Notes**: Simple metadata aggregation. Store MIME type on every document record. Aggregate queries provide corpus composition statistics. Format-specific routing is a connector configuration concern.

### A.12 Document Deduplication via Content Hashing

- **Kreuzberg Capability**: Content extraction produces deterministic text for the same input (Section 2.1)
- **SurrealDB Capability**: Crypto hash functions (`crypto::sha256`, `crypto::blake3`), unique indexes (Section 17 Crypto Functions, Section 14 Indexing)
- **What it enables for RAG builders**: Compute a hash of extracted content (or raw bytes) and store it in a unique-indexed field. Duplicate documents are detected at insert time. The connector skips re-extraction for already-stored content. Near-duplicate detection via content similarity is also possible.
- **Feasibility Notes**: Hash the extracted content string via `crypto::sha256` in SurrealQL, or compute the hash in Python before insert. Unique index on the hash field prevents duplicates. Near-duplicate detection would require additional logic (e.g., SimHash, MinHash) beyond simple hashing.

### A.13 Chunk Page Range for Citation

- **Kreuzberg Capability**: ChunkMetadata includes `first_page` and `last_page` (Section 5.2)
- **SurrealDB Capability**: Range type with bounds (Section 9 Range and Bounds)
- **What it enables for RAG builders**: Store the page range of each chunk as a SurrealDB Range value. When a chunk is retrieved in a RAG query, the page range provides precise citation: "Source: document.pdf, pages 5-7." Enables the LLM to generate citations in its response.
- **Feasibility Notes**: SurrealDB's Range type with BoundIncluded is a natural fit. The page range can also be stored as two integer fields (first_page, last_page) for simpler querying. Range type enables range intersection queries: "chunks overlapping page 5."

### A.14 Bounding Box Storage for Visual Document AI

- **Kreuzberg Capability**: BoundingBox on tables, images, annotations, and document nodes (Section 5.1, Section 5.4, Section 5.6, Section 5.8)
- **SurrealDB Capability**: Nested object storage, GeoJSON Polygon type (Section 9 Geometry Types)
- **What it enables for RAG builders**: Store bounding box coordinates for visual document understanding. Given a user's click position on a document rendering, find the element at that location. Enable visual Q&A: "what does this table show?" where "this table" is identified by bounding box.
- **Feasibility Notes**: Bounding boxes could be stored as GeoJSON Polygons (treating page coordinates as a 2D plane), enabling SurrealDB's INTERSECTS operator for spatial queries. However, this repurposes geographic operators for document coordinates, which is unconventional. Simple nested objects may be more appropriate.

### A.15 SurrealDB as Agent Memory Store

- **Kreuzberg Capability**: Full document extraction pipeline (all features) (Section 2.1)
- **SurrealDB Capability**: AI agent memory support: structured + unstructured + vectors + graphs, conversation history, prompt-response storage (Section 14 AI Agent Support)
- **What it enables for RAG builders**: The connector feeds extracted documents into SurrealDB's unified agent memory. An AI agent can reference documents (vector search), traverse document relationships (graph), recall previous conversations about documents (session storage), and maintain structured knowledge (document metadata) all in one database.
- **Feasibility Notes**: This is the full vision of the connector. SurrealDB's AI agent support is designed for this use case. The connector is the bridge that populates the agent's memory with real-world document knowledge. MCP integration enables AI tools to query the document store directly.

### A.16 Element-Type-Specific Embedding

- **Kreuzberg Capability**: Element-based extraction with typed elements (title, narrative_text, heading, code_block, table, etc.) (Section 5.5)
- **SurrealDB Capability**: Per-table or per-field HNSW indexes (Section 14 Indexing)
- **What it enables for RAG builders**: Embed different element types separately. Narrative text gets embedded with a general-purpose model; code blocks get embedded with a code-specific model; tables get embedded with a table-understanding model. Store each type in its own table with its own vector index.
- **Feasibility Notes**: Requires multiple embedding models, which increases complexity. The connector would route elements to type-specific embedding pipelines. This is an advanced feature for specialized RAG applications (e.g., technical documentation where code search is critical).

### A.17 Count Index for Corpus Statistics

- **Kreuzberg Capability**: Batch extraction produces many records (Section 2.1)
- **SurrealDB Capability**: Count indexes for pre-computed record counts (Section 14 Indexing)
- **What it enables for RAG builders**: Instant corpus statistics: total documents, documents per format, documents per language, chunks per document. Count indexes make these queries O(1) instead of scanning the entire table. Essential for dashboard and monitoring UIs.
- **Feasibility Notes**: Define count indexes on frequently queried groupings. `DEFINE INDEX count_by_format ON document FIELDS format_type COUNT`. The SurrealDB count index feature needs verification for current availability.

### A.18 Aggregate Indexed Views for Analytics

- **Kreuzberg Capability**: Quality scores, metadata fields, chunk counts across documents (Section 5.1, Section 6)
- **SurrealDB Capability**: Aggregate indexed views with pre-computed analytics and windowing (Section 14 Indexing)
- **What it enables for RAG builders**: Pre-computed analytics views: average quality score by format type, document count by language, ingestion rate over time. These views update automatically as documents are added, providing instant analytics without expensive aggregation queries.
- **Feasibility Notes**: Aggregate indexed views are a SurrealDB feature listed in the indexing section. Need to verify current availability and syntax. If available, this is a powerful feature for pipeline monitoring dashboards.

### A.19 Changefeed-Driven Embedding Updates

- **Kreuzberg Capability**: Re-extraction with updated configs (new embedding model) (Section 2.1, Section 4.7)
- **SurrealDB Capability**: SHOW CHANGES changefeed, table events (Section 14 Real-Time, Section 15 SurrealQL Statements)
- **What it enables for RAG builders**: When an embedding model is updated, table events trigger re-embedding of affected chunks. The changefeed tracks which documents have been re-embedded and which are still pending. Enables rolling embedding model upgrades across a large corpus.
- **Feasibility Notes**: Table events can invoke serverless-style handlers. The re-embedding process would read the chunk content, generate new embeddings with the new model, and update the embedding field. This is a distributed systems challenge (ensuring consistency during the transition).

### A.20 Document Versioning via Time-Series

- **Kreuzberg Capability**: Document re-extraction produces new ExtractionResult for updated files (Section 2.1)
- **SurrealDB Capability**: Time-series with versioned temporal tables (experimental) (Section 14 Multi-Model)
- **What it enables for RAG builders**: Track document versions over time. When a document is updated and re-ingested, the previous version is preserved in the time-series. Users can query "what did this document say last month?" or diff versions. Enables audit trails for regulated industries.
- **Feasibility Notes**: Time-series support is listed as experimental in SurrealDB. Need to verify current status and API. The connector would store each ingestion as a timestamped version. This is a premium feature for compliance-heavy use cases (legal, financial, medical).

---

## Summary Statistics

| Category | Feature Count |
|---|---|
| 1. Document Extraction + Storage | 6 |
| 2. Chunking + Indexing | 5 |
| 3. Embeddings + Vector Search | 4 |
| 4. Metadata + Enrichment | 7 |
| 5. OCR + Search | 5 |
| 6. Graph Features | 6 |
| 7. Real-Time Features | 4 |
| 8. Batch/Scale Features | 5 |
| 9. Security & Auth | 3 |
| 10. Advanced Search | 7 |
| 11. Observability | 4 |
| 12. Plugin/Extension | 4 |
| Additional Cross-Cutting | 20 |
| **Total** | **80** |

---

## Priority Tiers (suggested)

### Tier 1 -- Core (must-have for v1)
- 1.1 Universal Document Ingestion Pipeline
- 2.1 Native Chunk Storage with Vector Index
- 2.2 Embedding Preset to Index Configuration Mapping
- 2.4 Full-Text Index on Chunk Content
- 3.1 Local Embedding Generation + HNSW Storage
- 4.1 Rich Metadata Record Storage
- 8.1 High-Throughput Batch Ingestion
- 10.1 Hybrid Search (Vector + BM25 + RRF)
- A.7 Embedded Database for Testing/Development

### Tier 2 -- High Value (v1 stretch or v2)
- 1.2 Per-Page Document Storage
- 3.3 Query-Time Embedding + Vector Search
- 4.2 Document Dates as SurrealDB Datetime
- 4.6 Quality Score as Computed Relevance Weight
- 6.1 Keyword Concept Graph
- 6.2 Document Hierarchy as Graph
- 6.4 Chunk Adjacency Graph
- 7.1 Live Ingestion Monitoring
- 8.3 Transactional Batch Ingestion
- 8.4 Incremental Re-Indexing
- 10.2 Metadata-Filtered Vector Search
- 10.7 Search Result Highlighting
- 11.1 Extraction Error Logging to SurrealDB
- A.2 Image Extraction + File Storage Buckets
- A.12 Document Deduplication via Content Hashing
- A.13 Chunk Page Range for Citation

### Tier 3 -- Advanced (future)
- Everything else
