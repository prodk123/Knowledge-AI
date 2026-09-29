"""Benchmark Retrieval — evaluate Recall@K, MRR, and Latency for different retrieval modes."""

import argparse
import asyncio
import json
import logging
import time
from pathlib import Path

from app.core.config import settings
from app.core.dependencies import (
    get_dense_retriever,
    get_bm25_retriever,
    get_reranker,
    get_retrieval_orchestrator,
    get_embedding_provider_dep,
    get_vector_store
)

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

def evaluate_retrieval(orchestrator, queries, k_values=[1, 3, 5, 10]):
    """Run evaluation and calculate metrics."""
    metrics = {
        "mrr": 0.0,
        "latency_ms": 0.0,
    }
    for k in k_values:
        metrics[f"recall@{k}"] = 0.0

    total_queries = len(queries)
    if total_queries == 0:
        return metrics

    total_latency = 0.0
    
    for item in queries:
        question = item["question"]
        expected_docs = set(item.get("relevant_documents", []))
        
        start_t = time.perf_counter()
        results = orchestrator.retrieve(question)
        latency = (time.perf_counter() - start_t) * 1000
        total_latency += latency
        
        # Calculate ranks of relevant documents
        # A result is considered relevant if its filename is in expected_docs
        first_relevant_rank = None
        hits_at_k = {k: False for k in k_values}
        
        for rank, res in enumerate(results, start=1):
            if res.filename in expected_docs:
                if first_relevant_rank is None:
                    first_relevant_rank = rank
                for k in k_values:
                    if rank <= k:
                        hits_at_k[k] = True
                        
        if first_relevant_rank is not None:
            metrics["mrr"] += 1.0 / first_relevant_rank
            
        for k in k_values:
            if hits_at_k[k]:
                metrics[f"recall@{k}"] += 1.0

    # Average metrics
    metrics["mrr"] /= total_queries
    metrics["latency_ms"] = total_latency / total_queries
    for k in k_values:
        metrics[f"recall@{k}"] /= total_queries
        
    return metrics


async def main():
    parser = argparse.ArgumentParser(description="Evaluate RAG Retrieval Strategies")
    parser.add_argument("--dataset", type=str, default="evaluation/retrieval/questions.json")
    args = parser.parse_args()
    
    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"Dataset not found at {dataset_path}")
        return

    with open(dataset_path, "r") as f:
        queries = json.load(f)
        
    print(f"Loaded {len(queries)} evaluation queries.")
    
    # Initialize components
    embedding_provider = get_embedding_provider_dep()
    vector_store = get_vector_store(settings)
    dense_ret = get_dense_retriever(embedding_provider, vector_store)
    bm25_ret = get_bm25_retriever(settings)
    reranker = get_reranker(settings)
    
    modes = ["dense", "bm25", "hybrid", "hybrid_reranked"]
    
    print("\nRetrieval Benchmark")
    print("────────────────────────────────────────────────────────────────────────")
    print(f"{'Mode':<18} | {'Recall@1':<8} | {'Recall@3':<8} | {'Recall@5':<8} | {'MRR':<5} | {'Latency (ms)'}")
    print("────────────────────────────────────────────────────────────────────────")
    
    results_output = {}
    
    for mode in modes:
        settings.retrieval_mode = mode
        orchestrator = get_retrieval_orchestrator(settings, dense_ret, bm25_ret, reranker)
        
        metrics = evaluate_retrieval(orchestrator, queries)
        results_output[mode] = metrics
        
        print(f"{mode:<18} | {metrics['recall@1']:.2f}     | {metrics['recall@3']:.2f}     | {metrics['recall@5']:.2f}     | {metrics['mrr']:.2f}  | {metrics['latency_ms']:.1f}")

    # Output to file for dashboard
    import os
    output_dir = Path("evaluation/results")
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / "latest_retrieval.json", "w") as f:
        json.dump(results_output, f, indent=2)

if __name__ == "__main__":
    asyncio.run(main())
