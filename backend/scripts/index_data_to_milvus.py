"""Index project `data` markdown files into the Milvus RAG collection."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
from pathlib import Path
import sys
import time

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from src.core.config import get_settings
from src.rag.indexing_service import RagDocument, RagIndexingService
from src.rag.milvus_repository import MilvusRagRepository


@dataclass(frozen=True)
class IndexingStats:
    """Summary of one local data indexing run."""

    file_count: int
    chunk_count: int
    elapsed_seconds: float


def main() -> None:
    args = parse_args()
    data_dir = (PROJECT_ROOT / args.data_dir).resolve()
    if not data_dir.exists():
        raise SystemExit(f"Data directory does not exist: {data_dir}")

    settings = get_settings()
    repository = MilvusRagRepository(settings)
    if args.rebuild:
        dropped = repository.drop_collection_if_exists()
        print(f"Rebuild enabled. Dropped existing collection: {dropped}")

    service = RagIndexingService(settings=settings, repository=repository)
    markdown_files = sorted(data_dir.rglob("*.md"))
    print(
        "Starting RAG indexing:",
        f"files={len(markdown_files)}",
        f"kb={args.knowledge_base_id}",
        f"collection={settings.milvus_collection}",
        f"data_dir={data_dir}",
    )

    started_at = time.perf_counter()
    chunk_count = 0
    for index, path in enumerate(markdown_files, start=1):
        document = build_document(path, data_dir, args.knowledge_base_id)
        indexed_chunks = service.index_document(document)
        chunk_count += indexed_chunks
        print(f"[{index}/{len(markdown_files)}] {path.relative_to(data_dir)} -> {indexed_chunks} chunks")

    stats = IndexingStats(
        file_count=len(markdown_files),
        chunk_count=chunk_count,
        elapsed_seconds=time.perf_counter() - started_at,
    )
    print(
        "RAG indexing completed:",
        f"files={stats.file_count}",
        f"chunks={stats.chunk_count}",
        f"elapsed={stats.elapsed_seconds:.2f}s",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Index local markdown data into Milvus.")
    parser.add_argument("--data-dir", default="data", help="Project-relative data directory.")
    parser.add_argument(
        "--knowledge-base-id",
        default="cookbook",
        help="Knowledge base public id used by agent requests.",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Drop and recreate the configured Milvus collection before indexing.",
    )
    return parser.parse_args()


def build_document(path: Path, data_dir: Path, knowledge_base_id: str) -> RagDocument:
    relative_path = path.relative_to(data_dir)
    text = path.read_text(encoding="utf-8")
    document_public_id = build_document_id(relative_path)
    category_parts = relative_path.parts[:-1]

    return RagDocument(
        knowledge_base_public_id=knowledge_base_id,
        document_public_id=document_public_id,
        title=path.stem,
        text=text,
        metadata={
            "source_path": relative_path.as_posix(),
            "category": "/".join(category_parts),
            "file_name": path.name,
        },
    )


def build_document_id(relative_path: Path) -> str:
    digest = hashlib.sha1(relative_path.as_posix().encode("utf-8")).hexdigest()[:20]
    return f"doc_{digest}"


if __name__ == "__main__":
    main()

