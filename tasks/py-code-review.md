# Python Code Review

**Scope:** full
**Files reviewed:** 11 (4 source, 7 test)
**Tools:** ruff 0.15.4 [7 issues] | mypy 1.19.1 strict [0 source errors, 68 test errors]
**Reviews:** py-review + code-reviewer agent (deduplicated, merged)
**Changelogs:** 3.12, 3.13, 3.14
**Aspects:** quality, clean, types, security

---

## Critical Issues (2)

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

2. **[SQL injection risk]** `config.py`, `schema.py`, `ingester.py` — Table names, `distance_metric`, and `analyzer_language` are user-supplied strings interpolated directly into SurQL via f-strings with no validation (confidence: 90)

   Affected surfaces: `schema.py:10` (`analyzer_language` into `snowball()`), `schema.py:19-34,43-45,52-62,78-85` (table/chunk_table into DDL), `ingester.py:134,168-170,256,284-286,314-316,348-350` (table/chunk_table/distance_metric into queries). `chunk_table` (set on `DocumentPipeline.__init__`) and `namespace`/`database` (on `DatabaseConfig`) also need validation.

   ```python
   # After — add validation in config.py
   import re

   _IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
   _VALID_DISTANCE_METRICS = frozenset({"COSINE", "EUCLIDEAN", "MANHATTAN", "MINKOWSKI", "CHEBYSHEV"})
   _VALID_ANALYZER_LANGUAGES = frozenset({
       "arabic", "danish", "dutch", "english", "finnish", "french", "german",
       "hungarian", "italian", "norwegian", "portuguese", "romanian", "russian",
       "spanish", "swedish", "tamil", "turkish",
   })

   def _validate_identifier(value: str, name: str) -> None:
       if not _IDENTIFIER_RE.match(value):
           raise ValueError(f"Invalid {name}: {value!r}. Must be alphanumeric/underscore.")

   @dataclass
   class DatabaseConfig:
       table: str = "documents"
       # ...
       def __post_init__(self) -> None:
           for field in ("table", "namespace", "database"):
               _validate_identifier(getattr(self, field), field)
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
           if self.analyzer_language not in _VALID_ANALYZER_LANGUAGES:
               msg = f"Invalid analyzer language: {self.analyzer_language!r}"
               raise ValueError(msg)
   ```

   Also validate `chunk_table` in `DocumentPipeline.__init__`:

   ```python
   _validate_identifier(chunk_table, "chunk_table")
   ```

---

## Warnings (7)

3. **[Type hole]** `ingester.py:81` — `_client: Any` defeats all type checking on SurrealDB API calls (confidence: 95)

   Every `.query()`, `.connect()`, `.signin()`, `.use()`, `.close()` call is unchecked. Wrong method names or argument types would not be caught.

   ```python
   # Before
   self._client: Any = None

   # After
   from surrealdb.connections.async_template import AsyncTemplate
   self._client: AsyncTemplate | None = None
   ```

4. **[No None guard]** `ingester.py:124,159,172,236,273,301,320` — All methods access `self._client` without checking for `None`; crashes with `AttributeError` if called before `connect()` (confidence: 95)

   ```python
   # After — add a guard property
   @property
   def _db(self) -> Any:  # or AsyncTemplate
       if self._client is None:
           msg = "Not connected. Call connect() or use 'async with' first."
           raise RuntimeError(msg)
       return self._client
   ```

5. **[Connection leak]** `ingester.py:83-94` — If `signin()` or `use()` raises after `connect()`, the client is leaked (confidence: 85)

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

6. **[Silent auth skip]** `ingester.py:87` — Auth silently skipped when only one of username/password is provided (confidence: 90)

   ```python
   # After — validate in DatabaseConfig.__post_init__ or connect()
   if bool(self._db_config.username) != bool(self._db_config.password):
       msg = "Both username and password must be provided, or neither"
       raise ValueError(msg)
   ```

7. **[Zero batch size]** `config.py:18` — `insert_batch_size=0` causes `ValueError: range() arg 3 must not be zero`; negative values silently drop all records (confidence: 95)

   Covered in the `__post_init__` fix in Critical Issue #2.

