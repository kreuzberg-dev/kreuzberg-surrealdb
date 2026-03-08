# SurrealDB Python SDK v2/v3 Compatibility Issue

**Repo:** [surrealdb/surrealdb.py](https://github.com/surrealdb/surrealdb.py)
**Status:** To file

---

## Title

Python SDK 1.0.8 embedded engine uses SurrealDB v2 syntax, incompatible with v3

## Body

The Python SDK (1.0.8) bundles an embedded SurrealDB engine that uses v2.x SurQL syntax. However, SurrealDB server v3.x (`latest` Docker tag) has breaking syntax changes:

- `SEARCH ANALYZER` → `FULLTEXT ANALYZER`
- `FLEXIBLE TYPE object` → `TYPE object FLEXIBLE`

This means code written against the embedded engine (`mem://`) breaks when connecting to a v3 server, and vice versa.

### Steps to reproduce

```python
from surrealdb import AsyncSurreal

# Works with mem:// (v2 embedded engine)
async with AsyncSurreal("mem://") as db:
    await db.query("DEFINE FIELD metadata ON TABLE docs FLEXIBLE TYPE object;")  # OK

# Fails against surrealdb:latest (v3 server)
async with AsyncSurreal("ws://localhost:8000") as db:
    await db.query("DEFINE FIELD metadata ON TABLE docs FLEXIBLE TYPE object;")
    # Error: FLEXIBLE must be specified after TYPE
```

### Expected

The SDK's embedded engine and the latest server should use the same SurQL syntax, or the SDK should document which server version it's compatible with.

### Environment

- `surrealdb` Python SDK: 1.0.8
- SurrealDB server: v3.x (latest) vs v2.6.3 (embedded)
- Python: 3.11+

---

## Impact on kreuzberg-surrealdb

We pin the Docker image to `surrealdb/surrealdb:v2` in CI to match the SDK's embedded engine syntax. Once the SDK updates to v3, we should:

1. Update `pyproject.toml` dependency to the new SDK version
2. Migrate schema DDL to v3 SurQL syntax (`FULLTEXT ANALYZER`, `TYPE ... FLEXIBLE`)
3. Unpin Docker image from `v2` to `latest`
