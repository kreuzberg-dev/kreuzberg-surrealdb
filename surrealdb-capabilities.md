# SurrealDB Python SDK Capabilities Reference

> Deep analysis of surrealdb Python SDK for building integrations.
> Updated: 2026-03-06 | Latest: v2.0.0-alpha.1 (stable: v1.0.8)
> Repository: https://github.com/surrealdb/surrealdb.py
> Docs: https://surrealdb.com/docs/sdk/python
> Features: https://surrealdb.com/features

---

## 1. Architecture Overview

SurrealDB is a **multi-model database** (document, graph, relational, vector, key-value, time-series) with a Python SDK built as a **Rust extension** (PyO3 + Maturin). The Rust core provides an embedded database engine; remote connections use WebSocket or HTTP.

**Key facts:**
- Python 3.10+ (3.10, 3.11, 3.12, 3.13) | Apache-2.0 license
- Sync (`Surreal`) and async (`AsyncSurreal`) APIs with full parity
- CBOR wire format with custom tags for SurrealDB types
- Embedded (in-memory/file), WebSocket, and HTTP connection modes
- ACID-compliant transactions (WebSocket only)
- Live queries / real-time subscriptions
- Optional Pydantic integration (`surrealdb[pydantic]`)
- Build system: Maturin (Rust-based Python extension builder)

### Package Structure

```
src/surrealdb/
  __init__.py              # Public API, factory functions
  _surrealdb_ext.pyi       # Type stubs for native Rust extension
  errors.py                # Full error hierarchy
  types.py                 # Value type alias, Tokens dataclass
  py.typed                 # PEP 561 marker
  cbor/                    # CBOR encoder/decoder (custom SurrealDB tags)
    _decoder.py, _encoder.py, _types.py
    decoder.py, encoder.py, types.py, tool.py
  connections/
    async_embedded.py      # AsyncEmbeddedSurrealConnection
    async_http.py          # AsyncHttpSurrealConnection
    async_ws.py            # AsyncWsSurrealConnection + Session/Transaction
    blocking_embedded.py   # BlockingEmbeddedSurrealConnection
    blocking_http.py       # BlockingHttpSurrealConnection
    blocking_ws.py         # BlockingWsSurrealConnection + Session/Transaction
    async_template.py      # AsyncTemplate (abstract base, 22 methods)
    sync_template.py       # SyncTemplate (abstract base, 21 methods)
    url.py                 # Url, UrlScheme enum
    utils_mixin.py         # UtilsMixin (response checking, result unwrapping)
  data/types/
    constants.py           # CBOR tag numeric constants
    datetime.py, duration.py, geometry.py, range.py, record_id.py, table.py
  request_message/         # RPC request construction
```

---

## 2. Installation

```sh
pip install surrealdb           # core SDK
pip install surrealdb[pydantic] # with Pydantic RecordID support
uv add surrealdb                # via uv
```

**Core Dependencies:**
- `aiohttp>=3.8.0` (async HTTP)
- `pydantic-core>=2.0.1` (validation/serialization)
- `requests>=2.25.0` (sync HTTP)
- `websockets>=10.0` (WebSocket connections)
- `typing_extensions>=4.0.0` (Python < 3.12 only)

**Optional:** `pydantic>=2.12.5` (via `surrealdb[pydantic]`)

**Tooling:** `mypy` (strict), `pyright` (strict), `ruff` (isort + pyupgrade), `pytest` with `asyncio_mode = "auto"`

---

## 3. Connection Methods

Factory pattern: `Surreal(url)` / `AsyncSurreal(url)` auto-routes by URL scheme.

| Scheme | Transport | Connection Class (Sync / Async) | Live Queries | Transactions |
|---|---|---|---|---|
| `ws://`, `wss://` | WebSocket | `BlockingWsSurrealConnection` / `AsyncWsSurrealConnection` | Yes | Yes |
| `http://`, `https://` | HTTP | `BlockingHttpSurrealConnection` / `AsyncHttpSurrealConnection` | No | No |
| `memory`, `mem://` | Embedded (in-memory) | `BlockingEmbeddedSurrealConnection` / `AsyncEmbeddedSurrealConnection` | Yes | No |
| `file://`, `surrealkv://` | Embedded (file) | `BlockingEmbeddedSurrealConnection` / `AsyncEmbeddedSurrealConnection` | Yes | No |

### URL Parsing Internals

```python
class UrlScheme(Enum):
    HTTP = "http"
    HTTPS = "https"
    WS = "ws"
    WSS = "wss"
    MEM = "mem"
    FILE = "file"
    MEMORY = "memory"
    SURREALKV = "surrealkv"

class Url:
    raw_url: str       # with "/rpc" stripped
    scheme: UrlScheme
    hostname: str | None
    port: int | None
```

### Usage

```python
# Sync context manager
with Surreal("ws://localhost:8000/rpc") as db:
    db.signin({"username": "root", "password": "root"})
    db.use("namespace", "database")

# Async context manager
async with AsyncSurreal("ws://localhost:8000/rpc") as db:
    await db.signin({"username": "root", "password": "root"})
    await db.use("namespace", "database")

# Embedded (no server needed)
with Surreal("memory") as db:
    db.use("test", "test")
    db.signin({"username": "root", "password": "root"})

with Surreal("file://mydb") as db:
    db.use("test", "test")
```

### Connection Internals

- **WebSocket**: Manages via `websockets` library. Maintains `qry` dict (mapping query IDs to futures) and `live_queues` for live subscriptions.
- **Embedded**: Uses compiled Rust extension (`_surrealdb_ext`) exposing `AsyncEmbeddedDB` and `SyncEmbeddedDB` classes that communicate via CBOR-encoded requests.
- **UtilsMixin**: Shared utility methods — `check_response_for_error()`, `_unwrap_result()` (unwraps single-item lists for single-record operations), `_resource_to_variable()` (converts Table/RecordID/str to SurrealQL variable references).

---

## 4. Authentication

