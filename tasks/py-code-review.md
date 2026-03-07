# Python Code Review

**Scope:** full
**Files reviewed:** 11 (4 source, 7 test)
**Tools:** ruff 0.15.4 [7 issues] | mypy 1.19.1 strict [0 source errors, 68 test errors]
**Changelogs:** 3.12, 3.13, 3.14
**Aspects:** quality, clean, types

---

## Critical Issues (3)

1. **[Mutates caller's config]** `ingester.py:218` — `_build_extraction_config` mutates the user-supplied `ExtractionConfig` in-place (confidence: 95)

   If the same config is reused across multiple pipelines, the chunking config from the first leaks into subsequent ones.

   ```python
   # Before
   if self._config is not None:
       self._config.chunking = chunking
       return self._config

   # After
   import copy

   if self._config is not None:
       config = copy.copy(self._config)
       config.chunking = chunking
       return config
   ```

2. **[Blocking event loop]** `ingester.py:278-285` — `_embed_query` runs synchronous CPU-bound fastembed inference on the async event loop (confidence: 95)

   `TextEmbedding()` constructor (downloads/loads model) and `.embed()` (inference) are both blocking. This starves all concurrent coroutines.

   ```python
   # Before
   async def _embed_query(self, query: str) -> list[float]:
       if self._embedding_model is None:
           from fastembed import TextEmbedding
           self._embedding_model = TextEmbedding(model_name=self._fastembed_model_name)
       embeddings = list(self._embedding_model.embed([query]))
       return embeddings[0].tolist()

   # After
   import asyncio

   async def _embed_query(self, query: str) -> list[float]:
       if self._embedding_model is None:
           from fastembed import TextEmbedding
           loop = asyncio.get_running_loop()
           self._embedding_model = await loop.run_in_executor(
               None, TextEmbedding, self._fastembed_model_name,
           )
       loop = asyncio.get_running_loop()
       embeddings = await loop.run_in_executor(
           None, lambda: list(self._embedding_model.embed([query])),
       )
       return embeddings[0].tolist()
   ```

3. **[SQL injection risk]** `config.py`, `schema.py`, `ingester.py` — Table names, `distance_metric`, and `analyzer_language` are user-supplied strings interpolated directly into SurQL via f-strings with no validation (confidence: 90)

   ```python
   # After — add validation in config.py
   import re

   _IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
   _VALID_DISTANCE_METRICS = frozenset({"COSINE", "EUCLIDEAN", "MANHATTAN", "MINKOWSKI", "CHEBYSHEV"})

   @dataclass
   class DatabaseConfig:
       table: str = "documents"
       # ...
       def __post_init__(self) -> None:
           if not _IDENTIFIER_RE.match(self.table):
               msg = f"Invalid table name: {self.table!r}"
               raise ValueError(msg)
           if self.insert_batch_size < 1:
               msg = "insert_batch_size must be >= 1"
               raise ValueError(msg)

   @dataclass
   class IndexConfig:
       distance_metric: str = "COSINE"
       # ...
       def __post_init__(self) -> None:
           if self.distance_metric not in _VALID_DISTANCE_METRICS:
               msg = f"Invalid distance metric: {self.distance_metric!r}"
               raise ValueError(msg)
   ```

---

## Warnings (6)

4. **[Type hole]** `ingester.py:81` — `_client: Any` defeats all type checking on SurrealDB API calls (confidence: 95)

   Every `.query()`, `.connect()`, `.signin()`, `.use()`, `.close()` call is unchecked. Wrong method names or argument types would not be caught.

   ```python
   # Before
   self._client: Any = None

   # After
   from surrealdb.connections.async_template import AsyncTemplate
   self._client: AsyncTemplate | None = None
   ```

5. **[No None guard]** `ingester.py:124,159,172,236,273,301,320` — All methods access `self._client` without checking for `None`; crashes with `AttributeError` if called before `connect()` (confidence: 95)

   ```python
   # After — add a guard property
   @property
   def _db(self) -> Any:  # or AsyncTemplate
       if self._client is None:
           msg = "Not connected. Call connect() or use 'async with' first."
           raise RuntimeError(msg)
       return self._client
   ```

6. **[Connection leak]** `ingester.py:83-94` — If `signin()` or `use()` raises after `connect()`, the client is leaked (confidence: 85)

   ```python
   # After
   async def connect(self) -> None:
       client = AsyncSurreal(url=self._db_config.db_url)
       try:
           await client.connect()
           if self._db_config.username and self._db_config.password:
               await client.signin({...})
           await client.use(self._db_config.namespace, self._db_config.database)
       except Exception:
           await client.close()
           raise
       self._client = client
   ```

7. **[Silent auth skip]** `ingester.py:87` — Auth silently skipped when only one of username/password is provided (confidence: 90)

   ```python
   # After — validate in DatabaseConfig.__post_init__ or connect()
   if bool(self._db_config.username) != bool(self._db_config.password):
       msg = "Both username and password must be provided, or neither"
       raise ValueError(msg)
   ```

8. **[Zero batch size]** `config.py:18` — `insert_batch_size=0` causes `ValueError: range() arg 3 must not be zero`; negative values silently drop all records (confidence: 95)

   Covered in the `__post_init__` fix in Critical Issue #3.

9. **[Type hole]** `ingester.py:195` — `_embedding_model: Any` defeats fastembed type checking (confidence: 85)

   ```python
   # After (TYPE_CHECKING guard to avoid import-time cost)
   if TYPE_CHECKING:
       from fastembed import TextEmbedding
   self._embedding_model: TextEmbedding | None = None
   ```

---

## Suggestions (5)

10. **[DRY]** `ingester.py:238-276` — `DocumentPipeline._ingest_result` bypasses `_insert_documents` with inline query calls, duplicating the insert pattern (confidence: 85)

11. **[Literal types]** `config.py:24,21` — `distance_metric` and `analyzer_language` could use `Literal` types for compile-time validation (confidence: 80)

12. **[KeyError]** `ingester.py:202` — `_PRESET_TO_FASTEMBED[preset_info.model_name]` raises a raw `KeyError` if kreuzberg adds a new preset model (confidence: 80)

13. **[method-assign]** `test_pipeline.py:226,244` — Monkey-patching `_embed_query` with direct assignment; use `patch.object` instead (confidence: 95)

    ```python
    # Before
    pipeline._embed_query = AsyncMock(return_value=[0.1] * 768)

    # After
    with patch.object(pipeline, "_embed_query", new_callable=AsyncMock, return_value=[0.1] * 768):
        result = await pipeline.search("test query", limit=5)
    ```

14. **[union-attr]** `test_pipeline.py:44,49` — Access `.chunking` on `_config` without `None` guard; add `assert pipeline._config is not None` (confidence: 95)

---

## Lint Issues (ruff auto-fixable)

Run `uv run ruff check --fix tests/` to resolve all 7:
- **F401** Unused imports: `MagicMock` (test_connector, test_pipeline), `DatabaseConfig` (test_pipeline), `Path` (test_integration)
- **I001** Unsorted import blocks: test_connector, test_pipeline, test_schema

**Dead code:** `make_query_result` in `conftest.py:68-70` is never called — remove it.

---

## Version Compatibility

No deprecated or removed API usage detected for Python 3.10-3.14. The codebase uses `from __future__ import annotations` correctly for 3.10+ compatibility.

---

## Scores

| Dimension | Score | Notes |
|---|---|---|
| Code Quality | 6/10 | Good architecture; config mutation, event loop blocking, and missing input validation are significant |
| Cleanliness | 8/10 | Clean source modules with good docstrings; test files have minor dead code and import issues |
| Type Safety | 6/10 | Source passes strict mypy, but `_client: Any` and `_embedding_model: Any` create large unchecked surfaces |
| **Overall** | **7/10** | Well-structured for an early-stage package; fix the 3 critical issues before release |

---

## Tool Recommendations

Both ruff and mypy are installed and configured well. Consider:
- Running `ruff check --fix` to auto-resolve all 7 test lint issues
- Adding `ANN` enforcement selectively to test fixtures in `conftest.py` for consistency
