# Schema (D17-D19)

### D17: Documents table (both classes)

| Field | Type | Notes |
|---|---|---|
| `source` | string | |
| `content` | string | BM25-indexed in DocumentConnector |
| `mime_type` | string | |
| `title` | option\<string\> | |
| `authors` | option\<array\<string\>\> | |
| `created_at` | option\<datetime\> | |
| `ingested_at` | datetime DEFAULT time::now() | |
| `metadata` | object FLEXIBLE | Must be FLEXIBLE for arbitrary keys in SCHEMAFULL |
| `quality_score` | option\<float\> | |
| `content_hash` | string | Deduplication by content hash |
| `detected_languages` | option\<array\<string\>\> | |
| `keywords` | option\<array\<object\>\> | |

### D18: Chunks table (DocumentPipeline only)

| Field | Type | Notes |
|---|---|---|
| `document` | record\<documents\> | |
| `content` | string | BM25-indexed |
| `chunk_index` | int | |
| `embedding` | option\<array\<float\>\> | HNSW-indexed. null when embed=False |
| `page_number` | option\<int\> | |
| `char_start` | option\<int\> | Character offset in original text |
| `char_end` | option\<int\> | Character offset in original text |
| `token_count` | option\<int\> | For LLM context window budgeting |
| `first_page` | option\<int\> | For citation |
| `last_page` | option\<int\> | For citation |

### D19: Indexes

| Index | Type | DocumentConnector | DocumentPipeline |
|---|---|---|---|
| `idx_doc_source` | UNIQUE on documents.source | Yes | Yes |
| `idx_doc_hash` | UNIQUE on documents.content_hash | Yes | Yes |
| `idx_doc_content` | BM25 on documents.content | Yes | No (search on chunks) |
| `idx_chunk_embedding` | HNSW on chunks.embedding | N/A | Yes (when embed=True) |
| `idx_chunk_content` | BM25 on chunks.content | N/A | Yes |
| `chunk_analyzer` | Analyzer for BM25 | Yes (doc-level) | Yes (chunk-level) |
