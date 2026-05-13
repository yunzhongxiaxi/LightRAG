"""
Example: Using Metadata for Legal Document Amendment Handling

This example demonstrates how to use LightRAG's metadata system to handle
legal documents with amendments, ensuring that newer amendments take priority
over older regulations during retrieval.

Use Case:
- Original regulations and amendments are stored as separate documents
- Amendments should supersede original regulations
- Retrieval should prioritize active documents over superseded ones
- Newer documents should rank higher than older ones
"""

import asyncio
from datetime import datetime, timezone
from lightrag import LightRAG, QueryParam
from lightrag.llm.openai import gpt_4o_mini_complete, openai_embed
from lightrag.utils_metadata import create_supersede_filter, create_status_filter


async def main():
    # Initialize LightRAG
    rag = LightRAG(
        working_dir="./legal_rag_storage",
        llm_model_func=gpt_4o_mini_complete,
        embedding_func=openai_embed,
    )
    await rag.initialize_storages()

    # Example 1: Insert original regulation
    print("Inserting original RBI regulation...")
    await rag.ainsert(
        """
        RBI Regulation 2020-001: Compliance Requirements for Financial Institutions

        Section 3.2: Reporting Timeline
        All financial institutions must submit quarterly compliance reports within
        180 days of the end of each fiscal quarter.

        Section 4.1: Documentation Requirements
        Institutions must maintain records for a minimum of 5 years.
        """,
        ids=["RBI-2020-001"],
        metadata={
            "doc_type": "regulation",
            "doc_number": "RBI-2020-001",
            "status": "superseded",  # Mark as superseded
            "effective_date": "2020-01-15",
            "superseded_by": "RBI-2023-001-AMD",
            "authority": "Reserve Bank of India",
        },
    )

    # Example 2: Insert amendment (newer document)
    print("Inserting amendment...")
    await rag.ainsert(
        """
        Amendment RBI-2023-001-AMD to Regulation 2020-001

        Effective Date: June 1, 2023

        Section 3.2 Amendment:
        The reporting timeline in Section 3.2 is hereby amended. All financial
        institutions must now submit quarterly compliance reports within 270 days
        (extended from 180 days) of the end of each fiscal quarter.

        Rationale: This extension provides institutions with additional time to
        ensure comprehensive and accurate reporting.
        """,
        ids=["RBI-2023-001-AMD"],
        metadata={
            "doc_type": "amendment",
            "doc_number": "RBI-2023-001-AMD",
            "status": "active",  # Mark as active
            "effective_date": "2023-06-01",
            "supersedes": "RBI-2020-001",
            "authority": "Reserve Bank of India",
            "priority": "high",  # Amendments have high priority
        },
    )

    # Example 3: Insert another active regulation (for comparison)
    print("Inserting another active regulation...")
    await rag.ainsert(
        """
        RBI Regulation 2024-005: Digital Payment Security Standards

        All digital payment platforms must implement two-factor authentication
        for transactions exceeding Rs. 10,000.
        """,
        ids=["RBI-2024-005"],
        metadata={
            "doc_type": "regulation",
            "doc_number": "RBI-2024-005",
            "status": "active",
            "effective_date": "2024-03-01",
            "authority": "Reserve Bank of India",
        },
    )

    print("\n" + "=" * 80)
    print("QUERY 1: Without metadata filtering (problematic)")
    print("=" * 80)

    # Query without metadata filtering - may return both old and new
    result_no_filter = await rag.aquery(
        "What is the reporting timeline for quarterly compliance reports?",
        param=QueryParam(
            mode="naive",
            top_k=20,
        ),
    )
    print(f"\nResult without filtering:\n{result_no_filter}\n")

    print("\n" + "=" * 80)
    print("QUERY 2: With supersede filter (recommended)")
    print("=" * 80)

    # Query with supersede filter - excludes superseded documents
    supersede_filter = create_supersede_filter()
    result_with_filter = await rag.aquery(
        "What is the reporting timeline for quarterly compliance reports?",
        param=QueryParam(
            mode="naive",
            top_k=20,
            metadata_filter=supersede_filter,  # Filter out superseded docs
            # Default sorting by inserted_at (newest first) is automatic
        ),
    )
    print(f"\nResult with supersede filter:\n{result_with_filter}\n")

    print("\n" + "=" * 80)
    print("QUERY 3: With status filter (only active documents)")
    print("=" * 80)

    # Query with status filter - only active documents
    status_filter = create_status_filter(["active"])
    result_active_only = await rag.aquery(
        "What are the current RBI regulations?",
        param=QueryParam(
            mode="naive",
            top_k=20,
            metadata_filter=status_filter,
        ),
    )
    print(f"\nResult with status filter:\n{result_active_only}\n")

    print("\n" + "=" * 80)
    print("QUERY 4: Custom filter for high-priority amendments")
    print("=" * 80)

    # Custom filter: only high-priority active documents
    def high_priority_filter(meta: dict) -> bool:
        return (
            meta.get("status") == "active"
            and meta.get("priority") == "high"
        )

    result_high_priority = await rag.aquery(
        "What are the recent important changes to RBI regulations?",
        param=QueryParam(
            mode="naive",
            top_k=20,
            metadata_filter=high_priority_filter,
        ),
    )
    print(f"\nResult with high-priority filter:\n{result_high_priority}\n")

    print("\n" + "=" * 80)
    print("QUERY 5: Custom sort by effective date")
    print("=" * 80)

    # Custom sort: by effective date (newest first)
    def effective_date_sort(meta: dict) -> str:
        return meta.get("effective_date", "")

    result_sorted = await rag.aquery(
        "Show me RBI regulations in chronological order",
        param=QueryParam(
            mode="naive",
            top_k=20,
            metadata_filter=create_status_filter(["active"]),
            metadata_sort_key=effective_date_sort,
            metadata_sort_reverse=True,  # Newest first
        ),
    )
    print(f"\nResult sorted by effective date:\n{result_sorted}\n")

    # Cleanup
    await rag.finalize_storages()
    print("\n✓ Example completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
