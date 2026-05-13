# Metadata System for LightRAG

## Overview

LightRAG now supports a flexible metadata system that allows you to:
- **Automatically track insertion timestamps** for all documents
- **Add custom metadata fields** to documents (e.g., status, priority, doc_type)
- **Filter retrieved chunks** based on metadata conditions
- **Sort results** by metadata fields (default: newest first)

This is particularly useful for legal/regulatory documents where amendments should supersede original regulations.

## Quick Start

### 1. Insert Documents with Metadata

```python
import asyncio
from lightrag import LightRAG, QueryParam
from lightrag.utils_metadata import create_supersede_filter

async def main():
    rag = LightRAG(working_dir="./storage")
    await rag.initialize_storages()
    
    # Insert original regulation
    await rag.ainsert(
        "RBI Regulation 2020: compliance period is 180 days",
        ids=["RBI-2020-001"],
        metadata={
            "doc_type": "regulation",
            "status": "superseded",
            "superseded_by": "RBI-2023-AMD"
        }
    )
    
    # Insert amendment (automatically gets newer inserted_at timestamp)
    await rag.ainsert(
        "Amendment 2023: compliance period changed to 270 days",
        ids=["RBI-2023-AMD"],
        metadata={
            "doc_type": "amendment",
            "status": "active",
            "priority": "high"
        }
    )
```

**Note**: `inserted_at` timestamp is automatically added if not provided.

### 2. Query with Metadata Filtering

```python
# Filter out superseded documents
supersede_filter = create_supersede_filter()

result = await rag.aquery(
    "What is the compliance period?",
    param=QueryParam(
        mode="naive",
        metadata_filter=supersede_filter,  # Excludes superseded docs
        # Default: sorts by inserted_at (newest first)
    )
)
```

## API Reference

### `ainsert()` - New Parameter

```python
await rag.ainsert(
    input: str | list[str],
    ids: str | list[str] | None = None,
    metadata: dict | list[dict] | None = None,  # NEW
    ...
)
```

**metadata**: Optional metadata dict or list of dicts (one per document)
- Can be a single dict (applied to all documents) or a list (one per document)
- System automatically adds `inserted_at` timestamp if not provided
- Example: `{"doc_type": "amendment", "status": "active", "priority": "high"}`

### `QueryParam` - New Parameters

```python
QueryParam(
    mode="naive",
    metadata_filter: Callable[[dict], bool] | None = None,  # NEW
    metadata_sort_key: Callable[[dict], Any] | None = None,  # NEW
    metadata_sort_reverse: bool = True,  # NEW (default: newest first)
)
```

**metadata_filter**: Filter function that receives metadata dict and returns True to keep
- Example: `lambda meta: meta.get("status") != "superseded"`

**metadata_sort_key**: Sort key function that receives metadata dict and returns comparable value
- Default: sorts by `inserted_at` timestamp
- Example: `lambda meta: meta.get("effective_date", "")`

**metadata_sort_reverse**: Sort direction (True = descending/newest first)

## Built-in Helper Functions

### Filter Functions

```python
from lightrag.utils_metadata import (
    create_supersede_filter,
    create_status_filter,
    create_priority_sort_key,
)

# Exclude superseded documents
filter1 = create_supersede_filter()

# Only allow specific statuses
filter2 = create_status_filter(["active", "draft"])

# Custom filter
filter3 = lambda meta: (
    meta.get("status") == "active" 
    and meta.get("priority") == "high"
)
```

### Sort Functions

```python
# Sort by priority (high > medium > low)
sort_key = create_priority_sort_key()

# Sort by custom field
sort_key = lambda meta: meta.get("effective_date", "")
```

## Use Cases

### Legal Documents with Amendments

**Problem**: Original regulations and amendments are retrieved together, causing conflicting answers.

**Solution**: Mark original as `status: "superseded"` and amendment as `status: "active"`, then filter:

```python
supersede_filter = create_supersede_filter()
result = await rag.aquery(
    query,
    param=QueryParam(metadata_filter=supersede_filter)
)
```

### Time-Sensitive Documents

**Problem**: Need to prioritize newer documents over older ones.

**Solution**: Use default timestamp sorting (automatic):

```python
result = await rag.aquery(
    query,
    param=QueryParam(
        # metadata_sort_reverse=True is default (newest first)
    )
)
```

### Priority-Based Retrieval

**Problem**: High-priority documents should rank higher.

**Solution**: Add priority metadata and use custom sort:

```python
sort_key = create_priority_sort_key()
result = await rag.aquery(
    query,
    param=QueryParam(
        metadata_sort_key=sort_key,
        metadata_sort_reverse=True
    )
)
```

## Complete Example

See `examples/metadata_legal_documents.py` for a full working example demonstrating:
- Inserting documents with metadata
- Filtering superseded documents
- Status-based filtering
- Custom priority filtering
- Sorting by effective date

## Implementation Notes

1. **Automatic Timestamps**: Every document gets an `inserted_at` timestamp in ISO 8601 format (UTC)
2. **Backward Compatible**: Metadata parameter is optional; existing code works unchanged
3. **Filter Execution**: Filters are applied after vector retrieval, before LLM generation
4. **Default Sorting**: If no sort key is provided, sorts by `inserted_at` (newest first)
5. **Fail-Open**: If filter/sort functions raise exceptions, chunks are kept/returned as-is

## Limitations

- Metadata filtering happens **after** vector retrieval, not during
- For very large result sets, consider using more selective queries
- Metadata is stored with document status, not directly in vector storage (current implementation)

## Future Enhancements

Potential improvements for future versions:
- Native metadata filtering in vector storage layer
- Metadata-aware ranking during retrieval
- Metadata indexing for faster filtering