```python
# Root authentication
db.signin({"username": "root", "password": "root"})

# Scoped record authentication -> returns Tokens(access, refresh)
tokens = db.signin({
    "namespace": "ns", "database": "db", "access": "user",
    "variables": {"email": "user@example.com", "pass": "secret"},
})

# Bearer key authentication
db.signin({"namespace": "ns", "database": "db", "access": "api", "key": bearer_key})

# Refresh token authentication
db.signin({"namespace": "ns", "database": "db", "access": "user", "refresh": refresh_token})

# Signup (register new user)
tokens = db.signup({
    "namespace": "ns", "database": "db", "access": "user",
    "variables": {"email": "new@example.com", "pass": "secret"},
})

# JWT authentication
db.authenticate("eyJhbGciOiJIUzI1NiIs...")

# Invalidate session
db.invalidate()

# Get authenticated user info
user = db.info()
```

### Tokens Dataclass

```python
@dataclass(frozen=True)
class Tokens:
    access: str | None = None     # JWT access token
    refresh: str | None = None    # Refresh token

def parse_auth_result(result: Any) -> Tokens:
    # str -> Tokens(access=result, refresh=None)
    # dict -> Tokens(access=result.get("access"), refresh=result.get("refresh"))
    # else -> Tokens(access=None, refresh=None)
```

---

## 5. CRUD Operations

All methods accept `RecordIdType = str | RecordID | Table`.

```python
# CREATE — create record(s) (executes: CREATE $record CONTENT $data)
db.create("person", {"name": "Tobie", "age": 30})
db.create(RecordID("person", "tobie"), {"name": "Tobie"})

# SELECT — read record(s) (executes: SELECT * FROM $record)
all_people = db.select("person")
person = db.select(RecordID("person", "tobie"))

# UPDATE — replace entire record data (executes: UPDATE $record CONTENT $data)
db.update("person:tobie", {"name": "Tobie", "settings": {"active": True}})

# UPSERT — insert or replace (executes: UPSERT $record CONTENT $data)
db.upsert("person:tobie", {"name": "Tobie", "settings": {"active": True}})

# MERGE — deep merge partial data (executes: UPDATE $record MERGE $data)
db.merge("person:tobie", {"settings": {"active": True}})

# PATCH — JSON Patch operations RFC 6902 (executes: UPDATE $record PATCH $data)
db.patch("person:tobie", [
    {"op": "replace", "path": "/settings/active", "value": False},
    {"op": "add", "path": "/tags", "value": ["dev"]},
    {"op": "remove", "path": "/temp"},
])

# INSERT — bulk insert (executes: INSERT INTO $table $data)
db.insert("person", [{"name": "A"}, {"name": "B"}])

# INSERT RELATION — graph edges (executes: INSERT RELATION INTO $table $data)
db.insert_relation("likes", {"in": "person:1", "id": "object", "out": "person:2"})

# DELETE (executes: DELETE $record)
db.delete(RecordID("person", "tobie"))
db.delete("person")  # delete all in table
```

---

## 6. Query Methods

```python
# Raw SurrealQL (returns first statement result)
results = db.query("SELECT * FROM person WHERE age > 25")

# Parameterized queries (prevents injection)
results = db.query(
    "SELECT * FROM person WHERE name = $name AND age > $min_age",
    {"name": "Tobie", "min_age": 25}
)

# Raw query (returns full RPC response dict)
raw = db.query_raw("SELECT * FROM person", params={"key": "val"})

# Connection-scoped variables
db.let("name", {"first": "Tobie", "last": "Hitchcock"})
db.query("CREATE person SET name = $name")
db.unset("name")

# Server version
version = db.version()
```

---

## 7. Live Queries / Real-Time Subscriptions

WebSocket and embedded connections only. Returns notifications as records are created/updated/deleted.

```python
# Async
query_id = await db.live("person")           # returns UUID
query_id = await db.live("person", diff=True) # JSON Patch mode

async for notification in db.subscribe_live(query_id):
    print(notification)  # {"action": "CREATE", "result": {...}}

await db.kill(query_id)

# Sync
query_id = db.live("person")
for notification in db.subscribe_live(query_id):
    print(notification)
db.kill(query_id)
```

---

## 8. Sessions & Transactions

WebSocket connections only. HTTP/embedded raise `NotImplementedError`.

```python
async with AsyncSurreal("ws://localhost:8000/rpc") as db:
    await db.signin({"username": "root", "password": "root"})
    await db.use("test", "test")

    # Create a session
    session = await db.new_session()
    await session.use("test", "test")
    result = await session.query("SELECT 1")

    # Begin a transaction on the session
    txn = await session.begin_transaction()
    await txn.query("CREATE person SET name = 'Alice'")
    await txn.commit()    # or await txn.cancel()

    await session.close_session()
```

**RPC methods:** `attach`, `detach`, `begin`, `commit`, `cancel`
**Types:** `AsyncSurrealSession`, `AsyncSurrealTransaction`, `BlockingSurrealSession`, `BlockingSurrealTransaction`

---

## 9. Data Types

### Value Type Alias

```python
Value = (
    str | int | float | bool | None | bytes | UUID | Decimal
    | Table | Range | RecordID | Duration | Datetime
    | GeometryPoint | GeometryLine | GeometryPolygon
    | GeometryMultiPoint | GeometryMultiLine | GeometryMultiPolygon
    | GeometryCollection
    | dict[str, Value] | list[Value]
)
```

### RecordID

```python
RecordIdType = Union[str, RecordID, Table]

class RecordID:
    table_name: str
    id: Value

    def __init__(self, table_name: str, identifier: Any) -> None
    def __str__(self) -> str          # "table_name:identifier" with escaping
    def __repr__(self) -> str         # "RecordID(table_name=..., record_id=...)"
    def __eq__(self, other: object) -> bool

    @staticmethod
    def parse(record_str: str) -> RecordID
        # Splits on ":" -> RecordID(table, record_id)
        # Raises InvalidRecordIdError if no ":" found

    @staticmethod
    def _escape_identifier(identifier: str) -> str
        # Escapes with angle brackets when:
        # - Empty string
        # - Contains non-alphanumeric chars (except underscore)
        # - Contains only digits and underscores (no alphabetic chars)

    # Pydantic v2 integration (with surrealdb[pydantic]):
    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type, _handler) -> CoreSchema
        # Validates from str via parse(), or accepts RecordID instance
        # Serializes to str in JSON mode, passthrough in Python mode
    @classmethod
    def __get_pydantic_json_schema__(cls, _core_schema, handler) -> JsonSchemaValue
```

### Table

```python
TableType = Union[str, Table]

class Table:
    table_name: str
    def __init__(self, table_name: str) -> None
    def __str__(self) -> str       # returns table_name
    def __repr__(self) -> str
    def __eq__(self, other) -> bool
```

