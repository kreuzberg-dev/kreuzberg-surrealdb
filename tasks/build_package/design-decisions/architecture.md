# Architecture (D1, D2, D10)

Two classes, one shared base. User picks their mode by instantiating the right class. mypy catches misuse at compile time — no runtime mode checks.

| Class | Chunking | Embedding | Tables | Search | User profile |
|---|---|---|---|---|---|
| **DocumentConnector** | OFF | OFF | `documents` only | BM25 over full documents | "I want extracted text searchable in SurrealDB" |
| **DocumentPipeline** | ON (default) | ON (default) | `documents` + `chunks` | Hybrid + vector + BM25 over chunks | "I want a RAG pipeline" |

```python
class _BaseIngester:
    def __init__(
        self,
        *,
        db: DatabaseConfig,
        config: ExtractionConfig | None = None,
        index_config: IndexConfig | None = None,
    ) -> None: ...

    async def setup_schema(self) -> None: ...
    async def ingest_file(self, path: Path) -> None: ...
    async def ingest_files(self, paths: list[Path]) -> None: ...
    async def ingest_directory(self, dir: Path, glob: str = "**/*") -> None: ...
    async def ingest_bytes(self, data: bytes, mime_type: str, source: str) -> None: ...
    async def fulltext_search(self, query: str, limit: int = 10) -> list[dict]: ...

class DocumentConnector(_BaseIngester):
    async def search(self, query: str, limit: int = 10) -> list[dict]: ...
    # search() → BM25 over documents.content

class DocumentPipeline(_BaseIngester):
    def __init__(
        self,
        *,
        db: DatabaseConfig,
        chunk_table: str = "chunks",
        config: ExtractionConfig | None = None,
        embed: bool = True,
        index_config: IndexConfig | None = None,
    ) -> None: ...

    async def search(self, query: str, limit: int = 10) -> list[dict]: ...
    async def vector_search(self, query: str, limit: int = 10) -> list[dict]: ...
    # search() → hybrid (vector + BM25 + RRF) over chunks
    # vector_search() → pure HNSW semantic search over chunks
```

**Search behavior (D10):**
- `DocumentConnector.search()` → BM25 over `documents.content`
- `DocumentPipeline.search()` → hybrid (vector + BM25 + RRF) over `chunks`
- `fulltext_search()` → BM25, target differs per class
