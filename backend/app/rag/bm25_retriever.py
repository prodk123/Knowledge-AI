"""BM25 Retriever — retrieves chunks using exact/lexical matching."""

import logging
import pickle
from pathlib import Path
from typing import Any

from rank_bm25 import BM25Okapi

from app.core.config import Settings
from app.models.chat import RetrievalResult
from app.rag.chunker import DocumentChunk

logger = logging.getLogger(__name__)


class BM25Retriever:
    """Lexical retrieval using BM25.
    
    Maintains a mapping of chunk_id -> chunk to reconstruct RetrievalResult objects.
    """

    def __init__(self, settings: Settings):
        self.data_dir = Path(settings.upload_dir).parent / "bm25"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.data_dir / "bm25_index.pkl"
        
        self.bm25: BM25Okapi | None = None
        # chunk_id -> dict with text and metadata
        self.corpus_chunks: dict[str, dict[str, Any]] = {}
        # Keep track of tokenized corpus for BM25
        self.tokenized_corpus: list[list[str]] = []
        # Mapping from integer index (in bm25) to chunk_id
        self.index_to_chunk_id: list[str] = []

        self.load_index()

    def _tokenize(self, text: str) -> list[str]:
        """Simple tokenizer for BM25. Lowercases and splits on whitespace/punctuation."""
        import re
        text = text.lower()
        return [word for word in re.split(r'\W+', text) if word]

    def add_chunks(self, chunks: list[DocumentChunk]) -> None:
        """Add new chunks to the BM25 index."""
        if not chunks:
            return

        added_count = 0
        for chunk in chunks:
            if chunk.chunk_id in self.corpus_chunks:
                continue  # Skip existing

            # Store chunk data
            self.corpus_chunks[chunk.chunk_id] = {
                "text": chunk.text,
                "document_id": chunk.document_id,
                "metadata": chunk.metadata,
            }
            
            # Tokenize for BM25
            tokens = self._tokenize(chunk.text)
            self.tokenized_corpus.append(tokens)
            self.index_to_chunk_id.append(chunk.chunk_id)
            added_count += 1

        if added_count > 0:
            logger.info("Added %d new chunks to BM25 index. Rebuilding...", added_count)
            self.bm25 = BM25Okapi(self.tokenized_corpus)
            self.save_index()

    def remove_document_chunks(self, document_id: str) -> None:
        """Remove all chunks associated with a specific document_id."""
        chunk_ids_to_remove = set()
        for cid, data in self.corpus_chunks.items():
            if data.get("document_id") == document_id:
                chunk_ids_to_remove.add(cid)

        if not chunk_ids_to_remove:
            return

        logger.info("Removing %d chunks for document_id %s", len(chunk_ids_to_remove), document_id)
        
        # Rebuild lists without the removed chunks
        new_tokenized = []
        new_index_map = []
        
        for idx, cid in enumerate(self.index_to_chunk_id):
            if cid not in chunk_ids_to_remove:
                new_tokenized.append(self.tokenized_corpus[idx])
                new_index_map.append(cid)
            
        for cid in chunk_ids_to_remove:
            del self.corpus_chunks[cid]

        self.tokenized_corpus = new_tokenized
        self.index_to_chunk_id = new_index_map
        
        if self.tokenized_corpus:
            self.bm25 = BM25Okapi(self.tokenized_corpus)
        else:
            self.bm25 = None
            
        self.save_index()

    def retrieve(self, query: str, top_k: int, allowed_roles: list[str] | None = None) -> list[RetrievalResult]:
        """Retrieve top k chunks using BM25 lexical search."""
        if not self.bm25 or not self.tokenized_corpus:
            logger.warning("BM25 retrieve called but index is empty.")
            return []

        logger.info("Executing BM25 retrieval for top %d", top_k)
        
        query_tokens = self._tokenize(query)
        # get_scores returns a numpy array or list of floats
        scores = self.bm25.get_scores(query_tokens)
        
        # Zip with indices, sort by score descending
        scored_indices = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        
        results = []
        rank = 1
        for idx, score in scored_indices:
            if len(results) >= top_k:
                break
                
            if score <= 0.0:
                continue # Skip irrelevant chunks

            chunk_id = self.index_to_chunk_id[idx]
            chunk_data = self.corpus_chunks[chunk_id]
            
            # Authorization check
            if allowed_roles is not None:
                chunk_allowed_roles = chunk_data.get("metadata", {}).get("allowed_roles")
                if chunk_allowed_roles is not None:
                    # If chunk has restricted roles, user must have at least one of them
                    if not any(role in chunk_allowed_roles for role in allowed_roles):
                        continue
            
            results.append(
                RetrievalResult(
                    chunk_id=chunk_id,
                    document_id=chunk_data["document_id"],
                    text=chunk_data["text"],
                    metadata=chunk_data["metadata"],
                    bm25_score=float(score),
                    bm25_rank=rank,
                    retriever="bm25"
                )
            )
            rank += 1

        logger.info("BM25 retrieval completed with %d results", len(results))
        return results

    def save_index(self) -> None:
        """Persist the index state to disk."""
        try:
            state = {
                "corpus_chunks": self.corpus_chunks,
                "tokenized_corpus": self.tokenized_corpus,
                "index_to_chunk_id": self.index_to_chunk_id,
            }
            with open(self.index_path, "wb") as f:
                pickle.dump(state, f)
            logger.debug("BM25 index saved to %s", self.index_path)
        except Exception as e:
            logger.error("Failed to save BM25 index: %s", e)

    def load_index(self) -> None:
        """Load the index state from disk."""
        if not self.index_path.exists():
            logger.info("No existing BM25 index found at %s", self.index_path)
            return

        try:
            with open(self.index_path, "rb") as f:
                state = pickle.load(f)
            
            self.corpus_chunks = state.get("corpus_chunks", {})
            self.tokenized_corpus = state.get("tokenized_corpus", [])
            self.index_to_chunk_id = state.get("index_to_chunk_id", [])
            
            if self.tokenized_corpus:
                self.bm25 = BM25Okapi(self.tokenized_corpus)
                logger.info("Loaded BM25 index with %d documents", len(self.tokenized_corpus))
        except Exception as e:
            logger.error("Failed to load BM25 index: %s", e)
            # Start fresh if corrupted
            self.corpus_chunks = {}
            self.tokenized_corpus = []
            self.index_to_chunk_id = []
            self.bm25 = None