### Duration

```python
UNITS = {
    "ns": 1, "us": 1000, "µs": 1000, "ms": 1_000_000,
    "s": 1_000_000_000, "m": 60_000_000_000, "h": 3_600_000_000_000,
    "d": 86_400_000_000_000, "w": 604_800_000_000_000, "y": 31_536_000_000_000_000,
}

@dataclass
class Duration:
    elapsed: int = 0   # nanoseconds

    @staticmethod
    def parse(value: str | int, nanoseconds: int = 0) -> Duration
        # int -> treated as seconds
        # str -> regex parses compound "3h45m10s" style patterns

    def get_seconds_and_nano(self) -> tuple[int, int]   # (whole_seconds, remaining_ns)

    # Conversion properties (integer division):
    @property nanoseconds -> int
    @property microseconds -> int
    @property milliseconds -> int
    @property seconds -> int
    @property minutes -> int
    @property hours -> int
    @property days -> int
    @property weeks -> int
    @property years -> int

    def to_string(self) -> str         # Largest unit representation, e.g. "3h"
    def to_compact(self) -> list[int]  # [whole_seconds] for CBOR compact encoding
    def __eq__(self, other) -> bool
```

### Datetime

```python
class Datetime:
    dt: str    # ISO 8601 string
    def __init__(self, dt: str) -> None
```

### Range and Bounds

```python
class Bound:
    def __init__(self) -> None
    def __eq__(self, other) -> bool

@dataclass
class BoundIncluded(Bound):
    value: Any

@dataclass
class BoundExcluded(Bound):
    value: Any

@dataclass
class Range:
    begin: Bound
    end: Bound
    def __eq__(self, other) -> bool
```

### Geometry Types

All geometry types extend `Geometry` base class with `get_coordinates()` and `parse_coordinates()` methods.

```python
class Geometry:
    def get_coordinates(self) -> Any
    @staticmethod
    def parse_coordinates(coordinates: Any) -> Any

@dataclass
class GeometryPoint(Geometry):
    longitude: float
    latitude: float
    def get_coordinates(self) -> tuple[float, float]        # (lon, lat)
    @staticmethod
    def parse_coordinates(coords: tuple[float, float]) -> GeometryPoint

@dataclass
class GeometryLine(Geometry):
    geometry_points: list[GeometryPoint]
    def __init__(self, point1: GeometryPoint, point2: GeometryPoint, *other_points)
    def get_coordinates(self) -> list[tuple[float, float]]
    @staticmethod
    def parse_coordinates(coords) -> GeometryLine

@dataclass
class GeometryPolygon(Geometry):
    geometry_lines: list[GeometryLine]
    def __init__(self, exterior_ring: GeometryLine, *interior_rings: GeometryLine)
    @staticmethod
    def _validate_ring(ring: GeometryLine, ring_type: str) -> None
        # Raises InvalidGeometryError if < 4 points or first != last
    def get_coordinates(self) -> list[list[tuple[float, float]]]
    @staticmethod
    def parse_coordinates(coords) -> GeometryPolygon

@dataclass
class GeometryMultiPoint(Geometry):
    geometry_points: list[GeometryPoint]
    def __init__(self, *geometry_points: GeometryPoint)

@dataclass
class GeometryMultiLine(Geometry):
    geometry_lines: list[GeometryLine]
    def __init__(self, *geometry_lines: GeometryLine)

@dataclass
class GeometryMultiPolygon(Geometry):
    geometry_polygons: list[GeometryPolygon]
    def __init__(self, *geometry_polygons: GeometryPolygon)

@dataclass
class GeometryCollection:
    geometries: list[Geometry]
    def __init__(self, *geometries: Geometry)
```

---

## 10. CBOR Wire Format

All communication uses CBOR (Concise Binary Object Representation) with custom semantic tags for SurrealDB types.

### CBOR Tag Constants

```python
TAG_DATETIME         = 0     # ISO 8601 datetime string
TAG_NONE             = 6     # SurrealDB NONE (not standard CBOR null)
TAG_TABLE_NAME       = 7     # Table reference
TAG_RECORD_ID        = 8     # Record identifier [table, id]
TAG_UUID_STRING      = 9     # UUID value
TAG_DECIMAL_STRING   = 10    # High-precision decimal
TAG_DATETIME_COMPACT = 12    # Compact datetime encoding
TAG_DURATION         = 13    # Duration string
TAG_DURATION_COMPACT = 14    # Compact duration [seconds]
TAG_RANGE            = 49    # Range value [begin, end]
TAG_BOUND_INCLUDED   = 50    # Inclusive bound
TAG_BOUND_EXCLUDED   = 51    # Exclusive bound
TAG_GEOMETRY_POINT         = 88
TAG_GEOMETRY_LINE          = 89
TAG_GEOMETRY_POLYGON       = 90
TAG_GEOMETRY_MULTI_POINT   = 91
TAG_GEOMETRY_MULTI_LINE    = 92
TAG_GEOMETRY_MULTI_POLYGON = 93
TAG_GEOMETRY_COLLECTION    = 94
```

### CBOR Public API

```python
from surrealdb.cbor.encoder import CBOREncoder, dump, dumps, shareable_encoder
from surrealdb.cbor.decoder import CBORDecoder, load, loads
```

### CBOR Internal Types

```python
class CBORError(Exception)            # Base CBOR error
class CBOREncodeError(CBORError)
class CBOREncodeTypeError(CBOREncodeError)
class CBOREncodeValueError(CBOREncodeError)
class CBORDecodeError(CBORError)
class CBORDecodeValueError(CBORDecodeError)
class CBORDecodeEOF(CBORDecodeError)

class CBORTag:                        # Semantic tag wrapper
    tag: int
    value: Any

class CBORSimpleValue:                # Simple values 0-23, 32-255
    value: int

class FrozenDict(Mapping):            # Immutable, hashable dict
```

### Encoding Behavior
- Python `None` → CBOR tag 6 wrapping null (`b"\xc6\xf6"`) — SurrealDB's `NONE` type, not standard CBOR null
- Uses `@shareable_encoder` and `@container_encoder` decorators for cyclic reference detection
- Supports deferred type resolution for dynamically imported types
- String referencing for repeated strings within semantic tag boundaries

