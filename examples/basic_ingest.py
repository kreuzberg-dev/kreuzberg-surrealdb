"""Basic document ingestion and BM25 search with DocumentConnector.

Usage:
    uv run python examples/basic_ingest.py <path-to-file>

    # With a remote SurrealDB:
    docker run --rm -p 8000:8000 surrealdb/surrealdb:latest start --user root --pass root
    uv run python examples/basic_ingest.py report.pdf
"""

import asyncio
import sys
from pathlib import Path

from kreuzberg_surrealdb import DatabaseConfig, DocumentConnector


async def main(file_path: str) -> None:
    path = Path(file_path)
    if not path.exists():
        print(f"File not found: {file_path}")
        sys.exit(1)

    db = DatabaseConfig(
        db_url="ws://localhost:8000",
        namespace="examples",
        database="basic_ingest",
        username="root",
        password="root",
    )

    async with DocumentConnector(db=db) as connector:
        await connector.setup_schema()
        print(f"Ingesting {path.name}...")
        await connector.ingest_file(path)
        print("Done.")

        # Run a BM25 search
        query = input("\nSearch query (or press Enter to skip): ").strip()
        if not query:
            return

        results = await connector.search(query, limit=5)
        if not results:
            print("No results found.")
            return

        for i, result in enumerate(results, 1):
            source = result.get("source", "unknown")
            score = result.get("score", 0.0)
            content = result.get("content", "")[:200]
            print(f"\n--- Result {i} (score: {score:.4f}) ---")
            print(f"Source: {source}")
            print(f"Content: {content}...")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: uv run python examples/basic_ingest.py <path-to-file>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
