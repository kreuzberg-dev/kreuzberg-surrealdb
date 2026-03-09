"""Hybrid RAG pipeline with LLM integration.

Ingests a directory of documents, runs hybrid search, and passes retrieved
chunks as context to an LLM for answer generation.

Usage:
    # Start SurrealDB first:
    docker run --rm -p 8000:8000 surrealdb/surrealdb:latest start --user root --pass root

    export ANTHROPIC_API_KEY="your-key"
    uv run python examples/rag_pipeline.py <path-to-directory>

Requirements:
    pip install anthropic  # LLM client (not included in kreuzberg-surrealdb dependencies)
"""

import asyncio
import os
import sys
from pathlib import Path

from surrealdb import AsyncSurreal

from kreuzberg_surrealdb import DocumentPipeline


async def ingest_and_search(directory: str, query: str) -> list[dict[str, object]]:
    """Ingest documents from a directory and run hybrid search."""
    async with AsyncSurreal("ws://localhost:8000") as db:
        await db.signin({"username": "root", "password": "root"})
        await db.use("examples", "rag_pipeline")

        pipeline = DocumentPipeline(
            db=db,
            embed=True,
            embedding_model="balanced",
        )
        await pipeline.setup_schema()

        path = Path(directory)
        files = sorted(p for p in path.rglob("*") if p.is_file())
        if not files:
            print(f"No files found in {directory}")
            return []

        print(f"Ingesting {len(files)} file(s) from {directory}...")
        await pipeline.ingest_directory(directory)
        print("Ingestion complete.")

        # Hybrid search: vector + BM25 with RRF fusion
        print(f"\nSearching for: {query}")
        results = await pipeline.search(query, limit=5, quality_threshold=0.3)
        return results


def ask_llm(query: str, chunks: list[dict[str, object]]) -> str:
    """Send retrieved chunks as context to Claude for answer generation."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return (
            "[ANTHROPIC_API_KEY not set — skipping LLM call]\n\n"
            "Set the environment variable and re-run to see LLM-generated answers:\n"
            '  export ANTHROPIC_API_KEY="your-key"'
        )

    try:
        import anthropic
    except ImportError:
        return "[anthropic package not installed — skipping LLM call]\n\nInstall it with: pip install anthropic"

    context = "\n\n---\n\n".join(
        f"[Source: {c.get('source', c.get('document', 'unknown'))}]\n{c.get('content', '')}" for c in chunks
    )

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Answer the following question using ONLY the provided context. "
                    f"If the context doesn't contain enough information, say so.\n\n"
                    f"Context:\n{context}\n\n"
                    f"Question: {query}"
                ),
            }
        ],
    )
    return message.content[0].text


async def main(directory: str) -> None:
    path = Path(directory)
    if not path.is_dir():
        print(f"Not a directory: {directory}")
        sys.exit(1)

    query = input("Search query: ").strip()
    if not query:
        print("No query provided.")
        sys.exit(1)

    results = await ingest_and_search(directory, query)

    if not results:
        print("No results found.")
        return

    print(f"\n{'=' * 60}")
    print(f"Found {len(results)} chunk(s):")
    print(f"{'=' * 60}")
    for i, result in enumerate(results, 1):
        content = result.get("content", "")[:150]
        print(f"\n[{i}] {content}...")

    # Pass chunks to LLM for answer generation
    print(f"\n{'=' * 60}")
    print("LLM Answer:")
    print(f"{'=' * 60}")
    answer = ask_llm(query, results)
    print(answer)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: uv run python examples/rag_pipeline.py <path-to-directory>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
