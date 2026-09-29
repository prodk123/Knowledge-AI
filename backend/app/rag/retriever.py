"""Retriever — orchestrates query embedding and vector search."""

import logging

from app.models.chat import RetrievalResult
from app.core.config import Settings
from app.rag.dense_retriever import DenseRetriever
from app.rag.bm25_retriever import BM25Retriever
from app.rag.fusion import reciprocal_rank_fusion
from app.rag.reranker import Reranker

logger = logging.getLogger(__name__)


class RetrievalOrchestrator:
    """Orchestrates different retrieval strategies.
    
    Supports: dense, bm25, hybrid, and hybrid_reranked modes.
    """

    def __init__(
        self,
        settings: Settings,
        dense_retriever: DenseRetriever,
        bm25_retriever: BM25Retriever,
        reranker: Reranker,
    ):
        self.settings = settings
        self.dense_retriever = dense_retriever
        self.bm25_retriever = bm25_retriever
        self.reranker = reranker

    def retrieve(self, query: str, allowed_roles: list[str] | None = None) -> list[RetrievalResult]:
        """Retrieve the most relevant chunks based on configured mode, constrained by authorization."""
        mode = self.settings.retrieval_mode
        logger.info("Executing retrieval in mode: %s", mode)

        if mode == "dense":
            results = self.dense_retriever.retrieve(
                query, top_k=self.settings.dense_top_k, allowed_roles=allowed_roles
            )
            return results[:self.settings.final_top_k]

        elif mode == "bm25":
            results = self.bm25_retriever.retrieve(
                query, top_k=self.settings.bm25_top_k, allowed_roles=allowed_roles
            )
            return results[:self.settings.final_top_k]

        elif mode in ["hybrid", "hybrid_reranked"]:
            dense_res = self.dense_retriever.retrieve(
                query, top_k=self.settings.dense_top_k, allowed_roles=allowed_roles
            )
            bm25_res = self.bm25_retriever.retrieve(
                query, top_k=self.settings.bm25_top_k, allowed_roles=allowed_roles
            )
            
            fused_candidates = reciprocal_rank_fusion(
                dense_results=dense_res, 
                bm25_results=bm25_res, 
                rrf_k=self.settings.rrf_k
            )
            
            # Trim to hybrid candidate pool size
            candidates = fused_candidates[:self.settings.hybrid_candidate_k]

            if mode == "hybrid":
                return candidates[:self.settings.final_top_k]
            
            # mode == "hybrid_reranked"
            reranked = self.reranker.rerank(query=query, documents=candidates)
            return reranked[:self.settings.final_top_k]

        else:
            logger.warning("Unknown retrieval mode %s, falling back to dense", mode)
            results = self.dense_retriever.retrieve(
                query, top_k=self.settings.dense_top_k, allowed_roles=allowed_roles
            )
            return results[:self.settings.final_top_k]