### Decoding Behavior
- Handles 8 CBOR major types + 17 semantic tag handlers
- Supports indefinite-length items, large data chunking, UTF-8 validation
- Custom hooks via `tag_hook` and `object_hook` parameters

---

## 11. Error Handling

### ErrorKind Constants

```python
class ErrorKind:
    VALIDATION = "Validation"
    CONFIGURATION = "Configuration"
    THROWN = "Thrown"
    QUERY = "Query"
    SERIALIZATION = "Serialization"
    NOT_ALLOWED = "NotAllowed"
    NOT_FOUND = "NotFound"
    ALREADY_EXISTS = "AlreadyExists"
    CONNECTION = "Connection"
    INTERNAL = "Internal"
```

### Exception Hierarchy

```
SurrealError (base)
├── ServerError (from SurrealDB server)
│   ├── ValidationError      — parse errors, invalid params
│   ├── ConfigurationError   — unsupported feature
│   ├── ThrownError          — user THROW in SurrealQL
│   ├── QueryError           — timeout, cancelled
│   ├── SerializationError   — encode/decode failure
│   ├── NotAllowedError      — permission denied, token expired
│   ├── NotFoundError        — table/record/namespace not found
│   ├── AlreadyExistsError   — duplicate record/table
│   └── InternalError        — server internal error
├── ConnectionUnavailableError — no active connection
├── UnsupportedEngineError     — invalid URL protocol
├── UnsupportedFeatureError    — feature not supported by connection type
├── UnexpectedResponseError    — unexpected server response format
├── InvalidRecordIdError       — cannot parse RecordID string
├── InvalidDurationError       — cannot parse Duration string
├── InvalidGeometryError       — invalid geometry data
└── InvalidTableError          — invalid table/record string
```

### ServerError Base Class

```python
class ServerError(SurrealError):
    def __init__(self, kind: str, message: str, code: int = 0,
                 details: dict[str, Any] | None = None, cause: ServerError | None = None)
    @property
    def server_cause(self) -> ServerError | None
    def has_kind(self, kind: str) -> bool       # check this error or any cause in chain
    def find_cause(self, kind: str) -> ServerError | None
```

### ServerError Subclass Convenience Properties

| Class | Properties |
|---|---|
| `ValidationError` | `is_parse_error`, `parameter_name` |
| `ConfigurationError` | `is_live_query_not_supported` |
| `QueryError` | `is_not_executed`, `is_timed_out`, `is_cancelled`, `timeout` |
| `SerializationError` | `is_deserialization` |
| `NotAllowedError` | `is_token_expired`, `is_invalid_auth`, `is_scripting_blocked`, `method_name`, `function_name`, `target_name` |
| `NotFoundError` | `table_name`, `record_id`, `method_name`, `namespace_name`, `database_name`, `session_id` |
| `AlreadyExistsError` | `record_id`, `table_name`, `session_id`, `namespace_name`, `database_name` |

### Detail Kind Constants (for granular matching)

```python
class AuthDetailKind:
    TOKEN_EXPIRED = "TokenExpired"
    SESSION_EXPIRED = "SessionExpired"
    INVALID_AUTH = "InvalidAuth"
    UNEXPECTED_AUTH = "UnexpectedAuth"
    MISSING_USER_OR_PASS = "MissingUserOrPass"
    NO_SIGNIN_TARGET = "NoSigninTarget"
    INVALID_PASS = "InvalidPass"
    TOKEN_MAKING_FAILED = "TokenMakingFailed"
    INVALID_SIGNUP = "InvalidSignup"
    INVALID_ROLE = "InvalidRole"
    NOT_ALLOWED = "NotAllowed"

class ValidationDetailKind:
    PARSE = "Parse"
    INVALID_REQUEST = "InvalidRequest"
    INVALID_PARAMS = "InvalidParams"
    NAMESPACE_EMPTY = "NamespaceEmpty"
    DATABASE_EMPTY = "DatabaseEmpty"
    INVALID_PARAMETER = "InvalidParameter"
    INVALID_CONTENT = "InvalidContent"
    INVALID_MERGE = "InvalidMerge"

class ConfigurationDetailKind:
    LIVE_QUERY_NOT_SUPPORTED = "LiveQueryNotSupported"
    BAD_LIVE_QUERY_CONFIG = "BadLiveQueryConfig"
    BAD_GRAPHQL_CONFIG = "BadGraphqlConfig"

class QueryDetailKind:
    NOT_EXECUTED = "NotExecuted"
    TIMED_OUT = "TimedOut"
    CANCELLED = "Cancelled"

class SerializationDetailKind:
    SERIALIZATION = "Serialization"
    DESERIALIZATION = "Deserialization"

class NotAllowedDetailKind:
    SCRIPTING = "Scripting"
    AUTH = "Auth"
    METHOD = "Method"
    FUNCTION = "Function"
    TARGET = "Target"

class NotFoundDetailKind:
    METHOD = "Method"
    SESSION = "Session"
    TABLE = "Table"
    RECORD = "Record"
    NAMESPACE = "Namespace"
    DATABASE = "Database"
    TRANSACTION = "Transaction"

class AlreadyExistsDetailKind:
    SESSION = "Session"
    TABLE = "Table"
    RECORD = "Record"
    NAMESPACE = "Namespace"
    DATABASE = "Database"

class ConnectionDetailKind:
    UNINITIALISED = "Uninitialised"
    ALREADY_CONNECTED = "AlreadyConnected"
```

### Legacy Error Code Mapping

```python
CODE_TO_KIND = {
    -32700: "Validation",   -32600: "Validation",   -32603: "Validation",
    -32601: "NotFound",     -32602: "NotAllowed",   -32002: "NotAllowed",
    -32604: "Configuration", -32605: "Configuration", -32606: "Configuration",
    -32000: "Internal",     -32001: "Connection",
    -32003: "Query",        -32004: "Query",        -32005: "Query",
    -32006: "Thrown",       -32007: "Serialization", -32008: "Serialization",
}
```

Legacy alias: `SurrealDBMethodError` = `ServerError`

### Error Parsing Functions

- `parse_rpc_error(raw)` — Handles both new format (`kind`+`details`+`cause`) and legacy (`code`+`message`). Recursively parses `cause` chains.
- `parse_query_error(raw)` — Parses query result errors. Includes workaround for SurrealDB v3.0.0 double-wrapped details bug.

