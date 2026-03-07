# Ruff Ignore Decisions

Reference: `pyproject.toml` `[tool.ruff.lint.per-file-ignores]`

## Tests (`tests/**`)

### Kept after review (controversial)

| Code | Rule | Why it stays |
|------|------|-------------|
| `S108` | Insecure temp file/directory | Tests use hardcoded `/tmp/test.pdf` etc. as dummy source strings passed to `ingest_file()`. These aren't actual temp file operations — just string arguments. 18 occurrences across test_connector, test_pipeline. |
| `S608` | SQL injection via string query | Integration tests run `f"SELECT * FROM {table}"` against SurrealDB where `table` comes from `DatabaseConfig`, not user input. 7 occurrences in test_integration. |
| `S105` | Hardcoded password in variable | Test DB credentials like `password = "root"` for SurrealDB test fixtures. |
| `S106` | Hardcoded password in argument | Same — `password="root"` in `DatabaseConfig(...)` calls. |

### Standard (uncontroversial)

| Code | Rule | Reason |
|------|------|--------|
| `S101` | Use of `assert` | Tests use assert |
| `D` | All docstring rules | Tests don't need docstrings |
| `ANN` | All annotation rules | Tests don't need type annotations |
| `SLF001` | Private member access | Tests inspect `_client`, `_config` etc. |
| `PLR2004` | Magic value comparison | Tests compare against literal values |
| `PLC0415` | Import not at top | Tests may import inside functions |
| `PERF401` | Use list comprehension | Readability over perf in tests |
| `PERF402` | Use list/dict copy | Same |
| `TC001` | Move import to TYPE_CHECKING | Tests need runtime imports |
| `TC003` | Move stdlib import to TYPE_CHECKING | Same |

## Source files

| File | Code | Why |
|------|------|-----|
| `ingester.py` | `S608` | Builds SurrealQL with f-strings using config-controlled table names |
| `ingester.py` | `PLC0415` | Lazy import of `fastembed` (heavy dep, loaded on first use) |
| `schema.py` | `S608` | DDL generation with f-string table/field names |

## Compared against

`langchain-kreuzberg` sister repo uses the same global ignores and a subset of the test ignores (no S105/S106/S108/S608/TC001 — it doesn't connect to databases or build queries in tests).
