"""Reciprocal Rank Fusion — combines multiple ranked result sets."""

from app.models.chat import RetrievalResult


def reciprocal_rank_fusion(
    dense_results: list[RetrievalResult],
    bm25_results: list[RetrievalResult],
    rrf_k: int = 60,
) -> list[RetrievalResult]:
    """Combine Dense and BM25 results using Reciprocal Rank Fusion.
    
    RRF Score = 1 / (k + rank)
    """
    fused_scores: dict[str, float] = {}
    chunk_map: dict[str, RetrievalResult] = {}

    # Helper to apply RRF for a list
    def _apply_rrf(results: list[RetrievalResult], is_dense: bool):
        for rank, result in enumerate(results, start=1):
            chunk_id = result.chunk_id
            
            # Store best result instance (or merge them)
            if chunk_id not in chunk_map:
                chunk_map[chunk_id] = result
            else:
                # Merge tracking fields if already exists
                existing = chunk_map[chunk_id]
                if is_dense:
                    existing.dense_score = result.dense_score
                    existing.dense_rank = result.dense_rank
                else:
                    existing.bm25_score = result.bm25_score
                    existing.bm25_rank = result.bm25_rank

            # Compute RRF
            score = 1.0 / (rrf_k + rank)
            fused_scores[chunk_id] = fused_scores.get(chunk_id, 0.0) + score

    # Apply for both dense and bm25
    _apply_rrf(dense_results, is_dense=True)
    _apply_rrf(bm25_results, is_dense=False)

    # Sort by fused score
    sorted_chunks = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)

    # Rebuild final list with RRF fields populated
    final_results = []
    for rank, (chunk_id, rrf_score) in enumerate(sorted_chunks, start=1):
        result = chunk_map[chunk_id]
        result.rrf_score = rrf_score
        result.rrf_rank = rank
        result.retriever = "hybrid"
        final_results.append(result)

    return final_results