---

## 12. Complete API Method Reference

| Method | Signature | Returns | Description |
|---|---|---|---|
| `connect(url)` | `url: str \| None` | — | Connect to endpoint |
| `close()` | — | — | Close connection |
| `use(ns, db)` | `namespace: str, database: str` | — | Switch namespace/database |
| `version()` | — | `str` | Get server version |
| `signin(vars)` | `vars: dict[str, Value]` | `Tokens` | Sign in |
| `signup(vars)` | `vars: dict[str, Value]` | `Tokens` | Register user |
| `authenticate(token)` | `token: str` | — | Auth with JWT |
| `invalidate()` | — | — | Invalidate session |
| `info()` | — | `Value` | Get user info |
| `let(key, value)` | `key: str, value: Value` | — | Set connection variable |
| `unset(key)` | `key: str` | — | Remove connection variable |
| `query(sql, vars)` | `query: str, vars: dict \| None` | `Value` | Execute SurrealQL (first result) |
| `query_raw(sql, params)` | `query: str, params: dict \| None` | `dict` | Execute SurrealQL (full RPC response) |
| `select(record)` | `record: RecordIdType` | `Value` | Select records |
| `create(record, data)` | `record: RecordIdType, data: Value \| None` | `Value` | Create record |
| `update(record, data)` | `record: RecordIdType, data: Value \| None` | `Value` | Replace record entirely |
| `upsert(record, data)` | `record: RecordIdType, data: Value \| None` | `Value` | Insert or update |
| `merge(record, data)` | `record: RecordIdType, data: Value \| None` | `Value` | Deep merge partial |
| `patch(record, data)` | `record: RecordIdType, data: Value \| None` | `Value` | JSON Patch |
| `insert(table, data)` | `table: str \| Table, data: Value` | `Value` | Bulk insert |
| `insert_relation(table, data)` | `table: str \| Table, data: Value` | `Value` | Insert graph edge |
| `delete(record)` | `record: RecordIdType` | `Value` | Delete records |
| `live(table, diff)` | `table: str \| Table, diff: bool` | `UUID` | Start live query |
| `subscribe_live(uuid)` | `query_uuid: str \| UUID` | `Generator` / `AsyncGenerator` | Subscribe to notifications |
| `kill(uuid)` | `query_uuid: str \| UUID` | — | Kill live query |
| `new_session()` | — | `Session` | Create session (WS only) |
| `attach()` | — | `UUID` | Attach new session (WS only) |
| `detach(id)` | `session_id: UUID` | — | Detach session (WS only) |
| `begin_transaction()` | — | `Transaction` | Begin txn (WS session only) |
| `begin(session_id)` | `session_id: UUID \| None` | `UUID` | Begin txn (low-level) |
| `commit(txn_id, session_id)` | `txn_id: UUID, session_id: UUID \| None` | — | Commit transaction |
| `cancel(txn_id, session_id)` | `txn_id: UUID, session_id: UUID \| None` | — | Rollback transaction |

---

## 13. Complete Public Exports

```python
__all__ = [
    # Factory functions
    "AsyncSurreal", "Surreal",
    # Connection classes
    "AsyncEmbeddedSurrealConnection", "AsyncHttpSurrealConnection",
    "AsyncSurrealSession", "AsyncSurrealTransaction", "AsyncWsSurrealConnection",
    "BlockingEmbeddedSurrealConnection", "BlockingHttpSurrealConnection",
    "BlockingSurrealSession", "BlockingSurrealTransaction", "BlockingWsSurrealConnection",
    # Data types
    "Table", "Duration", "Geometry", "Range", "RecordID", "Datetime", "Tokens", "Value",
    # Errors
    "SurrealError", "ServerError", "ValidationError", "ConfigurationError",
    "ThrownError", "QueryError", "SerializationError", "NotAllowedError",
    "NotFoundError", "AlreadyExistsError", "InternalError", "ErrorKind",
    "ConnectionUnavailableError", "UnsupportedEngineError", "UnsupportedFeatureError",
    "UnexpectedResponseError", "InvalidRecordIdError", "InvalidDurationError",
    "InvalidGeometryError", "InvalidTableError",
    # Error detail constants
    "AuthDetailKind", "ValidationDetailKind", "ConfigurationDetailKind",
    "QueryDetailKind", "SerializationDetailKind", "NotAllowedDetailKind",
    "NotFoundDetailKind", "AlreadyExistsDetailKind", "ConnectionDetailKind",
    # Legacy
    "SurrealDBMethodError",
    # CBOR tag constants
    "TAG_BOUND_EXCLUDED", "TAG_BOUND_INCLUDED", "TAG_DATETIME", "TAG_DATETIME_COMPACT",
    "TAG_DECIMAL_STRING", "TAG_DURATION", "TAG_DURATION_COMPACT",
    "TAG_GEOMETRY_COLLECTION", "TAG_GEOMETRY_LINE", "TAG_GEOMETRY_MULTI_LINE",
    "TAG_GEOMETRY_MULTI_POINT", "TAG_GEOMETRY_MULTI_POLYGON", "TAG_GEOMETRY_POINT",
    "TAG_GEOMETRY_POLYGON", "TAG_NONE", "TAG_RANGE", "TAG_RECORD_ID",
    "TAG_TABLE_NAME", "TAG_UUID_STRING",
]
```

---

## 14. SurrealDB Database Features

### Multi-Model Support
- **Document store** — schemaless JSON-like records
- **Graph database** — RELATE statement, bi-directional edges, recursive traversal, Graph RAG
- **Relational** — traditional SQL-like queries, JOINs, foreign keys via record links
- **Vector database** — HNSW indexing, euclidean/cosine/manhattan distances, hybrid search
- **Key-value** — simple record lookup by ID
- **Time-series** — versioned temporal tables (experimental)

### Schema Options
- **Schemaless** — flexible, no enforcement
- **Schemafull** — strict field types and constraints per table
- Mix per table; nested field support with default values

### Storage & Scalability
- **In-memory** — high-performance caching with full transactional support
- **Embedded** — direct in-process execution (Python, JS, WASM, mobile, edge, browser)
- **Single node** — persistent on-disk for development and edge
- **Distributed** — storage-compute separation, horizontal scaling
- Automatic data sharding, partition-free tables
- Read replicas, multi-region replication

