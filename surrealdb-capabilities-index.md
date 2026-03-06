# SurrealDB Python SDK Capabilities Index

> Index for `surrealdb-capabilities.md` — SDK v2.0.0-alpha.1 (stable: v1.0.8)
> Full reference: `./surrealdb-capabilities.md`

---

## 1. Architecture Overview (L11-52)
- Multi-model DB: document, graph, relational, vector, key-value, time-series
- Rust extension via PyO3 + Maturin, Python 3.10+
- Sync (`Surreal`) and async (`AsyncSurreal`) with full parity
- CBOR wire format, embedded/WebSocket/HTTP connections
- Package structure: connections/, cbor/, data/types/, request_message/

## 2. Installation (L56-73)
- `pip install surrealdb` (core) or `surrealdb[pydantic]`
- Dependencies: aiohttp, pydantic-core, requests, websockets

## 3. Connection Methods (L77-135)

### URL Schemes (L81-86)
- `ws://`/`wss://` — WebSocket (live queries + transactions)
- `http://`/`https://` — HTTP (no live queries, no transactions)
- `memory`/`mem://` — Embedded in-memory (live queries, no transactions)
- `file://`/`surrealkv://` — Embedded file (live queries, no transactions)

### URL Parsing (L89-106) — `Url` class, `UrlScheme` enum
### Usage Patterns (L108-128) — context managers, sync/async, embedded
### Connection Internals (L130-134) — WebSocket queues, Rust extension, UtilsMixin

## 4. Authentication (L138-184)
- Root signin: `db.signin({"username": "root", "password": "root"})`
- Scoped record auth, bearer key, refresh token
- `signup()`, `authenticate()` (JWT), `invalidate()`, `info()`
- Tokens dataclass: `access` + `refresh` fields

## 5. CRUD Operations (L188-226)
- `create(record, data)` — create record(s)
- `select(record)` — read record(s)
- `update(record, data)` — replace entire record
- `upsert(record, data)` — insert or replace
- `merge(record, data)` — deep merge partial data
- `patch(record, data)` — JSON Patch (RFC 6902)
- `insert(table, data)` — bulk insert
- `insert_relation(table, data)` — graph edges
- `delete(record)` — delete record(s)

## 6. Query Methods (L230-252)
- `query(sql, vars)` — parameterized SurrealQL, returns first result
- `query_raw(sql, params)` — full RPC response dict
- `let(key, value)` / `unset(key)` — connection-scoped variables
- `version()` — server version

## 7. Live Queries (L256-275)
- WebSocket/embedded only
- `live(table, diff)` -> UUID, `subscribe_live(uuid)` -> generator
- `kill(uuid)` to stop

## 8. Sessions & Transactions (L279-303)
- WebSocket only, HTTP/embedded raise NotImplementedError
- `new_session()` -> Session, `begin_transaction()` -> Transaction
- `commit()` / `cancel()` on transaction

## 9. Data Types (L306-491)

### Value Type Alias (L310-318)
- Union of str, int, float, bool, None, bytes, UUID, Decimal, Table, Range, RecordID, Duration, Datetime, Geometry types, dict, list

### RecordID (L322-354)
- `table_name` + `id`, `parse()` static method, identifier escaping
- Pydantic v2 integration via `__get_pydantic_core_schema__`

### Table (L358-367) — simple wrapper around table_name
### Duration (L370-403) — nanosecond precision, compound parsing ("3h45m10s")
### Datetime (L406-411) — ISO 8601 string wrapper
### Range & Bounds (L414-433) — BoundIncluded, BoundExcluded
### Geometry Types (L436-491) — Point, Line, Polygon, Multi*, Collection (GeoJSON)

## 10. CBOR Wire Format (L495-561)

### Tag Constants (L501-521) — 17 custom semantic tags (DATETIME through GEOMETRY_COLLECTION)
### Public API (L524-528) — CBOREncoder, CBORDecoder, dump/dumps/load/loads
### Internal Types (L532-548) — CBORError hierarchy, CBORTag, CBORSimpleValue, FrozenDict
### Encoding Behavior (L552-556) — None -> tag 6 (NONE), cyclic reference detection
### Decoding Behavior (L558-561) — 8 major types, 17 tag handlers, custom hooks

## 11. Error Handling (L564-711)

### ErrorKind Constants (L568-580) — 10 kinds: Validation through Internal
### Exception Hierarchy (L583-603)
- `SurrealError` (base)
  - `ServerError` -> ValidationError, ConfigurationError, ThrownError, QueryError, SerializationError, NotAllowedError, NotFoundError, AlreadyExistsError, InternalError
  - `ConnectionUnavailableError`, `UnsupportedEngineError`, `UnsupportedFeatureError`
  - `UnexpectedResponseError`, `InvalidRecordIdError`, `InvalidDurationError`, `InvalidGeometryError`, `InvalidTableError`

