# Kreuzberg Capabilities Reference

> Deep analysis of kreuzberg v4.3.8 for building the Haystack converter component.
> Updated: 2026-03-04 | Latest PyPI: v4.4.2 | Local source: v4.4.1
> Source: `/home/v-tan/Code/kreuzberg/packages/python/kreuzberg`
> LangChain integration reference: `/home/v-tan/Code/langchain-kreuzberg`

---

## 1. Architecture Overview

Kreuzberg is a **Rust-core document intelligence library** with a thin Python wrapper. The Rust core handles all extraction logic (via PyO3 bindings); Python exclusively manages:
- Custom OCR backend plugins (e.g., EasyOCR)
- Custom postprocessor plugins
- Async orchestration (backed by Rust's tokio)

**Key facts:**
- Version: 4.3.8 | Python 3.10+ | MIT license
- 75+ supported file formats
- True async support (Rust tokio + rayon for parallelism)
- Native chunking and keyword extraction in Rust

---

## 2. Public API Surface

### 2.1 Core Extraction Functions

```python
# Synchronous
extract_file_sync(
    file_path: str | Path,
    mime_type: str | None = None,
    config: ExtractionConfig | None = None,
    *,
    easyocr_kwargs: dict[str, Any] | None = None,
) -> ExtractionResult

extract_bytes_sync(
    data: bytes | bytearray,
    mime_type: str,                    # REQUIRED for bytes input
    config: ExtractionConfig | None = None,
    *,
    easyocr_kwargs: dict[str, Any] | None = None,
) -> ExtractionResult

batch_extract_files_sync(
    paths: list[str | Path],
    config: ExtractionConfig | None = None,
    *,
    easyocr_kwargs: dict[str, Any] | None = None,
) -> list[ExtractionResult]

batch_extract_bytes_sync(
    data_list: list[bytes | bytearray],
    mime_types: list[str],             # Parallel list, 1:1 with data_list
    config: ExtractionConfig | None = None,
    *,
    easyocr_kwargs: dict[str, Any] | None = None,
) -> list[ExtractionResult]

# Async (same signatures, add `async def`)
extract_file(...)
extract_bytes(...)
batch_extract_files(...)
batch_extract_bytes(...)
```

**Input type matrix:**

| Input | Function | MIME Type Required? |
|---|---|---|
| File path | `extract_file_sync/async` | No (auto-detected) |
| Raw bytes | `extract_bytes_sync/async` | **Yes** |
| Multiple files | `batch_extract_files_sync/async` | No |
| Multiple bytes | `batch_extract_bytes_sync/async` | **Yes (parallel list)** |

### 2.2 MIME Type Detection

```python
detect_mime_type(data: bytes | bytearray) -> str          # Python wrapper, magic-number detection
detect_mime_type_from_bytes(data: bytes) -> str            # Direct Rust binding, same functionality
detect_mime_type_from_path(path: str | Path) -> str        # reads file, detects type
```

Use these to satisfy the `mime_type` requirement when passing `ByteStream` to kreuzberg.

### 2.3 Configuration I/O

```python
# Class methods (modern API)
ExtractionConfig.from_file(path: str | Path) -> ExtractionConfig   # .toml/.yaml/.json
ExtractionConfig.discover() -> ExtractionConfig                     # search cwd + parents

# Standalone functions
load_extraction_config_from_file(path: str | Path) -> ExtractionConfig  # .toml/.yaml/.json
config_to_json(config: ExtractionConfig) -> str
config_get_field(config: ExtractionConfig, field_name: str) -> Any | None
config_merge(base: ExtractionConfig, override: ExtractionConfig) -> None
```

### 2.4 Plugin Registration

```python
register_ocr_backend(backend: Any) -> None
register_post_processor(processor: Any) -> None
register_validator(validator: Any) -> None

# Unregistration
unregister_document_extractor(name: str) -> None
unregister_ocr_backend(name: str) -> None
unregister_post_processor(name: str) -> None
unregister_validator(name: str) -> None

# Clear all
clear_document_extractors() -> None
clear_ocr_backends() -> None
clear_post_processors() -> None
clear_validators() -> None

# Introspection
list_document_extractors() -> list[str]
list_ocr_backends() -> list[str]
list_post_processors() -> list[str]
list_validators() -> list[str]
```

### 2.5 Error Diagnostics

```python
get_last_error_code() -> int | None       # returns ErrorCode int (0–7)
get_error_details() -> dict[str, Any]     # message, code, type, source, line, context
classify_error(message: str) -> int
error_code_name(code: int) -> str
get_last_panic_context() -> str | None    # JSON from Rust panic
```

### 2.6 Validation Helpers

```python
validate_mime_type(mime_type: str) -> str
validate_ocr_backend(backend: str) -> bool
validate_language_code(code: str) -> bool
validate_output_format(output_format: str) -> bool
validate_binarization_method(method: str) -> bool
validate_confidence(confidence: float) -> bool
validate_dpi(dpi: int) -> bool
validate_chunking_params(max_chars: int, max_overlap: int) -> bool
validate_tesseract_psm(psm: int) -> bool
validate_tesseract_oem(oem: int) -> bool
validate_token_reduction_level(level: str) -> bool
```

### 2.7 Enumeration Helpers

```python
get_extensions_for_mime(mime_type: str) -> list[str]
get_valid_binarization_methods() -> list[str]
get_valid_language_codes() -> list[str]
get_valid_ocr_backends() -> list[str]
get_valid_token_reduction_levels() -> list[str]
list_embedding_presets() -> list[str]
get_embedding_preset(name: str) -> EmbeddingPreset | None
```

---

## 3. Supported File Formats

**Documents:** PDF, DOCX, DOC, XLSX, XLS, PPTX, PPT, PPSX, PPTM, ODT, ODS, ODP, RTF, FB2, DocBook
**Text/Markup:** TXT, MD, MDX, RST, JSON, YAML, TOML, HTML, XML, LaTeX, Typst, BibTeX, Jupyter (.ipynb)
**Email:** EML, MSG (with attachment extraction)
**eBooks:** EPUB
**Archives:** ZIP, RAR, 7Z, TAR, GZIP (extracts + processes contents recursively)
**Images (via OCR):** PNG, JPEG, JPEG 2000, TIFF, GIF, BMP, WEBP, SVG
**Data:** CSV

---

## 4. Configuration Classes

### 4.1 ExtractionConfig (top-level)

```python
class ExtractionConfig:
    use_cache: bool = True
    enable_quality_processing: bool = True
    force_ocr: bool = False
    result_format: str = "unified"           # or "element_based" (Unstructured-compatible)
    output_format: str = "plain"             # or "markdown", "djot", "html", "structured"
    include_document_structure: bool = False  # hierarchical tree output
    max_concurrent_extractions: int | None = None

    # Sub-configs (all optional)
    ocr: OcrConfig | None = None
    chunking: ChunkingConfig | None = None
    images: ImageExtractionConfig | None = None
    pdf_options: PdfConfig | None = None
    token_reduction: TokenReductionConfig | None = None
    language_detection: LanguageDetectionConfig | None = None
    keywords: KeywordConfig | None = None
    postprocessor: PostProcessorConfig | None = None
    html_options: HtmlConversionOptions | None = None    # NOTE: not exported as a class
    pages: PageConfig | None = None

    # Class methods
    @classmethod
    def from_file(cls, path: str | Path) -> ExtractionConfig   # load from .toml/.yaml/.json
    @classmethod
    def discover(cls) -> ExtractionConfig                       # search cwd + parents for config
```

**OutputFormat enum** (can be used instead of string literals):

```python
class OutputFormat(Enum):
    PLAIN = "plain"
    MARKDOWN = "markdown"
    DJOT = "djot"
    HTML = "html"
    STRUCTURED = "structured"    # new in 4.4.x
```

**ResultFormat enum**:

```python
class ResultFormat(Enum):
    UNIFIED = "unified"
    ELEMENT_BASED = "element_based"
```

### 4.2 OcrConfig

```python
class OcrConfig:
    backend: str = "tesseract"              # "tesseract" | "easyocr" | "paddleocr"
    language: str = "eng"                   # ISO 639-3, e.g. "eng+fra+deu"
    tesseract_config: TesseractConfig | None = None
    # NOTE: paddle_ocr_config and element_config do NOT exist on this class
    # despite being documented in some older references
```

### 4.3 TesseractConfig

```python
class TesseractConfig:
    language: str = "eng"
    psm: int = 3                            # Page segmentation mode (0–13)
    oem: int = 3                            # OCR engine mode (0–3)
    output_format: str = "markdown"
    min_confidence: float = 0.0
    enable_table_detection: bool = True
    table_min_confidence: float = 0.0
    table_column_threshold: int = 50
    table_row_threshold_ratio: float = 0.5
    use_cache: bool = True
    preprocessing: ImagePreprocessingConfig | None = None
    tessedit_char_whitelist: str = ""
    tessedit_char_blacklist: str = ""
    # Additional low-level tesseract flags:
    classify_use_pre_adapted_templates: bool = True
    language_model_ngram_on: bool = False
    tessedit_dont_blkrej_good_wds: bool = True
    tessedit_dont_rowrej_good_wds: bool = True
    tessedit_enable_dict_correction: bool = True
    tessedit_use_primary_params_model: bool = True
    textord_space_size_is_variable: bool = True
    thresholding_method: bool = False
```

### 4.4 ImagePreprocessingConfig (for OCR pipeline)

```python
class ImagePreprocessingConfig:
    target_dpi: int = 300
    auto_rotate: bool = True
    deskew: bool = True
    denoise: bool = False
    contrast_enhance: bool = False
    binarization_method: str = "otsu"
    invert_colors: bool = False
```

### 4.5 PaddleOcrConfig

> **NOTE**: `PaddleOcrConfig` is NOT exported from kreuzberg's Python package as of v4.3.8.
> PaddleOCR is configured via `OcrConfig(backend="paddleocr")` only.
> The class below is from documentation only and cannot be instantiated directly.

```python
# NOT AVAILABLE as a Python export — for reference only
class PaddleOcrConfig:
    language: str | None = None
    cache_dir: str | None = None
    use_angle_cls: bool | None = None
    enable_table_detection: bool | None = None
    det_db_thresh: float | None = None
    det_db_box_thresh: float | None = None
    det_db_unclip_ratio: float | None = None
    det_limit_side_len: int | None = None
    rec_batch_num: int | None = None
```

### 4.6 ChunkingConfig

```python
class ChunkingConfig:
    max_chars: int = 1000
    max_overlap: int = 200
    embedding: EmbeddingConfig | None = None   # optional embeddings per chunk
    preset: str | None = None                  # "balanced" | "compact" | "large"
```

### 4.7 EmbeddingConfig & EmbeddingModelType

```python
class EmbeddingConfig:
    # Constructor requires `model` parameter, but it's not accessible as an attribute
    # Accessible attributes:
    normalize: bool = True
    batch_size: int = 32
    # NOTE: show_download_progress and cache_dir are NOT accessible as attributes

class EmbeddingModelType:
    @staticmethod
    def preset(name: str) -> EmbeddingModelType  # "balanced" | "compact" | "large"
    @staticmethod
    def fastembed(model: str, dimensions: int) -> EmbeddingModelType
    @staticmethod
    def custom(model_id: str, dimensions: int) -> EmbeddingModelType
```

### 4.8 ImageExtractionConfig (extract images FROM documents)

```python
class ImageExtractionConfig:
    extract_images: bool = True
    target_dpi: int = 300
    max_image_dimension: int = 4096
    auto_adjust_dpi: bool = True
    min_dpi: int = 72
    max_dpi: int = 600
```

### 4.9 PdfConfig

```python
class PdfConfig:
    extract_images: bool = False
    passwords: list[str] | None = None       # try each password for encrypted PDFs
    extract_metadata: bool = True
    extract_annotations: bool = False        # NOTE: default is False, not None
    hierarchy: HierarchyConfig | None = None
    top_margin_fraction: float | None = None
    bottom_margin_fraction: float | None = None
```

### 4.10 HierarchyConfig

```python
class HierarchyConfig:
    enabled: bool = True
    k_clusters: int = 6
    include_bbox: bool = True
    ocr_coverage_threshold: float | None = None
```

### 4.11 PageConfig

```python
class PageConfig:
    extract_pages: bool = False              # if True: result.pages is populated
    insert_page_markers: bool = False        # inserts markers in content string
    marker_format: str = "\n\n<!-- PAGE {page_num} -->\n\n"
```

### 4.12 LanguageDetectionConfig

```python
class LanguageDetectionConfig:
    enabled: bool = True
    min_confidence: float = 0.8
    detect_multiple: bool = False
```

### 4.13 KeywordConfig

```python
class KeywordConfig:
    algorithm: KeywordAlgorithm             # KeywordAlgorithm.Yake | .Rake
    max_keywords: int = 10
    min_score: float = 0.0
    ngram_range: tuple[int, int] = (1, 3)
    language: str | None = "en"
    yake_params: YakeParams | None = None   # window_size: int = 2
    rake_params: RakeParams | None = None   # min_word_length, max_words_per_phrase
```

### 4.14 TokenReductionConfig

```python
class TokenReductionConfig:
    mode: Literal["off", "light", "moderate", "aggressive", "maximum"] = "off"
    preserve_important_words: bool = True
```

### 4.15 PostProcessorConfig

```python
class PostProcessorConfig:
    enabled: bool = True
    enabled_processors: list[str] | None = None
    disabled_processors: list[str] | None = None
```

### 4.16 OcrElementConfig

> **NOTE**: `OcrElementConfig` is NOT exported from kreuzberg's Python package as of v4.3.8.
> It exists in the Rust core but is not exposed through PyO3 bindings.

```python
# NOT AVAILABLE as a Python export — for reference only
class OcrElementConfig:
    include_elements: bool = False
    min_level: str | None = None
    min_confidence: float | None = None
    build_hierarchy: bool = False
```

---

## 5. ExtractionResult Structure

```python
class ExtractionResult:
    content: str                               # Main extracted text
    mime_type: str
    metadata: Metadata                         # Rich TypedDict (see §6)
    tables: list[ExtractedTable]               # Always present (may be empty)
    processing_warnings: list[ProcessingWarning]

    # Optional fields (None unless configured)
    detected_languages: list[str] | None       # Requires LanguageDetectionConfig
    chunks: list[Chunk] | None                 # Requires ChunkingConfig
    images: list[ExtractedImage] | None        # Requires ImageExtractionConfig
    pages: list[PageContent] | None            # Requires PageConfig(extract_pages=True)
    elements: list[Element] | None             # result_format="element_based"
    document: DocumentStructure | None         # include_document_structure=True
    ocr_elements: list[OcrElement] | None
    djot_content: DjotContent | None           # output_format="djot"
    output_format: str | None
    result_format: str | None
    extracted_keywords: list[ExtractedKeyword] | None   # Requires KeywordConfig
    quality_score: float | None                # Requires enable_quality_processing=True
    annotations: list[PdfAnnotation] | None   # PDF annotations (PdfConfig)

    # Convenience methods
    def get_page_count(self) -> int
    def get_chunk_count(self) -> int
    def get_detected_language(self) -> str | None
    def get_metadata_field(self, field_name: str) -> Any | None
```

### 5.1 ExtractedTable

```python
class ExtractedTable:
    cells: list[list[str]]    # 2D grid of strings
    markdown: str             # Formatted markdown table
    page_number: int          # 1-indexed
    bounding_box: BoundingBox | None
```

### 5.2 Chunk

```python
class Chunk:
    content: str
    embedding: list[float] | None     # populated when EmbeddingConfig present

class ChunkMetadata(TypedDict):
    byte_start: int
    byte_end: int
    chunk_index: int
    total_chunks: int
    token_count: int | None
    first_page: int
    last_page: int
```

### 5.3 PageContent (per-page)

```python
class PageContent(TypedDict):
    page_number: int          # 1-indexed
    content: str
    tables: list[ExtractedTable]
    images: list[ExtractedImage]
    is_blank: bool | None
```

### 5.4 ExtractedImage

```python
class ExtractedImage(TypedDict):
    data: bytes
    format: str               # "PNG", "JPEG", etc.
    image_index: int
    page_number: int
    width: int
    height: int
    colorspace: str
    bits_per_component: int
    is_mask: bool
    description: str
    bounding_box: BoundingBox | None
    ocr_result: ExtractionResult | None   # if OCR ran on this image
```

### 5.5 Element (Unstructured-compatible)

```python
class Element(TypedDict):
    element_id: str
    element_type: Literal[
        "title", "narrative_text", "heading", "list_item", "table",
        "image", "page_break", "code_block", "block_quote", "footer", "header"
    ]
    text: str
    metadata: ElementMetadata   # page_number, filename, coordinates, element_index
```

### 5.6 DocumentStructure (hierarchical tree)

```python
class DocumentStructure:
    nodes: list[DocumentNode]

class DocumentNode:
    id: str                    # deterministic hash-based ID
    content: NodeContent       # discriminated union on node_type
    parent: int | None         # index into nodes array
    children: list[int]
    content_layer: Literal["body", "header", "footer", "footnote"]
    page: int | None           # start page (1-indexed)
    page_end: int | None
    bbox: BoundingBox | None
    annotations: list[TextAnnotation]   # inline formatting

# NodeContent.node_type values:
# "title" | "heading" | "paragraph" | "list" | "list_item" | "table"
# "image" | "code" | "quote" | "formula" | "footnote" | "group" | "page_break"
```

### 5.7 ExtractedKeyword

```python
class ExtractedKeyword:
    text: str
    score: float
    algorithm: str            # "yake" or "rake"
    positions: list[int] | None
```

### 5.8 PdfAnnotation

```python
class PdfAnnotation:
    annotation_type: Literal["text", "highlight", "link", "stamp", "underline", "strike_out", "other"]
    content: str | None
    page_number: int
    bounding_box: BoundingBox | None
```

### 5.9 ProcessingWarning

```python
class ProcessingWarning:
    source: str
    message: str
```

---

## 6. Metadata Structure

`ExtractionResult.metadata` is a TypedDict discriminated by `format_type`.

### Common Fields (all formats)

```python
title: str | None
subject: str | None
authors: list[str] | None
keywords: list[str] | None
language: str | None
created_at: str | None         # ISO 8601
modified_at: str | None
created_by: str | None
modified_by: str | None
format_type: str               # discriminator field
```

### PDF-specific

```python
pdf_version: str | None
producer: str | None
is_encrypted: bool | None
width: float | None
height: float | None
page_count: int | None
```

### Excel-specific

```python
sheet_count: int | None
sheet_names: list[str] | None
```

### Email-specific

```python
from_email: str | None
from_name: str | None
to_emails: list[str] | None
cc_emails: list[str] | None
bcc_emails: list[str] | None
message_id: str | None
attachments: list[dict] | None
```

### PowerPoint-specific

```python
slide_count: int | None
slide_names: list[str] | None
```

### Archive-specific

```python
format: str | None
file_count: int | None
file_list: list[str] | None
total_size: int | None
compressed_size: int | None
```

### Image-specific

```python
width: int | None
height: int | None
format: str | None
exif: dict | None
```

### HTML-specific

```python
title: str | None
description: str | None
keywords: list[str] | None
author: str | None
canonical_url: str | None
base_href: str | None
language: str | None
text_direction: str | None
open_graph: dict | None
twitter_card: dict | None
meta_tags: dict | None
headers: list[dict] | None
links: list[dict] | None
images: list[dict] | None
structured_data: list[dict] | None
```

### Text-specific

```python
line_count: int | None
word_count: int | None
character_count: int | None
headers: list[str] | None
links: list[str] | None
code_blocks: list[str] | None
```

---

## 7. OCR Capabilities

### 7.1 Backends

| Backend | Type | Install | Language Count |
|---|---|---|---|
| `tesseract` | Native Rust | built-in | 100+ |
| `paddleocr` | Native Rust | built-in (Rust feature) | Many |
| `easyocr` | Python plugin | `pip install kreuzberg[easyocr]` | 80+ |

### 7.2 Tesseract PSM Reference

| PSM | Description |
|---|---|
| 0 | Orientation/script detection only |
| 3 | Fully automatic (default) |
| 6 | Uniform text block |
| 11 | Sparse text |

### 7.3 Tesseract OEM Reference

| OEM | Description |
|---|---|
| 0 | Legacy Tesseract only |
| 1 | LSTM only |
| 2 | Legacy + LSTM |
| 3 | Default (Tesseract decides) |

### 7.4 EasyOCR Backend

80+ supported language codes including: `en`, `de`, `fr`, `ar`, `zh_sim`, `zh_tra`, `ja`, `ko`, `ru`, `es`, `pt`, `it`, `nl`, `pl`, `tr`, `vi`, `th`, and many more.

```python
class EasyOCRBackend:
    def __init__(
        self,
        *,
        languages: list[str] | None = None,        # default: ["en"]
        use_gpu: bool | None = None,                # auto-detect CUDA
        model_storage_directory: str | None = None,
        beam_width: int = 5,
    ) -> None
```

---

## 8. Plugin Protocols

### 8.1 PostProcessorProtocol

```python
class PostProcessorProtocol(Protocol):
    def name(self) -> str: ...
    def process(self, result: ExtractionResult) -> ExtractionResult: ...
    def processing_stage(self) -> Literal["early", "middle", "late"]: ...
    def initialize(self) -> None: ...   # optional
    def shutdown(self) -> None: ...     # optional
```

### 8.2 OcrBackendProtocol

```python
class OcrBackendProtocol(Protocol):
    def name(self) -> str: ...
    def supported_languages(self) -> list[str]: ...
    def process_image(self, image_bytes: bytes, language: str) -> dict[str, Any]:
        # Returns: {"content": str, "metadata": dict, "tables": list[dict]}
        ...
    def process_file(self, path: str, language: str) -> dict[str, Any]: ...   # optional
    def initialize(self) -> None: ...
    def shutdown(self) -> None: ...
    def version(self) -> str: ...      # optional, defaults to "1.0.0"
```

### 8.3 ValidatorProtocol

```python
class ValidatorProtocol(Protocol):
    def name(self) -> str: ...
    def validate(self, result: ExtractionResult) -> None: ...  # raise to fail
    def priority(self) -> int: ...          # optional, default 50, higher = first
    def should_validate(self, result: ExtractionResult) -> bool: ...  # optional
    def initialize(self) -> None: ...
    def shutdown(self) -> None: ...
```

---

## 9. Error Handling

### 9.1 ErrorCode Enum

```python
class ErrorCode(IntEnum):
    SUCCESS = 0
    GENERIC_ERROR = 1
    PANIC = 2
    INVALID_ARGUMENT = 3
    IO_ERROR = 4
    PARSING_ERROR = 5
    OCR_ERROR = 6
    MISSING_DEPENDENCY = 7
```

### 9.2 Exception Hierarchy

```python
KreuzbergError(Exception)       # base; has .context: dict[str, Any]
├── ValidationError             # bad input arguments
├── ParsingError                # document parsing failed
├── OCRError                    # OCR processing failed
├── MissingDependencyError      # pip extra not installed
│       .create_for_package(dependency_group, functionality, package_name)
├── CacheError
├── ImageProcessingError
└── PluginError
```

### 9.3 PanicContext

```python
@dataclass(frozen=True, slots=True)
class PanicContext:
    file: str
    line: int
    function: str
    message: str
    timestamp_secs: int

    @classmethod
    def from_json(cls, json_str: str) -> PanicContext
```

---

## 10. Async / Sync Duality

All async functions are **true coroutines backed by Rust tokio** — not `asyncio.to_thread` wrappers. The batch async functions use Rust rayon for parallelism internally.

EasyOCR backend registration is automatic: if `config.ocr.backend == "easyocr"`, kreuzberg registers the Python EasyOCR backend transparently before calling into Rust.

---

## 11. Chunking & Embeddings

Native chunking is handled entirely in Rust with configurable:
- `max_chars` — maximum characters per chunk
- `max_overlap` — overlap between adjacent chunks
- Optional per-chunk embedding via FastEmbed-compatible models

Embedding presets (get via `get_embedding_preset(name)`):

```python
class EmbeddingPreset:
    name: str
    chunk_size: int
    overlap: int
    model_name: str
    dimensions: int
    description: str
```

Available preset names: `"balanced"`, `"compact"`, `"large"` (get full list via `list_embedding_presets()`).

---

## 12. LangChain Integration Reference

The LangChain integration (`langchain-kreuzberg`) is the primary design reference.

### 12.1 KreuzbergLoader API

```python
class KreuzbergLoader(BaseLoader):
    def __init__(
        self,
        *,
        file_path: str | Path | list[str | Path] | None = None,
        data: bytes | None = None,
        mime_type: str | None = None,      # required if data is provided
        glob: str | None = None,           # for directory globbing
        config: ExtractionConfig | None = None,
    ) -> None
```

Input modes:
- Single file: `file_path="doc.pdf"`
- Multiple files: `file_path=["a.pdf", "b.docx"]`
- Directory + glob: `file_path="./docs/", glob="**/*.pdf"`
- Raw bytes: `data=bytes_obj, mime_type="application/pdf"`

### 12.2 LangChain Metadata Mapping

The LangChain loader maps ExtractionResult to `Document.metadata`:

```python
{
    "source": "document.pdf",         # from file_path or "bytes"
    "mime_type": "application/pdf",

    # Flattened kreuzberg Metadata fields:
    "title": "...",
    "authors": ["..."],
    "created_at": "...",
    "language": "eng",
    "pdf_version": "1.7",
    "page_count": 10,
    # ... all other metadata fields

    # Extraction result fields:
    "quality_score": 0.95,
    "detected_languages": ["eng"],
    "output_format": "markdown",
    "table_count": 2,
    "tables": [                        # all ExtractedTable objects
        {
            "cells": [["H1", "H2"], ["V1", "V2"]],
            "markdown": "| H1 | H2 |\n...",
            "page_number": 1,
        }
    ],
    "extracted_keywords": [
        {"text": "python", "score": 0.95, "algorithm": "yake"},
    ],
    "processing_warnings": ["Low quality detected"],

    # Per-page mode only (PageConfig(extract_pages=True)):
    "page": 0,                         # 0-indexed (kreuzberg is 1-indexed)
    "is_blank": False,
}
```

### 12.3 Content Assembly

Tables are appended to page content (their markdown format):

```
Main extracted text...

| Header | Column |
|--------|--------|
| Cell1  | Cell2  |
```

### 12.4 Sync/Async Methods

```python
def load(self) -> list[Document]
def lazy_load(self) -> Iterator[Document]          # generator
async def aload(self) -> list[Document]
async def alazy_load(self) -> AsyncIterator[Document]   # async generator
```

---

## 13. Key Design Decisions for Haystack Converter

### 13.1 Input Handling

Haystack converters accept `sources: list[str | Path | ByteStream]`. The mapping to kreuzberg:

| Haystack Input | Kreuzberg API | Note |
|---|---|---|
| `str` / `Path` | `extract_file_sync` | MIME auto-detected |
| `ByteStream` | `extract_bytes_sync` | Must detect MIME from `ByteStream.data` or use `ByteStream.mime_type` |

For batch mode, prefer `batch_extract_files_sync` / `batch_extract_bytes_sync` for performance (Rust rayon parallelism).

### 13.2 ByteStream → kreuzberg

```python
# ByteStream has:
# .data: bytes
# .mime_type: str | None
# .meta: dict

stream = ByteStream(data=b"...", mime_type="application/pdf")

# Use ByteStream.mime_type if present, else call:
mime = detect_mime_type(stream.data)
result = extract_bytes_sync(stream.data, mime_type=mime, config=config)
```

### 13.3 ExtractionResult → Haystack Document

```python
from haystack.dataclasses import Document

doc = Document(
    content=result.content,
    meta={
        "mime_type": result.mime_type,
        **result.metadata,            # all extracted metadata fields

        # Tables serialized as dicts
        "tables": [
            {
                "cells": t.cells,
                "markdown": t.markdown,
                "page_number": t.page_number,
            }
            for t in result.tables
        ],

        # Optional enrichment
        "quality_score": result.quality_score,
        "detected_languages": result.detected_languages,
        "processing_warnings": [
            {"source": w.source, "message": w.message}
            for w in result.processing_warnings
        ],
    },
)
```

### 13.4 Per-Page Mode

When `PageConfig(extract_pages=True)`:
- `result.pages` is a `list[PageContent]`
- Yield one `Document` per `PageContent` with `meta["page"]` (1-indexed from kreuzberg)
- Each page's tables should be included in its content/meta

### 13.5 Configuration Passthrough

Expose `ExtractionConfig` as a constructor parameter (or individual sub-configs). Follow the pattern used in `PyPDFToDocument` — reasonable defaults, full configurability.

### 13.6 `store_full_path` Pattern

Follow PyPDFToDocument's `store_full_path` parameter to control whether `source` in metadata is a full absolute path or just the filename.

### 13.7 Async Support

Kreuzberg's async functions are native coroutines. The Haystack converter `run()` is synchronous; use `extract_file_sync` / `batch_extract_files_sync`. If Haystack adds async pipeline support later, async variants are ready to swap in.

---

## 14. Optional Extras

```toml
[optional-dependencies]
easyocr = [
    "easyocr>=1.7.2; python_version<'3.14'",
    "torch>=2.9.1; python_version<'3.14'",
]
all = ["kreuzberg[easyocr]"]
```

| Extra | Unlocks | Install |
|---|---|---|
| `easyocr` | EasyOCR Python OCR backend, GPU support | `pip install kreuzberg[easyocr]` |
| (none) | Tesseract + PaddleOCR (Rust-native) | `pip install kreuzberg` |

---

## 15. Deprecated Functions

```python
# DEPRECATED since 4.2.0 — use ExtractionConfig.from_file() or load_extraction_config_from_file()
discover_extraction_config() -> ExtractionConfig | None
# Modern replacement: ExtractionConfig.discover()
```

---

## Quick Reference

| Task | API |
|---|---|
| Extract file | `extract_file_sync(path, config=...)` |
| Extract bytes | `extract_bytes_sync(data, mime_type, config=...)` |
| Batch extract | `batch_extract_files_sync(paths, config=...)` |
| Detect MIME | `detect_mime_type(data)` |
| Build config | `ExtractionConfig(ocr=OcrConfig(...), chunking=ChunkingConfig(...))` |
| Per-page mode | `ExtractionConfig(pages=PageConfig(extract_pages=True))` |
| Markdown output | `ExtractionConfig(output_format="markdown")` |
| Enable OCR | `ExtractionConfig(ocr=OcrConfig(backend="tesseract", language="eng"))` |
| Force OCR | `ExtractionConfig(force_ocr=True)` |
| Native chunking | `ExtractionConfig(chunking=ChunkingConfig(max_chars=512, max_overlap=100))` |
| Keywords | `ExtractionConfig(keywords=KeywordConfig(algorithm=KeywordAlgorithm.Yake))` |
| Encrypted PDFs | `ExtractionConfig(pdf_options=PdfConfig(passwords=["secret"]))` |
| PDF annotations | `ExtractionConfig(pdf_options=PdfConfig(extract_annotations=True))` |
| Quality score | `ExtractionConfig(enable_quality_processing=True)` (default) |
| Token reduction | `ExtractionConfig(token_reduction=TokenReductionConfig(mode="moderate"))` |
| Structured output | `ExtractionConfig(include_document_structure=True)` |
| Unstructured compat | `ExtractionConfig(result_format="element_based")` |
| Load config file | `ExtractionConfig.from_file("kreuzberg.toml")` |
| Auto-discover config | `ExtractionConfig.discover()` |

---

## 16. Version History (v4.4.x Changes)

### v4.4.0 (2026-02-xx)

- **R, PHP async, Go FFI, C FFI bindings** (not relevant to Python API)
- **WASM native OCR and full-feature build**
- Many extraction quality fixes: DOCX equations, PPTX tables, EPUB, HTML metadata, SVG, RTF, etc.
- **PaddleOCR alias fix**: `backend="paddleocr"` now correctly resolves to `"paddle-ocr"`

### v4.4.1 (2026-02-28)

- **OCR table inlining into markdown content**: When `output_format="markdown"` and OCR detects tables, markdown pipe tables are inlined at correct vertical positions in `result.content`
- **OCR table bounding boxes**: OCR-detected tables now include pixel-level bounding box coordinates
- MSG/EML date and recipient extraction fixes

### v4.4.2 (2026-03-04)

- **OMML-to-LaTeX math conversion for DOCX**: Math equations converted to LaTeX notation
- **Plain text output paths for all extractors**: DOCX, PPTX, ODT, FB2, DocBook, RTF, Jupyter produce clean plain text when `output_format="plain"`
- **`OutputFormat.STRUCTURED`** value added
- **HTML metadata extraction fix** with Plain output
- CLI now includes full feature set (archive support)