### Indexing
- Unique indexes, compound indexes (multi-field including nested), flattened array indexes
- Full-text indexing (BM25 ranking, relevance scoring, highlighting)
- Vector embedding indexing (HNSW, euclidean/cosine/manhattan distances)
- Hybrid search (full-text + vector via reciprocal rank fusion)
- Non-blocking background index creation, concurrent cluster-wide construction
- Aggregate indexed views (pre-computed analytics with windowing)
- Count indexes (pre-computed record counts)
- **Planned:** partial indexes, expression indexes, graph indexes, geospatial indexes, record link indexes

### Security & Auth
- RBAC with granular permissions and inheritance
- Field-level, table-level, record-level access control
- Namespace/database-level access separation
- Root access with IP restrictions
- OAuth/JWT support: ES256/384/512, HS256/384/512, PS256/384/512, RS256/384/512
- TLS in transit, encryption at rest
- Field-level encryption with client-side key management (future)
- Multi-tenant isolation with separate compute and storage
- Database audit logs, cloud audit logs with SIEM integration (future)

### Real-Time
- WebSocket protocol for bi-directional communication
- Live queries (`LIVE SELECT`) with real-time notifications
- Table events (triggers on record modifications)
- Asynchronous non-blocking background events

### Geospatial
- Full GeoJSON type support (Point, Line, Polygon, Multi*, Collection)
- Geo operators: `OUTSIDE`, `INTERSECTS`
- Geo functions: `geo::area`, `geo::bearing`, `geo::centroid`, `geo::distance`, `geo::hash::decode`, `geo::hash::encode`, `geo::is_valid`

### File Storage (Buckets)
- Bucket types: in-memory, file-system (allowlisted paths), object storage (S3/GCS/Azure)
- Global buckets shared across namespaces/databases
- Operations: put, get, head, delete, copy, rename, exists, list
- Fine-grained bucket permissions per operation

### ML Integration (SurrealML)
- Custom model training (PyTorch, TensorFlow, Sklearn)
- `.surml` model format, versioned model storage (local/S3/GCS/Azure)
- ONNX-backed Rust-native inference (CPU/GPU)
- Python inference for consistent computation

### AI Agent Support
- Model Context Protocol (MCP) — connect AI tools like Cursor, VS Code, Claude
- RAG and Graph RAG (vector + graph traversal)
- LangChain integration for vector search and LLM compatibility
- Unified agent memory (structured + unstructured + vectors + graphs)
- Real-time agent reactivity via live queries and event-driven responses
- AI model integration with LLM/embedding model calls via WebAssembly
- Agent governance with permissions, access control, audit trails
- Prompt-response session storage for conversation history

### Deployment Options
- Embedded (in-app), single-node, distributed cluster
- Cloud-managed (SurrealDB Cloud)
- Edge and mobile deployments

### Connectivity / Protocols
- REST API (key-value and SurrealQL querying)
- HTTP protocol (text and binary support)
- WebSocket protocol (bi-directional real-time)

---

## 15. SurrealQL Statements

### Database Resource Statements
| Statement | Description |
|---|---|
| `DEFINE` | Creates database resources (tables, fields, indexes, functions, etc.) |
| `ALTER` | Modifies existing resources |
| `REMOVE` | Deletes database resources |
| `REBUILD` | Reconstructs an index |
| `ACCESS` | Manages access grants and permissions |
| `USE` | Switches between namespaces or databases |
| `INFO` | Displays definitions of existing resources |
| `SHOW` | Views changefeeds for tables or databases |

### Query / CRUD Statements
| Statement | Description |
|---|---|
| `CREATE` | Generates new records across multiple tables |
| `INSERT` | Adds records or graph edges |
| `RELATE` | Creates a single directed edge between records |
| `UPDATE` | Modifies existing records |
| `UPSERT` | Updates or creates records as needed |
| `SELECT` | Retrieves records and values |
| `LIVE SELECT` | Streams real-time table changes |
| `DELETE` | Removes records |
| `KILL` | Cancels a LIVE SELECT operation |
| `LET` | Assigns values to parameters for reuse |

### Control Flow Statements
| Statement | Description |
|---|---|
| `BEGIN` | Initiates a manual transaction |
| `COMMIT` | Finalizes a transaction |
| `CANCEL` | Aborts a transaction |
| `FOR` | Starts a loop structure |
| `CONTINUE` | Advances to the next loop iteration |
| `BREAK` | Exits a loop or function |
| `IF/ELSE` | Conditional execution |
| `SLEEP` | Pauses execution temporarily |
| `RETURN` | Exits and optionally returns a value |
| `THROW` | Terminates with an error message |

---

## 16. SurrealQL Operators

### Logical
| Operator | Description |
|---|---|
| `&&` / `AND` | Both values truthy |
| `\|\|` / `OR` | Either value truthy |
| `!` | NOT (reverse truthiness) |
| `!!` | Double NOT (determine if truthy) |
| `??` | Null coalescing (first non-NULL truthy) |
| `?:` | Truthy coalescing (first truthy) |

### Comparison
| Operator | Description |
|---|---|
| `=` / `IS` | Equal |
| `!=` / `IS NOT` | Not equal |
| `==` | Exact equal (type-strict) |
| `?=` | Any value in set equals |
| `*=` | All values in set equal |
| `<`, `<=`, `>`, `>=` | Magnitude comparisons |

### Arithmetic
| Operator | Description |
|---|---|
| `+` | Addition (numeric or string concat) |
| `-` | Subtraction |
| `*` / `x` | Multiplication |
| `/` / `div` | Division |
| `**` | Exponentiation |

### Containment
| Operator | Description |
|---|---|
| `CONTAINS` / `∋` | Value includes another |
| `CONTAINSNOT` / `∌` | Value does not include |
| `CONTAINSALL` / `⊇` | Contains all specified |
| `CONTAINSANY` / `⊃` | Contains at least one |
| `CONTAINSNONE` / `⊅` | Contains none |

### Membership
| Operator | Description |
|---|---|
| `INSIDE` / `IN` / `∈` | Value contained within |
| `NOTINSIDE` / `NOT IN` / `∉` | Value not contained |
| `ALLINSIDE` / `⊆` | All values inside |
| `ANYINSIDE` / `⊂` | Any value inside |
| `NONEINSIDE` / `⊄` | None inside |

