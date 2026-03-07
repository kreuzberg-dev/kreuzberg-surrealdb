# Methods (D7, D20)

**D7: All four ingestion methods — Yes**

All on `_BaseIngester`, available to both classes:

- `ingest_file(path)` — single file ingestion
- `ingest_files(paths)` — explicit list from different directories, batched DB inserts
- `ingest_directory(dir, glob)` — batch ingestion with glob filtering
- `ingest_bytes(data, mime_type, source)` — programmatic ingestion from API responses, downloads, in-memory data

**D20: setup_schema() — explicit, user-called**

Creates tables, indexes, and analyzers in SurrealDB. On `_BaseIngester`, available to both classes. Not called in the constructor — schema creation is idempotent but has side effects, so the user decides when to run it.

- `DocumentConnector.setup_schema()` → `documents` table + BM25 index + analyzer
- `DocumentPipeline.setup_schema()` → `documents` + `chunks` tables + all indexes + analyzer
