# kreuzberg-surrealdb: Integration Pitch

## Proposal Summary

Build a Kreuzberg-to-SurrealDB connector that delivers the **first zero-external-dependency RAG pipeline** in the Python ecosystem. No OpenAI API key for embeddings. No Pinecone account for vector storage. Just `pip install` and go.

**Primary deliverable**: `kreuzberg-surrealdb` adapter package on PyPI, listed on [surrealdb.com/docs/integrations](https://surrealdb.com/docs/integrations) alongside LangChain, LlamaIndex, etc.

**Tactical first step**: Examples PR to [`surrealdb/surrealdb.py/examples/`](https://github.com/surrealdb/surrealdb.py/tree/main/examples) — builds the relationship with SurrealDB maintainers and fills a gap (their Python SDK examples have zero AI/RAG content today).

---

## The Core Pitch

### Problem: RAG pipelines have too many moving parts

A typical RAG setup today requires:

| Component | Common choice | What it costs |
|---|---|---|
| Document parsing | Unstructured, LlamaParse | Fragile / paid API |
| Embeddings | OpenAI, Cohere | $0.10–$0.50 per 1M tokens, API key, network latency |
| Vector store | Pinecone, Weaviate, Qdrant | Separate service, separate billing |
| Metadata store | PostgreSQL | Another service to manage |
| Graph relations | Neo4j | Yet another service |
| Cache | Redis | And another |

That's 4–6 services, at least one paid API key, and a `docker-compose.yml` longer than the application code.

### Solution: kreuzberg + SurrealDB collapses the entire stack

```
Document → kreuzberg (extract + chunk + embed locally) → SurrealDB (store + index + search)
```

**Two components. No API keys. No billing. Runs on a laptop.**

| Capability | Traditional RAG | kreuzberg + SurrealDB |
|---|---|---|
| Document parsing | Paid API or fragile libs | 75+ formats, Rust core, 10-50x faster |
| Embeddings | OpenAI/Cohere API ($$$) | Local ONNX/FastEmbed, zero API calls |
| Vector store | Pinecone/Weaviate (separate service) | SurrealDB built-in HNSW |
| Full-text search | Elasticsearch (separate service) | SurrealDB built-in BM25 |
| Hybrid search | Custom fusion logic | SurrealDB `search::rrf()` |
| Metadata store | Postgres (another service) | Same SurrealDB instance |
| Graph relations | Neo4j (yet another service) | Same SurrealDB instance, native edges |
| Setup time | Hours | Minutes |
| Monthly cost (embeddings + vector DB) | $50–500+ | $0 |

### Why this pairing is unique

- **Kreuzberg's pitch**: "Local embeddings without API calls" — ONNX runtime, FastEmbed models (384–1024d), runs on CPU, no GPU required
- **SurrealDB's pitch**: "You don't need a separate vector DB" — HNSW indexes, hybrid search, graph + vector + document in one engine

No other connector in the ecosystem combines both claims. LangChain's SurrealDB integration still requires an external embedding provider. This connector doesn't.

---

## Path Analysis: Examples PR vs. Adapter Package

### Why the adapter package is the primary deliverable

Research into both SurrealDB's example repos and integrations page reveals a clear answer:

**Current state of SurrealDB examples:**

| Repo | Content | AI/RAG coverage |
|---|---|---|
| [`surrealdb/surrealdb.py/examples/`](https://github.com/surrealdb/surrealdb.py/tree/main/examples) | 15 examples — all web frameworks (Flask, FastAPI, Django, etc.) + FastMCP | **Zero** vector/RAG/AI examples |
| [`surrealdb/examples`](https://github.com/surrealdb/examples) | 22 examples, broader scope | 5 AI examples: `simple-rag-chatbot`, `surrealdb-rag`, `surrealdb-openai`, `vector-search`, `hybrid-search` |

**What the existing RAG examples look like — and why they're inadequate:**

- **`simple-rag-chatbot`** — Streamlit + Ollama + SurrealDB. Loads a single `.txt` file. No real document extraction, no format handling beyond plain text.
- **`surrealdb-rag`** — The most complete example. FastAPI + spaCy + OpenAI/GloVe/FastText. Requires spaCy, transformers, pandas, FuzzyWuzzy, and API keys for OpenAI/Gemini. Heavy, complex, and not reusable as a library.
- **`vector-search`** — SurrealQL tutorial using Ollama's `nomic-embed-text`. Pre-baked dataset. Not a real ingestion pipeline.
- **`surrealdb-openai`** — 25K Wikipedia articles with OpenAI embeddings. Requires `OPENAI_API_KEY`.

**The pattern**: Every existing example either uses a toy `.txt` file or requires an external embedding API. None handle real-world document formats (PDF, DOCX, XLSX, scanned images). None do local embeddings without a separate service.

**What the integrations page looks like:**

[surrealdb.com/docs/integrations/frameworks](https://surrealdb.com/docs/integrations/frameworks) lists 12 frameworks — LangChain, LlamaIndex, CrewAI, Agno, Pydantic AI, etc. Each gets a dedicated docs page. The pattern: **installable PyPI package + docs page + code examples**. This is where RAG builders actually evaluate their stack.

**The reference — `langchain-surrealdb`:**

- PyPI package with `SurrealDBVectorStore` class
- Methods: `add_documents()`, `similarity_search()`, `similarity_search_with_score()`, `as_retriever()`
- Gets a full docs page on surrealdb.com
- **But still requires a separate embedding provider** (Ollama, OpenAI, etc.)

### Head-to-head comparison for RAG pipeline builders

| Dimension | Examples PR | Adapter package |
|---|---|---|
| **Discoverability** | Hidden in a GitHub repo, found by browsing | PyPI search for "surrealdb rag", integrations page, `pip install` |
| **Reusability** | Copy-paste, re-implement schema/search/chunking every time | `pip install kreuzberg-surrealdb`, call 3 methods |
| **Maintainability** | Examples silently break when APIs change, no CI | Versioned, CI catches breakages, semver guarantees |
| **Integrations page eligibility** | Not listed — examples aren't packages | Listed alongside LangChain, LlamaIndex |
| **Dependency graph visibility** | None | Shows in `pip list`, `uv tree`, GitHub dependency graphs |
| **Time to ship** | ~3 days | ~2–3 weeks |
| **Composability** | Standalone scripts | Works with LangChain/LlamaIndex on top if users want |
| **Ecosystem signal** | "kreuzberg works with SurrealDB" | "kreuzberg is an official SurrealDB integration" |

### Verdict

**The adapter package wins for RAG builders, and it's not close.**

Examples show what's *possible*. A package makes it *easy*. RAG builders install packages, they don't copy examples.

### But do the examples PR first — as a tactical wedge

| Phase | Action | Purpose |
|---|---|---|
| **Week 1** | PR to `surrealdb/surrealdb.py/examples/` | Fill the zero-AI-examples gap, open dialogue with SurrealDB maintainers |
| **Week 2–3** | Ship `kreuzberg-surrealdb` v0.1.0 to PyPI | The real product |
| **Week 3–4** | PR to SurrealDB docs for integrations page listing | Reference the package, use examples as supporting material |

The examples PR is a conversation starter with the SurrealDB team. The package is what you ship. The integrations page is where it lives permanently.

---

## Phase 1: Examples PR (Tactical — Week 1)

Contribute to [`surrealdb/surrealdb.py/examples/`](https://github.com/surrealdb/surrealdb.py/tree/main/examples) — which currently has **zero AI/RAG examples**.

### Structure: `examples/kreuzberg_rag/`

```
examples/kreuzberg_rag/
    README.md
    requirements.txt          # kreuzberg, surrealdb
    basic_ingest.py           # Extract PDF → store in SurrealDB
    vector_search.py          # Embed query locally → HNSW search
    hybrid_search.py          # Vector + BM25 fusion
    batch_pipeline.py         # Directory ingestion at scale
```

**`basic_ingest.py`** — The 30-line demo:

```python
import kreuzberg
from surrealdb import Surreal

async def main():
    # Extract + chunk + embed locally (no API calls)
    config = kreuzberg.ExtractionConfig(
        output_format="markdown",
        chunking=kreuzberg.ChunkingConfig(
            strategy="semantic",
            chunk_size=512,
            chunk_overlap=64,
        ),
    )
    result = await kreuzberg.extract_file("document.pdf", config=config)

    # Store in SurrealDB
    db = Surreal("ws://localhost:8000/rpc")
    await db.signin({"username": "root", "password": "root"})
    await db.use("rag", "documents")

    # Schema with vector index
    await db.query("""
        DEFINE TABLE chunks SCHEMAFULL;
        DEFINE FIELD content ON chunks TYPE string;
        DEFINE FIELD embedding ON chunks TYPE array<float>;
        DEFINE FIELD source ON chunks TYPE string;
        DEFINE INDEX idx_vec ON chunks FIELDS embedding HNSW DIMENSION 768 DIST COSINE;
        DEFINE INDEX idx_ft ON chunks FIELDS content SEARCH ANALYZER simple BM25;
    """)

    # Insert chunks with locally-generated embeddings
    for chunk in result.chunks:
        await db.create("chunks", {
            "content": chunk.content,
            "embedding": chunk.embedding,
            "source": "document.pdf",
        })
```

**Value to SurrealDB**: Fills a glaring gap — their Python SDK examples have zero AI content. Shows SurrealDB working with a real document intelligence library, not toy data.

**Value to kreuzberg**: Visibility in SurrealDB's official repo. Opens the door for the adapter package conversation.

---

## Phase 2: Adapter Package (Primary Deliverable — Week 2–3)

`kreuzberg-surrealdb` on PyPI, listed on [surrealdb.com/docs/integrations](https://surrealdb.com/docs/integrations) as a peer to LangChain, LlamaIndex, etc.

### Design principles

1. **Embeddings on by default** — The zero-config path produces vectors. Kreuzberg's `"balanced"` preset (768d, ONNX, local) just works out of the box.
2. **Hybrid search by default** — `search()` does vector KNN + BM25 full-text + `search::rrf()` fusion. One method, smart behavior.
3. **Schema auto-setup** — `setup_schema()` creates tables, vector indexes, full-text indexes. No manual SQL.
4. **`pip install` is the entire setup** — No `.env` with API keys. No external services beyond SurrealDB itself.

### User experience target

```python
from kreuzberg_surrealdb import DocumentIngester

# Connect — that's all the config needed
ingester = DocumentIngester(url="ws://localhost:8000/rpc")
await ingester.setup_schema()

# Ingest a directory of documents
# (extracts, chunks, embeds locally, stores with HNSW index)
await ingester.ingest_directory("./docs/", glob="**/*.pdf")

# Search — embedding happens locally, hybrid search automatic
results = await ingester.search("What is the refund policy?", limit=5)

# Feed to any LLM
context = "\n---\n".join(r["content"] for r in results)
```

No `OPENAI_API_KEY`. No `PINECONE_API_KEY`. No `docker-compose.yml` with 5 services.

### What the adapter must ship with (v0.1.0)

| Feature | Why non-negotiable |
|---|---|
| Local embeddings via kreuzberg's ONNX/FastEmbed | The entire pitch falls apart without this |
| HNSW vector index on chunks | SurrealDB's differentiator — must be wired |
| BM25 full-text index on content | Enables hybrid search |
| `search()` with hybrid fusion (`search::rrf`) | One method does vector + keyword + fusion |
| `vector_search()` for pure semantic queries | Escape hatch for embedding-only retrieval |
| Kreuzberg metadata stored (quality, languages, keywords) | Proves kreuzberg's extraction depth |

### Schema (v0.1.0)

```sql
DEFINE TABLE documents SCHEMAFULL;
DEFINE FIELD source ON documents TYPE string;
DEFINE FIELD content ON documents TYPE string;
DEFINE FIELD mime_type ON documents TYPE string;
DEFINE FIELD title ON documents TYPE option<string>;
DEFINE FIELD authors ON documents TYPE option<array<string>>;
DEFINE FIELD created_at ON documents TYPE option<datetime>;
DEFINE FIELD ingested_at ON documents TYPE datetime DEFAULT time::now();
DEFINE FIELD metadata ON documents TYPE object FLEXIBLE;
DEFINE FIELD quality_score ON documents TYPE option<float>;
DEFINE FIELD detected_languages ON documents TYPE option<array<string>>;
DEFINE FIELD keywords ON documents TYPE option<array<object>>;

DEFINE TABLE chunks SCHEMAFULL;
DEFINE FIELD document ON chunks TYPE record<documents>;
DEFINE FIELD content ON chunks TYPE string;
DEFINE FIELD embedding ON chunks TYPE option<array<float>>;
DEFINE FIELD chunk_index ON chunks TYPE int;
DEFINE FIELD page_number ON chunks TYPE option<int>;
DEFINE FIELD char_start ON chunks TYPE option<int>;
DEFINE FIELD char_end ON chunks TYPE option<int>;

-- Vector index (dimension configurable, 768 default for balanced preset)
DEFINE INDEX idx_chunk_embedding ON chunks
    FIELDS embedding HNSW DIMENSION 768 DIST COSINE;

-- Full-text index for hybrid search
DEFINE ANALYZER chunk_analyzer TOKENIZERS class FILTERS lowercase, snowball(english);
DEFINE INDEX idx_chunk_content ON chunks
    FIELDS content SEARCH ANALYZER chunk_analyzer BM25;

-- Source lookup
DEFINE INDEX idx_doc_source ON documents FIELDS source UNIQUE;
```

### Differences from the original Linear task spec

| Original spec | This pitch | Why |
|---|---|---|
| `chunk: bool = False` | `embed: bool = True` | Embeddings should be the default, not an opt-in afterthought |
| No embedding field in schema | `embedding` field + HNSW index | Without this, it's not a RAG connector |
| `search()` full-text only | `search()` hybrid by default | SurrealDB's `search::rrf()` is the differentiator |
| No vector search method | `vector_search()` + `search()` | Must showcase SurrealDB's HNSW capability |
| No kreuzberg embeddings used | Kreuzberg's ONNX/FastEmbed wired in | The "zero API key" pitch requires local embeddings |
| No keyword extraction stored | `keywords` field from YAKE/RAKE | Proves kreuzberg's extraction depth beyond plain text |
| No language detection stored | `detected_languages` field | Low effort, high value metadata |
| No quality score used | `quality_score` field | Signals document reliability for downstream ranking |

---

## Strategic Rationale

### For the SurrealDB partnership

SurrealDB is actively seeking AI/ML integrations (raised $23M Series A extension in Feb 2026 specifically for this). Their integrations page currently lists:

- **Frameworks**: LangChain, LlamaIndex, Spring AI, Haystack
- **Embedding providers**: OpenAI, Ollama, Mistral, HuggingFace, AWS Bedrock, Google Gemini

kreuzberg-surrealdb would be the **first integration that eliminates the need for a separate embedding provider entirely**. That's a story SurrealDB's marketing team can use: "zero-dependency RAG with kreuzberg."

### For kreuzberg's ecosystem

kreuzberg already has:
- `langchain-kreuzberg` (LangChain integration)
- `kreuzberg-haystack` (Haystack integration)

Adding SurrealDB positions kreuzberg across the three major AI database paradigms:
- **Framework orchestrators**: LangChain, Haystack
- **AI-native databases**: SurrealDB
- **Cloud platforms**: kreuzberg-cloud

### Visibility multiplier

Being listed on `surrealdb.com/docs/integrations` puts kreuzberg in front of every SurrealDB user evaluating document processing. The examples in `surrealdb.py` put kreuzberg in front of every Python SDK user. Both audiences are actively building RAG pipelines.

---

## Execution Timeline

| Week | Phase | Deliverable | Outcome |
|---|---|---|---|
| 1 | Examples PR | `kreuzberg_rag/` in `surrealdb/surrealdb.py/examples/` | Relationship with SurrealDB team, fill their AI examples gap |
| 2–3 | Adapter v0.1.0 | `kreuzberg-surrealdb` on PyPI | The real product — installable zero-dependency RAG pipeline |
| 3–4 | Integrations page | PR to SurrealDB docs | Listed alongside LangChain, LlamaIndex on surrealdb.com |
| Future | v0.2.0+ | Graph edges, concept graphs, GraphRAG | Tier 2 architecture — `RELATE` edges, keyword graph, table entities |

---

## One-liner

> `kreuzberg-surrealdb` is the only RAG connector where `pip install` is the entire setup — local document extraction, local embeddings, and vector + graph + full-text search in a single database, with zero external API dependencies.