### ServerError Properties (L618-628) — per-subclass convenience properties
### Detail Kind Constants (L632-696) — Auth, Validation, Configuration, Query, Serialization, NotAllowed, NotFound, AlreadyExists, Connection
### Legacy Error Codes (L700-711) — CODE_TO_KIND mapping
### Error Parsing (L714-717) — `parse_rpc_error()`, `parse_query_error()`

## 12. Complete API Method Reference (L720-756)
- 30 methods: connect, close, use, version, signin, signup, authenticate, invalidate, info, let, unset, query, query_raw, select, create, update, upsert, merge, patch, insert, insert_relation, delete, live, subscribe_live, kill, new_session, attach, detach, begin_transaction, begin, commit, cancel

## 13. Complete Public Exports (L759-793)
- Factory functions, connection classes, data types, errors, detail constants, CBOR tags

## 14. SurrealDB Database Features (L797-877)

### Multi-Model Support (L799-806) — document, graph, relational, vector, KV, time-series
### Schema Options (L808-811) — schemaless, schemafull, mix per table
### Storage & Scalability (L813-819) — in-memory, embedded, single-node, distributed
### Indexing (L821-828) — unique, compound, full-text (BM25), vector (HNSW), hybrid search
### Security & Auth (L830-839) — RBAC, field/table/record-level, JWT/OAuth
### Real-Time (L841-845) — WebSocket, LIVE SELECT, table events
### Geospatial (L847-851) — GeoJSON, geo operators/functions
### File Storage (L853-856) — Buckets (memory/filesystem/S3/GCS/Azure)
### ML Integration (L858-862) — SurrealML, ONNX inference, .surml format
### AI Agent Support (L864-872) — MCP, RAG, Graph RAG, LangChain, agent memory

## 15. SurrealQL Statements (L886-927)
- Database resource: DEFINE, ALTER, REMOVE, REBUILD, ACCESS, USE, INFO, SHOW
- Query/CRUD: CREATE, INSERT, RELATE, UPDATE, UPSERT, SELECT, LIVE SELECT, DELETE, KILL, LET
- Control flow: BEGIN, COMMIT, CANCEL, FOR, CONTINUE, BREAK, IF/ELSE, SLEEP, RETURN, THROW

## 16. SurrealQL Operators (L930-990)
- Logical: AND, OR, !, ??, ?:
- Comparison: =, !=, ==, ?=, *=, <, <=, >, >=
- Arithmetic: +, -, *, /, **
- Containment: CONTAINS, CONTAINSALL, CONTAINSANY, CONTAINSNONE
- Membership: IN, NOT IN, ALLINSIDE, ANYINSIDE, NONEINSIDE
- Geometric: OUTSIDE, INTERSECTS
- Search: @@ (full-text), <|K,METRIC|> (KNN)

## 17. SurrealQL Built-in Functions (L993-1071)
- ~340+ functions across 18 categories:
- Array (56), String (57), Math (~63 + 21 constants), Time (39 + 3 constants)
- Type (44), Crypto (14), Vector (20), Duration (17 + 1 constant), Geo (7)
- HTTP (6), Record (5), Object (8), Rand (12), Parse (9), Session (8)
- Search (6), Encoding (4), Set (9), File (13), Value (3), Standalone (4)

## 18. SurrealQL Data Model Types (L1074-1114)
- Primitives: any, bool, string, int, float, decimal, number
- Temporal: datetime, duration
- Collections: array, set, object
- Specialized: bytes, geometry, regex, record, range
- Modifiers: option<type>, literal

## 19. Observability (L1117-1128)
- Pydantic Logfire, OpenTelemetry tracing, Jaeger/DataDog/Honeycomb

## 20. Framework Examples (L1132-1134)
- FastAPI, Django, Flask, Litestar, Starlette, Sanic, Quart, GraphQL, Jupyter, FastMCP, Logfire, Embedded

## 21. Version History (L1138-1147)
- v2.0.0-alpha.1: SurrealDB 3.x protocol, structured errors, Logfire, dropped Python 3.9
- v1.0.8: Pydantic extra for RecordID
- v1.0.7: Embedded DB, compound duration, framework examples
- v1.0.0: Initial stable release

## Quick Reference Table (L1150-1175)
- Common task -> API mapping (connect, signin, CRUD, query, live, transactions)
