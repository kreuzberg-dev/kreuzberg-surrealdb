# Changelog

All notable changes to kreuzberg-surrealdb will be documented in this file.

## [0.1.1] — 2026-03-13

### Changed

- Bump minimum kreuzberg dependency from `>=4.4.4` to `>=4.4.6`
  - Better PDF extraction for positioned/tabular text (v4.4.5, #431)
  - DOCX image placeholder fix (v4.4.6, #484)
  - 13 additional file formats: dBASE (.dbf), HWP (.hwp/.hwpx), Office templates (.docm, .dotx, .dotm, .dot, .potx, .potm, .pot, .xltx, .xlt)

## [0.1.0] — 2026-03-08

Initial release.

### Added

- `DocumentConnector` — full-document extraction and BM25 search (no chunking or embeddings)
- `DocumentPipeline` — chunked extraction with local embeddings, hybrid search (vector + BM25 via RRF), and vector search
- `DatabaseConfig` / `IndexConfig` — configuration dataclasses for connection and index tuning
- Four ingestion methods: `ingest_file`, `ingest_files`, `ingest_directory`, `ingest_bytes`
- SHA-256 content-hash deduplication via deterministic record IDs
- Quality filtering on search results via `quality_threshold` parameter
- Detection of SurrealDB's silent INSERT IGNORE errors (dimension mismatch, etc.)
- Support for all kreuzberg embedding presets: `"fast"`, `"balanced"`, `"quality"`, `"multilingual"`
- Async context manager lifecycle for both classes
