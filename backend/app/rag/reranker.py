"""Cross-Encoder Reranker — refines rankings using a cross-encoder model."""

import logging
from abc import ABC, abstractmethod

from app.models.chat import RetrievalResult
from app.core.config import Settings

logger = logging.getLogger(__name__)


class Reranker(ABC):
    """Abstract interface for a reranker."""
    
    @abstractmethod
    def rerank(self, query: str, documents: list[RetrievalResult]) -> list[RetrievalResult]:
        pass


class FlashRankReranker(Reranker):
    """Reranks candidates using FlashRank (ultra-lightweight ONNX cross-encoder)."""

    def __init__(self, settings: Settings):
        try:
            from flashrank import Ranker
        except ImportError:
            raise ImportError("FlashRank is required. Run: pip install flashrank")
            
        self.model_name = settings.reranker_model or "ms-marco-MiniLM-L-12-v2"
        # Optional: FlashRank can run on GPU if onnxruntime-gpu is installed
        # but we default to CPU since it's extremely fast anyway.
        logger.info("Initializing FlashRank reranker: %s", self.model_name)
        self.ranker = Ranker(model_name=self.model_name)

    def rerank(self, query: str, documents: list[RetrievalResult]) -> list[RetrievalResult]:
        """Rerank a list of candidates against the query."""
        if not documents:
            return []

        logger.info("Reranking %d candidates", len(documents))

        # FlashRank expects a list of dictionaries with 'id' and 'text'
        passages = [
            {"id": doc.chunk_id, "text": doc.text}
            for doc in documents
        ]

        try:
            from flashrank import RerankRequest
            rerankRequest = RerankRequest(query=query, passages=passages)
            results = self.ranker.rerank(rerankRequest)
        except ImportError:
            # Fallback if older flashrank version uses dict directly (it actually uses namedtuple/pydantic depending on version)
            rerankRequest = {
                "query": query,
                "passages": passages
            }
            try:
                results = self.ranker.rerank(rerankRequest)
            except AttributeError:
                # If ranker expects RerankRequest but it failed to import, try instantiating a dict-like object
                class DummyRequest:
                    def __init__(self, q, p):
                        self.query = q
                        self.passages = p
                results = self.ranker.rerank(DummyRequest(query, passages))

        # Build mapping for O(1) lookup
        doc_map = {doc.chunk_id: doc for doc in documents}
        
        final_results = []
        for rank, res in enumerate(results, start=1):
            chunk_id = res["id"]
            score = res["score"]
            
            doc = doc_map[chunk_id]
            doc.reranker_score = float(score)
            doc.final_rank = rank
            doc.retriever = "hybrid_reranked"
            final_results.append(doc)

        return final_results
