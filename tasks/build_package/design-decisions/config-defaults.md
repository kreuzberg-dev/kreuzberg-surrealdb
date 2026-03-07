# Config Defaults (D3-D6)

**D3: namespace/database — "default"/"default"**

Library is neutral about deployment topology. Users who care pass explicit values. "default" is the standard SurrealDB convention. Table-level namespacing (D4) handles real separation.

**D4: Customizable table names — Yes**

`table` in `DatabaseConfig` (default "documents"), `chunk_table` on DocumentPipeline (default "chunks"). Enables multiple ingestion contexts in one database (e.g., "contracts" vs "emails").

**D5: output_format / ocr_backend — Not exposed**

Not top-level params. Users set these via `ExtractionConfig` (D6). Keeps constructor surface small.

**D6: ExtractionConfig escape hatch — Yes**

`config: ExtractionConfig | None = None` on both classes. Required given D5 — only way to customize extraction behavior (output format, OCR backend, etc.).
