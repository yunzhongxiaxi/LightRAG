"""Metadata filtering and sorting utilities for LightRAG."""

from typing import Any, Callable
from lightrag.base import QueryParam


def apply_metadata_filter_and_sort(
    chunks: list[dict[str, Any]],
    query_param: QueryParam,
) -> list[dict[str, Any]]:
    """Apply metadata filtering and sorting to retrieved chunks.

    Args:
        chunks: List of chunk dictionaries with metadata
        query_param: Query parameters containing filter and sort functions

    Returns:
        Filtered and sorted list of chunks
    """
    if not chunks:
        return chunks

    # Step 1: Apply metadata filter if provided
    if query_param.metadata_filter is not None:
        filtered_chunks = []
        for chunk in chunks:
            metadata = chunk.get("metadata", {})
            try:
                if query_param.metadata_filter(metadata):
                    filtered_chunks.append(chunk)
            except Exception as e:
                # If filter function fails, keep the chunk (fail-open)
                filtered_chunks.append(chunk)
        chunks = filtered_chunks

    # Step 2: Apply metadata sorting
    # Default: sort by inserted_at timestamp (newest first)
    if query_param.metadata_sort_key is not None:
        sort_key_func = query_param.metadata_sort_key
    else:
        # Default sort by inserted_at timestamp
        def default_sort_key(meta: dict[str, Any]) -> str:
            return meta.get("inserted_at", "")
        sort_key_func = default_sort_key

    try:
        chunks = sorted(
            chunks,
            key=lambda chunk: sort_key_func(chunk.get("metadata", {})),
            reverse=query_param.metadata_sort_reverse,
        )
    except Exception:
        # If sorting fails, return chunks as-is
        pass

    return chunks


def create_supersede_filter(superseded_status: str = "superseded") -> Callable[[dict[str, Any]], bool]:
    """Create a filter function that excludes superseded documents.

    Args:
        superseded_status: The status value indicating a superseded document

    Returns:
        Filter function that returns True for non-superseded documents

    Example:
        >>> filter_func = create_supersede_filter()
        >>> param = QueryParam(metadata_filter=filter_func)
    """
    def filter_func(metadata: dict[str, Any]) -> bool:
        return metadata.get("status") != superseded_status
    return filter_func


def create_status_filter(allowed_statuses: list[str]) -> Callable[[dict[str, Any]], bool]:
    """Create a filter function that only allows specific statuses.

    Args:
        allowed_statuses: List of allowed status values

    Returns:
        Filter function that returns True for allowed statuses

    Example:
        >>> filter_func = create_status_filter(["active", "draft"])
        >>> param = QueryParam(metadata_filter=filter_func)
    """
    def filter_func(metadata: dict[str, Any]) -> bool:
        status = metadata.get("status")
        return status in allowed_statuses if status else True
    return filter_func


def create_priority_sort_key(priority_field: str = "priority") -> Callable[[dict[str, Any]], Any]:
    """Create a sort key function based on priority field.

    Args:
        priority_field: The metadata field name for priority

    Returns:
        Sort key function for priority-based sorting

    Example:
        >>> sort_key = create_priority_sort_key()
        >>> param = QueryParam(metadata_sort_key=sort_key, metadata_sort_reverse=True)
    """
    priority_map = {
        "critical": 4,
        "high": 3,
        "medium": 2,
        "low": 1,
    }

    def sort_key_func(metadata: dict[str, Any]) -> int:
        priority = metadata.get(priority_field, "low")
        if isinstance(priority, str):
            return priority_map.get(priority.lower(), 0)
        return int(priority) if isinstance(priority, (int, float)) else 0

    return sort_key_func
