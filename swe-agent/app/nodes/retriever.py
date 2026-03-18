"""
Retriever node: ingests the repository, builds a FAISS index,
and retrieves the top-k most relevant chunks for the issue.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from app.config import settings
from app.state import AgentState
from app.tools.repo_ingest import ingest_repo
from app.tools.chunking import chunk_all_files
from app.tools.retrieval import ChunkIndex, extract_mentioned_files

logger = logging.getLogger(__name__)


def retriever_node(state: AgentState) -> Dict[str, Any]:
    """
    LangGraph node: index the repo and retrieve relevant chunks.

    Reads:  state["repo_path"], state["issue_text"]
    Writes: state["chunks"], state["retrieved_chunks"], state["retrieved_files"]
    """
    repo_path = state["repo_path"]
    issue_text = state["issue_text"]

    logger.info("Ingesting repository: %s", repo_path)
    file_paths = ingest_repo(repo_path)
    logger.info("Found %d indexable files.", len(file_paths))

    logger.info("Chunking files…")
    chunks = chunk_all_files(repo_path, file_paths)
    logger.info("Created %d chunks.", len(chunks))

    if not chunks:
        logger.warning("No chunks produced — repository may be empty or all files were filtered.")
        return {
            "chunks": [],
            "retrieved_chunks": [],
            "retrieved_files": [],
        }

    # Files explicitly mentioned in the issue get a score boost
    boost_files = extract_mentioned_files(issue_text, file_paths)
    if boost_files:
        logger.info("Issue mentions files: %s — applying boost.", boost_files)

    logger.info("Building FAISS index…")
    index = ChunkIndex(chunks)

    logger.info("Querying index for top-%d chunks…", settings.top_k_chunks)
    retrieved = index.query(
        issue_text,
        top_k=settings.top_k_chunks,
        boost_files=boost_files or None,
    )

    # Deduplicated sorted list of file paths in retrieved chunks
    seen: set[str] = set()
    retrieved_files: list[str] = []
    for c in retrieved:
        if c.file_path not in seen:
            seen.add(c.file_path)
            retrieved_files.append(c.file_path)

    logger.info("Retrieved %d chunks from %d files.", len(retrieved), len(retrieved_files))

    return {
        "chunks": chunks,
        "retrieved_chunks": retrieved,
        "retrieved_files": retrieved_files,
    }