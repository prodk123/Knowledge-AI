"""Tests for Reciprocal Rank Fusion."""

from app.models.chat import RetrievalResult
from app.rag.fusion import reciprocal_rank_fusion

def test_rrf_mathematical_correctness():
    # Dense: A rank 1, B rank 2, C rank 3
    # BM25: B rank 1, D rank 2, A rank 3
    
    dense = [
        RetrievalResult(chunk_id="A", document_id="doc1", text="A", metadata={}),
        RetrievalResult(chunk_id="B", document_id="doc1", text="B", metadata={}),
        RetrievalResult(chunk_id="C", document_id="doc1", text="C", metadata={}),
    ]
    
    bm25 = [
        RetrievalResult(chunk_id="B", document_id="doc1", text="B", metadata={}),
        RetrievalResult(chunk_id="D", document_id="doc1", text="D", metadata={}),
        RetrievalResult(chunk_id="A", document_id="doc1", text="A", metadata={}),
    ]
    
    # Using k=60
    # A dense rank: 1 -> score = 1/61
    # A bm25 rank: 3 -> score = 1/63
    # A total = 1/61 + 1/63 ≈ 0.01639 + 0.01587 = 0.03226
    
    # B dense rank: 2 -> score = 1/62
    # B bm25 rank: 1 -> score = 1/61
    # B total = 1/62 + 1/61 ≈ 0.01612 + 0.01639 = 0.03251
    
    # B > A
    
    results = reciprocal_rank_fusion(dense_results=dense, bm25_results=bm25, rrf_k=60)
    
    assert len(results) == 4
    
    # Top should be B
    assert results[0].chunk_id == "B"
    # Second should be A
    assert results[1].chunk_id == "A"
    
    # B rrf score should be 1/62 + 1/61
    expected_b_score = (1.0 / 62) + (1.0 / 61)
    assert abs(results[0].rrf_score - expected_b_score) < 1e-6
    
    # A rrf score should be 1/61 + 1/63
    expected_a_score = (1.0 / 61) + (1.0 / 63)
    assert abs(results[1].rrf_score - expected_a_score) < 1e-6
    
    # D is third (1/62 = 0.01612)
    assert results[2].chunk_id == "D"
    
    # C is fourth (1/63 = 0.01587)
    assert results[3].chunk_id == "C"

    # Ensure metadata and other tracking is preserved
    assert results[0].retriever == "hybrid"
    assert results[0].rrf_rank == 1
    assert results[1].rrf_rank == 2
