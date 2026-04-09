---
name: data-processing
description: ETL pipelines, batch processing, file parsing, serialization
---

# Data Processing

## File Parsing

- Stream large files — never load entire file into memory
- Use streaming parsers: `csv.reader` (Python), `csv-parse` (Node), `encoding/csv` (Go)
- Validate structure (headers, column count) before processing rows
- Per-row error reporting: log bad rows with line number and reason, continue processing
- Support configurable encoding (UTF-8 default, detect or accept as parameter)

## ETL Pipelines

- Separate Extract, Transform, Load into distinct functions — independently testable
- Each step is idempotent: running twice produces the same result
- Checkpoint progress: record last-processed ID/offset for resumability
- Log at each stage boundary: "Extracted N records", "Transformed N", "Loaded N"

## Batch Processing

- Configurable batch size (default 1000, adjustable per operation)
- Progress tracking: log batch number, total processed, estimated remaining
- Partial failure handling: commit successful batches, log and skip failed records
- Wrap each batch in a transaction — rollback on batch failure, not entire job
- Backpressure: pause extraction if transform/load falls behind

## Serialization

- Define explicit schemas for serialization format (JSON Schema, Protobuf, Avro)
- Handle version changes: old data must still parse (backward compatibility)
- Validate after deserialization — don't trust the shape of external data
- Use appropriate formats: JSON for APIs, CSV for tabular data, binary for performance

## Data Validation

- Validate at ingestion boundary — before data enters your system
- Define skip-vs-abort policy: invalid rows skip (with logging) or abort the entire job
- Log validation failures with context: field name, expected type, actual value, row ID
- Explicit type coercion: parse strings to numbers/dates deliberately, never implicitly
