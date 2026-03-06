# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - Unreleased

### Added

- `DocumentIngester` class for end-to-end document ingestion and search
- `setup_schema()` for automatic SurrealDB table, field, index, and analyzer creation
- `ingest_file()` for single-file extraction, chunking, embedding, and storage
- `ingest_directory()` for batch ingestion with glob pattern filtering
- `search()` for hybrid search (vector KNN + BM25 full-text + RRF fusion)
- `vector_search()` for pure semantic retrieval via HNSW
- `text_search()` for standalone BM25 keyword search
- Local embedding generation via kreuzberg's ONNX/FastEmbed runtime (no API keys)
- Configurable embedding presets: "balanced" (768d), "compact" (384d), "large" (1024d)
- Rich metadata storage: quality score, detected languages, keywords, document dates
- Document deduplication via SHA-256 content hashing
- Chunk page range tracking for citation (`first_page`, `last_page`)
- Embedded SurrealDB mode for testing (`memory://`)
- Type annotations and `py.typed` marker for static analysis