8. **[`__aexit__` exception shadowing]** `ingester.py:115-116` — If `close()` raises, it shadows the original exception propagating from the `async with` block (confidence: 80)

    ```python
    # After
    async def __aexit__(self, *_args: object) -> None:
        try:
            await self.close()
        except Exception:
            if _args[0] is None:
                raise
    ```

9. **[Symlink traversal]** `ingester.py:74` — `_collect_files` uses `Path.glob()` which follows symlinks, potentially traversing outside the intended directory (confidence: 75)

    ```python
    # After — add symlink guard
    root = Path(directory).resolve()
    return sorted(
        p for p in root.glob(glob)
        if p.is_file() and p.resolve().is_relative_to(root)
    )
    ```

10. **[Shared analyzer semantics]** `schema.py:9` — `doc_analyzer` is a global SurrealDB object created with `IF NOT EXISTS` (confidence: 80)

    If two connectors in the same namespace/database use different `analyzer_language` values, the second `DEFINE ANALYZER IF NOT EXISTS` silently no-ops, leaving the first language in effect. Either use `OVERWRITE` or include the language in the analyzer name (e.g., `doc_analyzer_english`).

---

## Suggestions (7)

11. **[DRY]** `ingester.py:238-276` — `DocumentPipeline._ingest_result` bypasses `_insert_documents` with inline query calls, duplicating the insert pattern (confidence: 85)

12. **[Literal types]** `config.py:24,21` — `distance_metric` and `analyzer_language` could use `Literal` types for compile-time validation (confidence: 80)

13. **[method-assign]** `test_pipeline.py:226,244` — Monkey-patching `_embed_query` with direct assignment; use `patch.object` instead (confidence: 95)

    ```python
    # Before
    pipeline._embed_query = AsyncMock(return_value=[0.1] * 768)

    # After
    with patch.object(pipeline, "_embed_query", new_callable=AsyncMock, return_value=[0.1] * 768):
        result = await pipeline.search("test query", limit=5)
    ```

14. **[union-attr]** `test_pipeline.py:44,49` — Access `.chunking` on `_config` without `None` guard; add `assert pipeline._config is not None` (confidence: 95)

15. **[Misleading field name]** `ingester.py:270` — `token_count` uses `len(chunk.content.split())` which counts whitespace-delimited words, not tokens (confidence: 90)

    Either rename the field to `word_count` (in schema and ingester) or use a proper tokenizer. The schema field name `token_count` and the BPE/sentencepiece meaning of "token" don't match.

16. **[Credentials in repr]** `config.py` — `DatabaseConfig.__repr__` exposes `password` and `db_url` (which may contain embedded credentials) in plain text (confidence: 85)

    ```python
    # After
    def __repr__(self) -> str:
        pw = "***" if self.password else None
        return (f"DatabaseConfig(db_url={self.db_url!r}, namespace={self.namespace!r}, "
                f"database={self.database!r}, username={self.username!r}, password={pw!r}, "
                f"table={self.table!r}, insert_batch_size={self.insert_batch_size!r})")
    ```

17. **[No limit guard]** `ingester.py:165,298,329` — `limit` parameter is passed to SurQL as `$limit` (parameterized, safe), but `limit <= 0` produces unexpected empty results with no error (confidence: 75)

    A simple `if limit < 1: raise ValueError(...)` at the top of each search method would prevent misuse.

---

## Version Compatibility

No deprecated or removed API usage detected for Python 3.11-3.14. Minimum version is 3.11 (`requires-python = ">=3.11"`). No files use `from __future__ import annotations`.

---

## Scores

| Dimension | Score | Notes |
|---|---|---|
| Code Quality | 7/10 | Good architecture; config mutation and missing input validation remain |
| Cleanliness | 9/10 | Clean source modules with good docstrings; lint and dead code issues resolved |
| Type Safety | 7/10 | Source passes strict mypy; `_client: Any` is the main unchecked surface |
| **Overall** | **7.5/10** | Well-structured; fix the 2 remaining critical issues before release |

---

## Tool Recommendations

Both ruff and mypy are installed and configured well. Consider:
- Adding `ANN` enforcement selectively to test fixtures in `conftest.py` for consistency
