# kreuzberg-surrealdb v0.1.0 — Task List

## Phase 2: Build

> **References:**
> - Feature list: `tasks/build_package/initial_feature_list.md`
> - Design decisions: `tasks/build_package/design-decisions/`

Sequential — each step depends on prior steps being complete.

- [x] Initialize project: `uv init`, src layout, pyproject.toml (hatchling)
- [x] Set up tooling: ruff, mypy strict, pytest + pytest-asyncio, pre-commit
- [x] Publish workflow to PyPI (`.github/workflows/publish.yaml`)
- [x] Declare runtime dependencies in pyproject.toml: `kreuzberg>=4.4.3`, `surrealdb>=1.0.8,<3.0`, `fastembed>=0.7.4`
- [x] Fix CI: Python 3.10-3.13 matrix for unit tests, integration job uses `mem://` embedded SurrealDB (no service container needed — `mem://` runs SurrealDB's Rust engine in-process), lint job runs pre-commit hooks
  - **Plan deviation:** SurrealDB service container removed from CI — all integration tests use `mem://` embedded engine, no Docker or network required
- [x] Implement `DatabaseConfig`, `IndexConfig` dataclasses (`src/kreuzberg_surrealdb/config.py`)
- [x] Implement schema module (`src/kreuzberg_surrealdb/schema.py`) — `build_document_schema()`, `build_connector_schema()`, `build_pipeline_schema()` generating parameterized SurrealQL DDL
- [x] Implement `_BaseIngester` (`src/kreuzberg_surrealdb/ingester.py`) — connection lifecycle, auth, all four ingestion methods (`ingest_file`, `ingest_files`, `ingest_directory`, `ingest_bytes`), SHA-256 content hashing, ExtractionConfig forwarding, full metadata mapping
  - **Plan deviation (dedup):** `INSERT IGNORE` only deduplicates by record ID in SurrealDB, NOT by UNIQUE indexes. Changed to use `RecordID(table, content_hash)` as explicit `id` field for natural dedup
  - **Plan deviation (AsyncSurreal):** `AsyncSurreal(url=...)` is a factory function (not awaited); requires separate `await db.connect()` call
- [x] Implement `fulltext_search(query, limit=10)` as public method on `_BaseIngester`
- [x] Implement `DocumentConnector` — document-level BM25 search, delegates to `fulltext_search()`
- [x] Implement `DocumentPipeline` — chunking, embedding, hybrid/vector/BM25 search, `embed=False` mode, chunk metadata with `token_count`/`first_page`/`last_page`
  - **Plan deviation (dimensions):** "balanced" preset = `BGEBaseENV15` = 768 dimensions (not 384 as initially planned)
  - **Plan deviation (query embedding):** Uses fastembed `TextEmbedding` directly with model name resolved from kreuzberg's `_PRESET_TO_FASTEMBED` mapping
- [x] Update `__init__.py` public API exports — `DatabaseConfig`, `IndexConfig`, `DocumentConnector`, `DocumentPipeline`, `__version__`
- [x] Write unit tests (mocked SurrealDB SDK) — 50 tests across `test_config.py`, `test_schema.py`, `test_connector.py`, `test_pipeline.py`; covers `embed=True`/`embed=False`, all ingestion methods, dedup, search modes
  - **Plan deviation (test style):** All tests are functional (`test_` functions), not class-based — per user preference
- [x] Write integration tests (`tests/test_integration.py`, `@pytest.mark.integration`) — 9 tests using `mem://` embedded SurrealDB; covers both connector and pipeline, dedup, fulltext search
- [x] Hit 80%+ coverage — achieved 93% (unit tests only, without integration)
- [ ] Write examples — `examples/basic_ingest.py` and `examples/rag_pipeline.py` exist as stubs (docstring only), need full implementation. `rag_pipeline.py` must include LLM SDK integration with env var API key handling
- [ ] Write `examples/README.md` — does not exist yet
- [ ] Write project README — current `README.md` is a 5-line stub, needs full documentation (installation, quickstart, API reference, configuration)
- [ ] Update CHANGELOG.md — current version references old `DocumentIngester` class name, needs update to reflect actual API (`DocumentConnector`, `DocumentPipeline`)
- [ ] Final ruff + mypy --strict pass — mypy passes clean, ruff has 7 auto-fixable errors (import sorting, unused imports in test files)
- [ ] Tag `v0.1.0`, verify publish workflow
