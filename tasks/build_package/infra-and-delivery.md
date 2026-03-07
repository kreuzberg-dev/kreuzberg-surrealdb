# Infrastructure & Delivery Fixes

Items that need to happen beyond design decisions. Does not cover code implementation (see `todo.md`).

---

## CI Workflow Fixes

### SurrealDB service container for integration tests

`ci.yaml` runs `uv run pytest -m integration -v` but never starts SurrealDB. Tests will fail or be skipped silently.

Add service container to the test job:

```yaml
services:
  surrealdb:
    image: surrealdb/surrealdb:latest
    ports:
      - 8000:8000
    options: >-
      --health-cmd "curl -sf http://localhost:8000/health || exit 1"
      --health-interval 5s
      --health-timeout 3s
      --health-retries 10
env:
  SURREALDB_URL: ws://localhost:8000
```

### Python version matrix

CI lints on 3.13, tests on 3.10 only. Package declares support for 3.10-3.13.

Add matrix to the test job:

```yaml
strategy:
  matrix:
    python-version: ["3.10", "3.11", "3.12", "3.13"]
```

---

## CHANGELOG.md

References `DocumentIngester` (old single-class design). Must be rewritten after implementation to reflect `DocumentConnector` + `DocumentPipeline`, all methods from D7/D10/D20, and the full feature set from D21-D22.

Update **after** implementation is complete so it reflects what actually shipped.

---

## README.md

Current: 5-line stub. Needs:

- Badges (PyPI version, Python versions, CI status, license, coverage)
- Installation (`pip install kreuzberg-surrealdb`)
- Quickstart (3-method UX: `setup_schema` -> `ingest_directory` -> `search`)
- Schema docs (documents table, chunks table, indexes)
- RAG pipeline example (`DocumentPipeline` with hybrid search)
- DocumentConnector example (simple BM25 use case)
- SurrealDB setup instructions (Docker one-liner, SurrealDB Cloud)
- API reference summary
- Links to kreuzberg and SurrealDB docs

Write **after** implementation is complete.

---

## Examples

Current stubs: `basic_ingest.py`, `rag_pipeline.py` (docstring-only).

Target set per `todo.md` + two-class architecture:

| File | Class | Demonstrates |
|---|---|---|
| `basic_ingest.py` | `DocumentConnector` | File ingestion + BM25 search |
| `batch_pipeline.py` | `DocumentConnector` | `ingest_directory()` with glob |
| `vector_search.py` | `DocumentPipeline` | `vector_search()` pure semantic |
| `hybrid_search.py` | `DocumentPipeline` | `search()` hybrid RRF |
| `rag_pipeline.py` | `DocumentPipeline` | End-to-end RAG with LLM call |

Plus `examples/README.md` with prerequisites (running SurrealDB, sample documents).

---

## Testing Strategy

### Unit tests (mock SurrealDB SDK)

- `test_schema.py` -- schema SQL generation per class/mode, idempotency
- `test_connector.py` -- `DocumentConnector` ingestion + BM25 search
- `test_pipeline.py` -- `DocumentPipeline` chunking, embedding, hybrid/vector search
- `test_config.py` -- `DatabaseConfig`, `IndexConfig` validation and defaults
- `conftest.py` -- shared fixtures: mock SurrealDB client, sample `ExtractionResult` objects

### Integration tests (real SurrealDB via service container)

- Marked with `@pytest.mark.integration`
- Full round-trip: `setup_schema` -> ingest -> search -> verify results
- Both `DocumentConnector` and `DocumentPipeline` modes
- Deduplication (ingest same file twice)
- `embed=True` vs `embed=False`

### Coverage

80%+ enforced via `pyproject.toml` (`fail_under = 80`), reported as XML in CI.

---

## `__init__.py` Public API

Current: exports `__version__` only. After implementation, must export:

```python
__all__ = [
    "DatabaseConfig",
    "DocumentConnector",
    "DocumentPipeline",
    "IndexConfig",
    "__version__",
]
```

---

## Delivery Sequence

1. Fix CI (service container + version matrix)
2. Implement code (per `todo.md` Phase 2)
3. Update `__init__.py` exports
4. Write tests (unit + integration), hit 80%+
5. Write examples (5 scripts + README)
6. Write README.md
7. Update CHANGELOG.md
8. Final lint/type-check pass
9. Tag `v0.1.0`, verify publish workflow
