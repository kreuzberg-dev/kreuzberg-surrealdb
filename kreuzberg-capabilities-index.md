# Kreuzberg Capabilities Index

> Index for `kreuzberg-capabilities.md` — v4.3.8 (latest PyPI: v4.4.2)
> Full reference: `./kreuzberg-capabilities.md`

---

## 1. Architecture Overview (L10-22)
- Rust-core with PyO3 bindings, thin Python wrapper
- 75+ file formats, true async (tokio + rayon), native chunking/keywords

## 2. Public API Surface (L25-165)

### 2.1 Core Extraction Functions (L28-67)
- `extract_file_sync/async` — single file, MIME auto-detected
- `extract_bytes_sync/async` — raw bytes, MIME required
- `batch_extract_files_sync/async` — multiple files
- `batch_extract_bytes_sync/async` — multiple byte inputs

### 2.2 MIME Type Detection (L79-86)
- `detect_mime_type()`, `detect_mime_type_from_bytes()`, `detect_mime_type_from_path()`

### 2.3 Configuration I/O (L90-100)
- `ExtractionConfig.from_file()`, `.discover()`, `load_extraction_config_from_file()`
- `config_to_json()`, `config_get_field()`, `config_merge()`

### 2.4 Plugin Registration (L102-126)
- `register_ocr_backend()`, `register_post_processor()`, `register_validator()`
- Unregister, clear, list functions for each plugin type

### 2.5 Error Diagnostics (L128-136)
- `get_last_error_code()`, `get_error_details()`, `classify_error()`, `get_last_panic_context()`

### 2.6 Validation Helpers (L138-152)
- Validators for MIME type, OCR backend, language code, output format, DPI, confidence, etc.

### 2.7 Enumeration Helpers (L154-164)
- `get_extensions_for_mime()`, `get_valid_*()`, embedding presets

## 3. Supported File Formats (L168-177)
- Documents: PDF, DOCX, DOC, XLSX, XLS, PPTX, PPT, ODT, ODS, ODP, RTF, FB2, etc.
- Text/Markup: TXT, MD, JSON, YAML, HTML, XML, LaTeX, Jupyter, etc.
- Email: EML, MSG | eBooks: EPUB | Archives: ZIP, RAR, 7Z, TAR, GZIP
- Images (OCR): PNG, JPEG, TIFF, GIF, BMP, WEBP, SVG
- Data: CSV

## 4. Configuration Classes (L180-428)

### 4.1 ExtractionConfig (L182-211)
- Top-level: `use_cache`, `force_ocr`, `output_format`, `result_format`, `include_document_structure`
- Sub-configs: `ocr`, `chunking`, `images`, `pdf_options`, `token_reduction`, `language_detection`, `keywords`, `postprocessor`, `html_options`, `pages`

### 4.2 OcrConfig (L233-241)
- `backend` (tesseract/easyocr/paddleocr), `language`, `tesseract_config`

### 4.3 TesseractConfig (L243-269)
- PSM, OEM, confidence, table detection, char whitelist/blacklist, preprocessing

### 4.4 ImagePreprocessingConfig (L271-282)
- DPI, rotation, deskew, denoise, contrast, binarization

### 4.5 PaddleOcrConfig (L284-302) — NOT exported, reference only

### 4.6 ChunkingConfig (L304-312)
- `max_chars`, `max_overlap`, `embedding`, `preset`

### 4.7 EmbeddingConfig & EmbeddingModelType (L314-331)
- Model presets: balanced/compact/large, FastEmbed, custom

### 4.8 ImageExtractionConfig (L333-343)
- Extract images from documents, DPI settings

### 4.9 PdfConfig (L345-356)
- `extract_images`, `passwords`, `extract_metadata`, `extract_annotations`, `hierarchy`

