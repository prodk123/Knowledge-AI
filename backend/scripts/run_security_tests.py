import asyncio
import json
import os
import sys

# Ensure backend root is in PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.config import settings
from app.services.generation_service import GenerationService
from app.core.guardrails.engine import GuardrailEngine
from app.core.guardrails.input.normalization import InputNormalizationGuardrail
from app.core.guardrails.input.secrets import SecretDetectionGuardrail
from app.core.guardrails.input.prompt_injection import PromptInjectionGuardrail
from app.core.guardrails.context.indirect_injection import IndirectInjectionGuardrail
from app.core.guardrails.output.secrets import OutputSecretGuardrail
from app.core.guardrails.output.citations import CitationGuardrail
from app.rag.pipeline import RAGPipeline
from app.core.dependencies import get_retrieval_orchestrator, get_context_builder
from fastapi import Request
import uuid
from app.core.tracing import Tracer, current_trace_id

# We need to monkey-patch `_log_event` in GuardrailEngine so it doesn't try to write to the DB
# since we aren't spinning up Postgres in this script.

async def mock_log_event(self, stage_name: str, result, latency: float, trace_id):
    # Just print it for debugging if needed, but we don't save to DB.
    pass

GuardrailEngine._log_event = mock_log_event

async def main():
    print("========================================")
    print("STAGE 7.5: RED-TEAM SECURITY TEST RUNNER")
    print("========================================")
    
    generation_service = GenerationService(settings)
    
    # To mock dependencies properly, we should just use the app's Dependency Injection
    # but we don't have a FastAPI request. We can instantiate RAGPipeline manually.
    
    from app.rag.embeddings import OpenAICompatibleEmbeddingProvider
    from app.rag.vector_store import QdrantVectorStore
    from app.rag.dense_retriever import DenseRetriever
    from app.rag.bm25_retriever import BM25Retriever
    from app.rag.reranker import FlashRankReranker
    from app.rag.retriever import RetrievalOrchestrator
    from app.rag.prompt import ContextBuilder
    from app.models.auth import User
    
    # Minimal mocks for components that don't need real execution if we just want to test Guardrails
    # But since we want to test RBAC and grounding, we should just initialize the real ones or mock them.
    # To keep it simple, we will test `engine.check_input`, and for testing context/output,
    # we simulate the pipeline manually instead of standing up the whole Qdrant DB.
    
    # We'll just test the Guardrail Engine on different stages based on the test category.
    # If category is "indirect_injection", we test check_context.
    # If category is "secret_exfiltration", we test check_input AND check_output.
    
    input_guardrails = [
        InputNormalizationGuardrail(),
        SecretDetectionGuardrail(),
        PromptInjectionGuardrail(generation_service)
    ]
    context_guardrails = [
        IndirectInjectionGuardrail()
    ]
    output_guardrails = [
        OutputSecretGuardrail(),
        # GroundingGuardrail is currently excluded from script since it needs mocking
        CitationGuardrail()
    ]
    
    engine = GuardrailEngine(
        input_guardrails=input_guardrails,
        context_guardrails=context_guardrails,
        output_guardrails=output_guardrails
    )
    
    dataset_path = os.path.join(os.path.dirname(__file__), "guardrail_redteam_dataset.json")
    with open(dataset_path, "r") as f:
        dataset = json.load(f)
        
    print(f"Loaded {len(dataset)} test cases.\n")
    
    results = {
        "total_cases": len(dataset),
        "passed": 0,
        "failed": 0,
        "false_positives": 0,
        "false_negatives": 0,
        "details": []
    }
    
    for item in dataset:
        test_id = item["id"]
        query = item["query"]
        expected = item["expected_action"]
        category = item["category"]
        
        # Test Input Pipeline
        # To simulate a request, we need a trace ID ContextVar
        req_id = str(uuid.uuid4())
        
        try:
            async with Tracer.start_trace(request_id=req_id, user_id=uuid.uuid4(), conversation_id=uuid.uuid4()) as trace:
                
                # Determine which guardrail stage to test
                if category == "indirect_injection":
                    # Mock retrieved chunks
                    chunks = [{"text": query, "metadata": {"source": "malicious_doc.pdf"}}]
                    result = engine.check_context(query, chunks)
                elif category == "system_prompt_extraction":
                    # Mock an LLM generating the system prompt
                    result = await engine.check_output(query, [{"text": "Doc", "metadata": {}}])
                else:
                    # Default: Test Input
                    result = await engine.check_input(query)
                
                actual_action = result.status
                
                passed = (actual_action == expected)
                
                print(f"[{'PASS' if passed else 'FAIL'}] {test_id} ({category})")
                print(f"   Query: {query[:60]}...")
                print(f"   Expected: {expected} | Actual: {actual_action}")
                if not passed:
                    print(f"   Reason: {result.reason}")
                
                if passed:
                    results["passed"] += 1
                else:
                    results["failed"] += 1
                    if expected == "ALLOW" and actual_action == "BLOCK":
                        results["false_positives"] += 1
                    elif expected == "BLOCK" and actual_action == "ALLOW":
                        results["false_negatives"] += 1
                        
                results["details"].append({
                    "id": test_id,
                    "category": category,
                    "passed": passed,
                    "expected": expected,
                    "actual": actual_action,
                    "reason": result.reason
                })
        except Exception as e:
            print(f"[ERROR] {test_id}: {e}")
            results["failed"] += 1
            
    # Save results
    output_path = os.path.join(os.path.dirname(__file__), "security_results.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
        
    print("\n========================================")
    print("SECURITY RESULTS")
    print(f"Passed: {results['passed']}/{results['total_cases']}")
    print(f"False Positives: {results['false_positives']}")
    print(f"False Negatives: {results['false_negatives']}")
    print("========================================")

if __name__ == "__main__":
    asyncio.run(main())
