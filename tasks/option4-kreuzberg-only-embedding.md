# Option 4: Kreuzberg-Only Embedding — Trade-offs

## Decision
Use kreuzberg for both content and query embedding, eliminating the fastembed Python dependency.

## Cons / Risks

### 1. Silent embedding failure
kreuzberg's `extract_bytes` returns `embedding=None` instead of raising when ONNX runtime fails. If `libonnxruntime.so` is missing or misconfigured, search silently returns garbage.
**Mitigation:** We raise `RuntimeError` in `_embed_query` when embedding is None.

### 2. Query embedding overhead
Each query embedding goes through kreuzberg's full extraction pipeline (`extract_bytes` → parse → chunk → embed) even though the input is just a short string. Heavier than a direct `TextEmbedding.embed()` call.
**Measured:** Extraction overhead is ~0.1ms per call (negligible). The ONNX inference dominates regardless of which runtime is used.

### 3. System dependency: libonnxruntime.so
kreuzberg's Rust `ort` crate loads `libonnxruntime.so` dynamically. Users must install it system-wide:
- macOS: `brew install onnxruntime`
- Ubuntu/Debian: `apt install libonnxruntime libonnxruntime-dev`
- Fedora: `dnf install onnxruntime onnxruntime-devel`
- Or set `ORT_DYLIB_PATH` env var

fastembed Python bundles its own ONNX runtime, so this was previously transparent.

### 4. kreuzberg-internal model names
Users who want models beyond the 4 presets must use kreuzberg's PascalCase names (`BGEBaseENV15`, `NomicEmbedTextV15`) instead of HuggingFace names (`BAAI/bge-base-en-v1.5`). Less discoverable.
**Mitigation:** Document the available models and how to use `EmbeddingModelType.fastembed()`.

### 5. Model availability tied to kreuzberg's Rust fastembed version
kreuzberg v4.4.3 bundles Rust fastembed 5.12.0 with ~40 models. New fastembed models require a kreuzberg release. Previously, users could upgrade Python fastembed independently.

### 6. No standalone embed API
kreuzberg has no `embed(text) -> vector` function. We must use `extract_bytes(query.encode(), "text/plain", config=...)` which is semantically awkward — treating a search query as a "document to extract."

### 7. Breaking API change
`embedding_preset=` becomes `embedding_model=`. Pre-1.0 so acceptable, but existing users must update.

## Pros (why we're doing it anyway)

1. **Guaranteed model match** — same config, same runtime, same ONNX weights for content and query
2. **Eliminates `_PRESET_TO_FASTEMBED` map** — no fragile name translation
3. **Drops fastembed Python dependency** — one fewer dependency
4. **Supports all three model types** — preset, fastembed (40+ models), custom ONNX
5. **Eliminates dual-runtime mismatch** — no risk of different quantization/weights between two ONNX runtimes
6. **Fixes the multilingual bug** — old map pointed to `intfloat/multilingual-e5-base` which fastembed doesn't support

## Execution Plan

See the comprehensive plan in conversation. Summary:

### Files changed
- `src/kreuzberg_surrealdb/ingester.py` — core refactor (remove map, rewrite __init__, _build_extraction_config, _embed_query)
- `tests/test_pipeline.py` — update param names, rewrite _embed_query tests, add EmbeddingModelType tests
- `tests/test_integration.py` — rename `embedding_preset=` → `embedding_model=` (2 occurrences)
- `pyproject.toml` — remove fastembed dependency, remove PLC0415 ruff ignore
- `README.md` — update API docs, fix preset names, add custom model docs
- `examples/README.md` — no changes needed

### Files unchanged
- `config.py`, `schema.py`, `__init__.py`, `test_connector.py`, `conftest.py`

### Implementation order
1. pyproject.toml + uv sync
2. ingester.py (core changes)
3. test_pipeline.py
4. test_integration.py
5. README.md
6. Full test suite + lint + mypy