### Geometric
| Operator | Description |
|---|---|
| `OUTSIDE` | Geometry external to another |
| `INTERSECTS` | Geometry intersects another |

### Search
| Operator | Description |
|---|---|
| `@@` / `@[ref]@` | Full-text match against indexed field |
| `<\|K,METRIC\|>` | K-Nearest Neighbors search |

---

## 17. SurrealQL Built-in Functions (~340+ total)

### Array Functions (56)
`array::add`, `array::all`, `array::any`, `array::at`, `array::append`, `array::boolean_and`, `array::boolean_or`, `array::boolean_xor`, `array::boolean_not`, `array::combine`, `array::complement`, `array::clump`, `array::concat`, `array::difference`, `array::distinct`, `array::fill`, `array::filter`, `array::filter_index`, `array::find`, `array::find_index`, `array::first`, `array::flatten`, `array::fold`, `array::group`, `array::insert`, `array::intersect`, `array::is_empty`, `array::join`, `array::last`, `array::len`, `array::logical_and`, `array::logical_or`, `array::logical_xor`, `array::map`, `array::max`, `array::matches`, `array::min`, `array::pop`, `array::prepend`, `array::push`, `array::range`, `array::reduce`, `array::remove`, `array::repeat`, `array::reverse`, `array::sequence`, `array::shuffle`, `array::slice`, `array::sort`, `array::sort_lexical`, `array::sort_natural`, `array::sort_natural_lexical`, `array::sort::asc`, `array::sort::desc`, `array::swap`, `array::transpose`, `array::union`, `array::windows`

### String Functions (57)
**Core:** `string::capitalize`, `string::concat`, `string::contains`, `string::ends_with`, `string::join`, `string::len`, `string::lowercase`, `string::matches`, `string::repeat`, `string::replace`, `string::reverse`, `string::slice`, `string::slug`, `string::split`, `string::starts_with`, `string::trim`, `string::uppercase`, `string::words`
**Distance:** `string::distance::damerau_levenshtein`, `string::distance::normalized_damerau_levenshtein`, `string::distance::hamming`, `string::distance::levenshtein`, `string::distance::normalized_levenshtein`, `string::distance::osa`
**HTML:** `string::html::encode`, `string::html::sanitize`
**Validation:** `string::is_alphanum`, `string::is_alpha`, `string::is_ascii`, `string::is_datetime`, `string::is_domain`, `string::is_email`, `string::is_hexadecimal`, `string::is_ip`, `string::is_ipv4`, `string::is_ipv6`, `string::is_latitude`, `string::is_longitude`, `string::is_numeric`, `string::is_record`, `string::is_semver`, `string::is_ulid`, `string::is_url`, `string::is_uuid`
**Semver:** `string::semver::compare`, `string::semver::major`, `string::semver::minor`, `string::semver::patch`, `string::semver::inc::major/minor/patch`, `string::semver::set::major/minor/patch`
**Similarity:** `string::similarity::fuzzy`, `string::similarity::jaro`, `string::similarity::jaro_winkler`

### Math Functions (~63 + 21 constants)
**Functions:** `math::abs`, `math::acos`, `math::acot`, `math::asin`, `math::atan`, `math::bottom`, `math::ceil`, `math::clamp`, `math::cos`, `math::cot`, `math::deg2rad`, `math::fixed`, `math::floor`, `math::interquartile`, `math::lerp`, `math::lerpangle`, `math::ln`, `math::log`, `math::log10`, `math::log2`, `math::max`, `math::mean`, `math::median`, `math::midhinge`, `math::min`, `math::mode`, `math::nearestrank`, `math::percentile`, `math::pow`, `math::product`, `math::rad2deg`, `math::round`, `math::sign`, `math::sin`, `math::spread`, `math::sqrt`, `math::stddev`, `math::sum`, `math::tan`, `math::top`, `math::trimean`, `math::variance`
**Constants:** `math::e`, `math::pi`, `math::tau`, `math::inf`, `math::neg_inf`, `math::frac_1_pi`, `math::frac_1_sqrt_2`, `math::frac_2_pi`, `math::frac_2_sqrt_pi`, `math::frac_pi_2/3/4/6/8`, `math::ln_10`, `math::ln_2`, `math::log10_2`, `math::log10_e`, `math::log2_10`, `math::log2_e`, `math::sqrt_2`

### Time Functions (39 + 3 constants)
`time::ceil`, `time::day`, `time::floor`, `time::format`, `time::group`, `time::hour`, `time::max`, `time::micros`, `time::millis`, `time::min`, `time::minute`, `time::month`, `time::nano`, `time::now`, `time::round`, `time::second`, `time::timezone`, `time::unix`, `time::wday`, `time::week`, `time::yday`, `time::year`, `time::is_leap_year`, `time::from_micros/millis/nanos/secs/unix/ulid/uuid`, `time::set_year/month/day/hour/minute/second/nanosecond`
**Constants:** `time::epoch`, `time::maximum`, `time::minimum`

### Type Functions (44)
**Conversion:** `type::array`, `type::bool`, `type::bytes`, `type::datetime`, `type::decimal`, `type::duration`, `type::field`, `type::fields`, `type::file`, `type::float`, `type::int`, `type::number`, `type::point`, `type::range`, `type::record`, `type::string`, `type::string_lossy`, `type::table`, `type::uuid`
**Type checking:** `type::of`, `type::is_array/bool/bytes/collection/datetime/decimal/duration/float/geometry/int/line/none/null/multiline/multipoint/multipolygon/number/object/point/polygon/range/record/string/uuid`

### Crypto Functions (14)
**Hashing:** `crypto::blake3`, `crypto::joaat`, `crypto::md5`, `crypto::sha1`, `crypto::sha256`, `crypto::sha512`
**Password:** `crypto::argon2::generate/compare`, `crypto::bcrypt::generate/compare`, `crypto::pbkdf2::generate/compare`, `crypto::scrypt::generate/compare`

### Vector Functions (20)
**Operations:** `vector::add`, `vector::angle`, `vector::cross`, `vector::divide`, `vector::dot`, `vector::magnitude`, `vector::multiply`, `vector::normalize`, `vector::project`, `vector::scale`, `vector::subtract`
**Distance:** `vector::distance::chebyshev/euclidean/hamming/knn/manhattan/minkowski`
**Similarity:** `vector::similarity::cosine/jaccard/pearson`

