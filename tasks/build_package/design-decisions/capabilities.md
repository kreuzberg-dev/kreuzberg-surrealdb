# Capabilities & Dependencies (D11, D21, D22)

### D11: Dependencies

| Dependency | Version | Notes |
|---|---|---|
| kreuzberg | >=4.4.3 | Core extraction |
| surrealdb | >=1.0.8 | Database SDK |
| fastembed | >=0.7.4 | Embedding generation. NOT a transitive dep of kreuzberg. |

All core dependencies, always installed. One `pip install` gets everything.

### D21: Feature matrix

| Feature | DocumentConnector | Pipeline (embed=True) | Pipeline (embed=False) |
|---|---|---|---|
| Extract 75+ formats | Yes | Yes | Yes |
| Document text + metadata | Yes | Yes | Yes |
| Quality score, languages, keywords | Yes | Yes | Yes |
| Deduplication | Yes | Yes | Yes |
| BM25 search | Yes (documents) | Yes (chunks) | Yes (chunks) |
| BM25/IndexConfig tuning | Yes | Yes | Yes |
| ExtractionConfig customization | Yes | Yes | Yes |
| Chunking with positional metadata | No | Yes | Yes |
| Custom chunk_table name | No | Yes | Yes |
| Local embedding (ONNX/FastEmbed) | No | Yes | No |
| HNSW vector index | No | Yes | No |
| Hybrid search (vector+BM25+RRF) | No | Yes | No |
| Vector search | No | Yes | No |
| Quality threshold filtering | No | Yes | No |
| Page range citation | No | Yes | Yes |

### D22: Mode interaction

| embed | Class | Tables | Search | Indexes |
|---|---|---|---|---|
| (N/A) | DocumentConnector | documents | BM25 on documents | idx_doc_source, idx_doc_hash, idx_doc_content |
| True | DocumentPipeline | documents + chunks | hybrid, vector, BM25 | All 5 indexes + analyzer |
| False | DocumentPipeline | documents + chunks | BM25 on chunks | idx_doc_source, idx_doc_hash, idx_chunk_content + analyzer |
