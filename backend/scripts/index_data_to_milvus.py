"""Index project `data` recipe files into the Milvus RAG collection."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys
import time

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from src.core.config import get_settings
from src.rag.document_loader import (
    SUPPORTED_RAG_DATA_EXTENSIONS,
    build_document_id,
    iter_supported_files,
    load_rag_documents_from_path,
)
from src.rag.indexing_service import RagDocument, RagIndexingService
from src.rag.milvus_repository import MilvusRagRepository


@dataclass(frozen=True)
class IndexingStats:
    """Summary of one local data indexing run."""

    file_count: int
    document_count: int
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
    data_files = iter_supported_files(data_dir)
    print(
        "Starting RAG indexing:",
        f"files={len(data_files)}",
        f"kb={args.knowledge_base_id}",
        f"collection={settings.milvus_collection}",
        f"data_dir={data_dir}",
        f"formats={','.join(sorted(SUPPORTED_RAG_DATA_EXTENSIONS))}",
    )

    started_at = time.perf_counter()
    document_count = 0
    chunk_count = 0
    for index, path in enumerate(data_files, start=1):
        documents = load_rag_documents_from_path(path, data_dir, args.knowledge_base_id)
        indexed_chunks = sum(service.index_document(document) for document in documents)
        document_count += len(documents)
        chunk_count += indexed_chunks
        print(
            f"[{index}/{len(data_files)}] {path.relative_to(data_dir)}"
            f" -> {len(documents)} docs, {indexed_chunks} chunks"
        )

    stats = IndexingStats(
        file_count=len(data_files),
        document_count=document_count,
        chunk_count=chunk_count,
        elapsed_seconds=time.perf_counter() - started_at,
    )
    print(
        "RAG indexing completed:",
        f"files={stats.file_count}",
        f"docs={stats.document_count}",
        f"chunks={stats.chunk_count}",
        f"elapsed={stats.elapsed_seconds:.2f}s",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Index local recipe data into Milvus.")
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
    """Backward-compatible helper for older one-file script tests/imports."""

    documents = load_rag_documents_from_path(path, data_dir, knowledge_base_id)
    if not documents:
        raise ValueError(f"Unsupported RAG data file: {path}")
    return documents[0]


if __name__ == "__main__":
    main()