### Duration Functions (17 + 1 constant)
**From numeric:** `duration::from_days/hours/micros/millis/mins/nanos/secs/weeks`
**Extract numeric:** `duration::days/hours/micros/millis/mins/nanos/secs/weeks/years`
**Constant:** `duration::max`

### Geo Functions (7)
`geo::area`, `geo::bearing`, `geo::centroid`, `geo::distance`, `geo::hash::decode`, `geo::hash::encode`, `geo::is_valid`

### HTTP Functions (6)
`http::head`, `http::get`, `http::put`, `http::post`, `http::patch`, `http::delete`

### Record Functions (5)
`record::exists`, `record::id`, `record::tb`, `record::refs`, `record::is_edge`

### Object Functions (8)
`object::entries`, `object::extend`, `object::from_entries`, `object::is_empty`, `object::keys`, `object::len`, `object::remove`, `object::values`

### Rand Functions (12)
`rand()`, `rand::bool`, `rand::duration`, `rand::enum`, `rand::float`, `rand::id`, `rand::int`, `rand::string`, `rand::time`, `rand::uuid` (v7), `rand::uuid::v4`, `rand::ulid`

### Parse Functions (9)
**Email:** `parse::email::host`, `parse::email::user`
**URL:** `parse::url::domain/fragment/host/path/port/scheme/query`

### Session Functions (8)
`session::ac`, `session::db`, `session::id`, `session::ip`, `session::ns`, `session::origin`, `session::rd`, `session::token`

### Search Functions (6)
`search::analyze`, `search::highlight`, `search::linear`, `search::offsets`, `search::rrf`, `search::score`

### Encoding Functions (4)
`encoding::base64::encode/decode`, `encoding::cbor::encode/decode`

### Set Functions (9)
`set::add`, `set::complement`, `set::contains`, `set::difference`, `set::intersect`, `set::is_empty`, `set::len`, `set::remove`, `set::union`

### File Functions (13)
`file::bucket`, `file::copy`, `file::copy_if_not_exists`, `file::delete`, `file::exists`, `file::get`, `file::head`, `file::key`, `file::list`, `file::put`, `file::put_if_not_exists`, `file::rename`, `file::rename_if_not_exists`

### Value Functions (3)
`.chain()`, `value::diff`, `value::patch`

### Standalone Functions
`count()`, `not()`, `sleep()`, `sequence::next()`, `bytes::len()`

---

## 18. SurrealQL Data Model Types

### Primitive Types
| Type | Description |
|---|---|
| `any` | Accepts any supported data type |
| `bool` | Truthy/falsy values |
| `string` | Text values |
| `int` | 64-bit signed integers |
| `float` | Floating point numbers |
| `decimal` | High-precision decimal |
| `number` | Auto-detected numeric type with minimal byte storage |

### Temporal Types
| Type | Description |
|---|---|
| `datetime` | RFC 3339 compliant with time zone, UTC conversion |
| `duration` | Time length, nanosecond to week range, arithmetic support |

### Collection Types
| Type | Description |
|---|---|
| `array` | Ordered, optional element type/length: `array<string, 10>` |
| `set` | Auto-deduplicated, ordered collection |
| `object` | Key-value with unlimited nesting |

### Specialized Types
| Type | Description |
|---|---|
| `bytes` | Byte array storage |
| `geometry` | GeoJSON (RFC 7946): point, line, polygon, multi*, collection |
| `regex` | Compiled regular expressions |
| `record` | Record references with optional table restriction: `record<user>` |
| `range` | Value spans with optional bounds: `0..10`, `'a'..'z'` |

### Modifier Types
| Type | Description |
|---|---|
| `option<type>` | Optional fields (stores NONE or specified type) |
| `literal` | Union-like: `"a" \| "b"` |

---

## 19. Observability

Pydantic Logfire integration for automatic OpenTelemetry tracing:

```python
import logfire
logfire.configure()
logfire.instrument_surrealdb()
# All operations automatically traced as OTel spans
```

Features: automatic tracing, sensitive data scrubbing. Compatible with Jaeger, DataDog, Honeycomb.

---

## 20. Framework Examples

The SDK ships examples for: FastAPI, Django, Flask, Litestar, Starlette, Sanic, Quart, GraphQL (with subscriptions), Jupyter, FastMCP (MCP server), Logfire, Embedded.

---

## 21. Version History

| Version | Date | Highlights |
|---|---|---|
| `2.0.0-alpha.1` | 2026-02-25 | SurrealDB 3.x protocol, structured error hierarchy, Logfire observability, dropped Python 3.9 |
| `1.0.8` | 2026-01-07 | Pydantic extra for RecordID, switched from cerberus to pydantic-core |
| `1.0.7` | 2025-12-03 | Embedded DB support, compound duration parsing, framework examples, pyright |
| `1.0.6` | 2025-07-21 | Switched to uv project management |
| `1.0.0` | 2025-01-30 | Initial stable release |

---

## Quick Reference

| Task | API |
|---|---|
| Connect (WebSocket) | `Surreal("ws://localhost:8000/rpc")` |
| Connect (HTTP) | `Surreal("http://localhost:8000")` |
| Connect (embedded memory) | `Surreal("memory")` |
| Connect (embedded file) | `Surreal("file://path")` |
| Sign in (root) | `db.signin({"username": "root", "password": "root"})` |
| Switch ns/db | `db.use("namespace", "database")` |
| Create record | `db.create("table", {"key": "value"})` |
| Create with ID | `db.create(RecordID("table", "id"), data)` |
| Select all | `db.select("table")` |
| Select one | `db.select(RecordID("table", "id"))` |
| Update (replace) | `db.update("table:id", data)` |
| Merge (partial) | `db.merge("table:id", partial_data)` |
| Patch (JSON Patch) | `db.patch("table:id", [ops])` |
| Bulk insert | `db.insert("table", [records])` |
| Graph edge | `db.insert_relation("edge", {"in": "a:1", "out": "b:2"})` |
| Delete | `db.delete("table:id")` |
| Raw query | `db.query("SELECT * FROM table WHERE x = $val", {"val": 1})` |
| Live query | `uuid = db.live("table")` |
| Subscribe | `for n in db.subscribe_live(uuid): ...` |
| Transaction | `txn = await session.begin_transaction()` |
| Server version | `db.version()` |
