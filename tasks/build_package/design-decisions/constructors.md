# Constructor Design (D13-D16)

**D13: DatabaseConfig** — connection, auth, table name, insert batch size. Single required param on both classes.

```python
@dataclass
class DatabaseConfig:
    db_url: str
    namespace: str = "default"
    database: str = "default"
    username: str | None = None
    password: str | None = None
    table: str = "documents"
    insert_batch_size: int = 100
```

**D14: IndexConfig** — HNSW, BM25, RRF, analyzer tuning. Optional on both classes. `analyzer_language` applies to both (DocumentConnector also has BM25).

```python
@dataclass
class IndexConfig:
    analyzer_language: str = "english"
    bm25_k1: float = 1.2
    bm25_b: float = 0.75
    distance_metric: str = "COSINE"
    hnsw_efc: int = 150
    hnsw_m: int = 12
    rrf_k: int = 60
```

**D15:** Chunking/embedding params delegated to kreuzberg's `ChunkingConfig` / `EmbeddingConfig` via `ExtractionConfig(chunking=ChunkingConfig(...))`. Supersedes D9, D12.

**D16: Final signatures:**

```python
class DocumentConnector:
    def __init__(
        self,
        *,
        db: DatabaseConfig,
        config: ExtractionConfig | None = None,
        index_config: IndexConfig | None = None,
    ) -> None: ...

class DocumentPipeline:
    def __init__(
        self,
        *,
        db: DatabaseConfig,
        chunk_table: str = "chunks",
        config: ExtractionConfig | None = None,
        embed: bool = True,
        index_config: IndexConfig | None = None,
    ) -> None: ...
```

`chunk_table` top-level on Pipeline only. `embed` controls HNSW index creation and search behavior — not a kreuzberg param.
