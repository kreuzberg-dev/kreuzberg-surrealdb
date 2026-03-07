# Known Bugs

## BUG-1: KNN operator rejects parameterized limit

**Severity:** High — breaks `vector_search()` and hybrid `search()` at runtime

**Location:** `src/kreuzberg_surrealdb/ingester.py` lines 293, 325

**Description:**
SurrealDB's KNN operator `<|K,metric|>` requires `K` to be a literal unsigned integer. The current code passes `$limit` as a bound parameter:

```python
# vector_search (line 325)
f"WHERE {qt}embedding <|$limit,{dist}|> $embedding ORDER BY distance"

# hybrid search (line 293)
f"LET $vs = (SELECT id FROM {ct} WHERE {qt}embedding <|{limit},{dist}|> $embedding);"
```

The `vector_search` method uses `$limit` (parameter binding) which SurrealDB's parser rejects:
```
Parse error: Unexpected token `a parameter`, expected an unsigned integer
 --> [1:77]
  |
1 | ...bedding <|$limit,COSINE|> $embedding ORDER BY distance
  |              ^^^^^^
```

Note: `search()` already interpolates `{limit}` as a literal in the hybrid query — only `vector_search` has this bug.

**Fix:** Interpolate `limit` as a literal integer in the KNN operator (same as hybrid search already does):
```python
f"WHERE {qt}embedding <|{limit},{dist}|> $embedding ORDER BY distance"
```

---

## BUG-2: `search::rrf()` not available in SurrealDB embedded mode

**Severity:** Medium — hybrid search only works against a full SurrealDB server

**Location:** `src/kreuzberg_surrealdb/ingester.py` line 296

**Description:**
The embedded SurrealDB engine (used via `mem://` and the Python SDK's Rust extension) does not support the `search::rrf()` function:

```
Parse error: Invalid function/constant path
 --> [1:203]
  |
1 | ...CT * FROM search::rrf([$vs, $ft], $limit, $k);
  |              ^^^^^^^^^^^
```

This means `DocumentPipeline.search()` with `embed=True` fails when connected via `mem://`. It works fine against a networked SurrealDB server (`ws://`, `wss://`).

**Impact:** Integration tests for hybrid search cannot run in embedded mode. Users who test locally with `mem://` will hit this error.

**Options:**
1. Document that hybrid search requires a real SurrealDB server
2. Add a fallback to manual RRF computation when `search::rrf` is unavailable
3. Accept as a known limitation of the embedded driver