### 4.10 HierarchyConfig (L358-366)
### 4.11 PageConfig (L368-375) — per-page extraction, page markers
### 4.12 LanguageDetectionConfig (L377-384)
### 4.13 KeywordConfig (L386-397) — YAKE/RAKE algorithms
### 4.14 TokenReductionConfig (L399-405) — off/light/moderate/aggressive/maximum
### 4.15 PostProcessorConfig (L407-414)
### 4.16 OcrElementConfig (L416-428) — NOT exported, reference only

## 5. ExtractionResult Structure (L432-581)

### 5.1 ExtractionResult (L434-462)
- `content`, `mime_type`, `metadata`, `tables`, `processing_warnings`
- Optional: `detected_languages`, `chunks`, `images`, `pages`, `elements`, `document`, `extracted_keywords`, `quality_score`, `annotations`

### 5.2 ExtractedTable (L464-472) — `cells`, `markdown`, `page_number`, `bounding_box`
### 5.3 Chunk (L474-489) — `content`, `embedding`, ChunkMetadata
### 5.4 PageContent (L491-500) — per-page content, tables, images
### 5.5 ExtractedImage (L502-518) — image data, format, dimensions, OCR result
### 5.6 Element (L520-531) — Unstructured-compatible elements
### 5.7 DocumentStructure (L533-553) — hierarchical tree with DocumentNode
### 5.8 ExtractedKeyword (L555-563)
### 5.9 PdfAnnotation (L565-573)
### 5.10 ProcessingWarning (L575-581)

## 6. Metadata Structure (L585-689)
- Common fields: title, subject, authors, keywords, language, dates, format_type
- Format-specific: PDF, Excel, Email, PowerPoint, Archive, Image, HTML, Text

## 7. OCR Capabilities (L693-735)
- Backends: tesseract (built-in), paddleocr (Rust), easyocr (Python plugin)
- Tesseract PSM (0-13) and OEM (0-3) reference
- EasyOCR: 80+ languages, GPU support, beam width config

## 8. Plugin Protocols (L739-777)
- PostProcessorProtocol: `name()`, `process()`, `processing_stage()`
- OcrBackendProtocol: `name()`, `process_image()`, `process_file()`
- ValidatorProtocol: `name()`, `validate()`, `priority()`

## 9. Error Handling (L781-824)
- ErrorCode enum: SUCCESS through MISSING_DEPENDENCY (0-7)
- Exception hierarchy: KreuzbergError -> ValidationError, ParsingError, OCRError, etc.
- PanicContext for Rust panics

## 10. Async/Sync Duality (L828-833)
- True coroutines via Rust tokio, not asyncio.to_thread wrappers

## 11. Chunking & Embeddings (L836-855)
- Native Rust chunking, FastEmbed-compatible models
- Presets: balanced, compact, large

## 12. LangChain Integration Reference (L859-945)
- KreuzbergLoader API: file_path, data, glob, config
- Metadata mapping, content assembly with tables
- Sync/async methods: load(), lazy_load(), aload(), alazy_load()

## 13. Key Design Decisions for Haystack Converter (L948-1026)
- Input handling: str/Path -> extract_file_sync, ByteStream -> extract_bytes_sync
- ExtractionResult -> Haystack Document mapping
- Per-page mode, config passthrough, store_full_path pattern, async support

## 14. Optional Extras (L1029-1043)
- `kreuzberg[easyocr]` for EasyOCR + torch

## 15. Deprecated Functions (L1047-1053)
- `discover_extraction_config()` -> use `ExtractionConfig.discover()`

## 16. Version History (L1083-1105)
- v4.4.0: Multi-language bindings, extraction fixes, PaddleOCR alias fix
- v4.4.1: OCR table inlining, bounding boxes, email fixes
- v4.4.2: OMML-to-LaTeX, plain text output paths, OutputFormat.STRUCTURED

## Quick Reference Table (L1057-1080)
- Common task -> API mapping (extract, batch, config, OCR, chunking, etc.)
