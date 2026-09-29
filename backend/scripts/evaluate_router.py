import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Add backend directory to sys.path so we can import app modules
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.rag.router import QueryRouter
from app.services.generation_service import GenerationService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    logger.info("Initializing services...")
    generation_service = GenerationService(settings)
    router = QueryRouter(generation_service)

    data_path = Path(__file__).resolve().parent.parent / "evaluation" / "routing" / "routing_questions.json"
    if not data_path.exists():
        logger.error(f"Dataset not found at {data_path}")
        return

    with open(data_path, "r") as f:
        dataset = json.load(f)

    logger.info(f"Loaded {len(dataset)} evaluation questions.")

    correct = 0
    total = len(dataset)
    
    direct_expected = 0
    direct_predicted = 0
    direct_correct = 0
    
    rag_expected = 0
    rag_predicted = 0
    rag_correct = 0

    for item in dataset:
        message = item["message"]
        expected = item["expected_route"]
        history = item.get("conversation", [])

        # The router runs synchronously since generate_json is sync
        decision = router.route(message, history)
        predicted = decision.route

        is_correct = predicted == expected
        if is_correct:
            correct += 1
            logger.info(f"[PASS] {message} -> {predicted}")
        else:
            logger.error(f"[FAIL] {message} -> expected {expected}, got {predicted}")

        if expected == "direct":
            direct_expected += 1
        else:
            rag_expected += 1

        if predicted == "direct":
            direct_predicted += 1
            if is_correct:
                direct_correct += 1
        elif predicted == "rag":
            rag_predicted += 1
            if is_correct:
                rag_correct += 1

    accuracy = correct / total if total > 0 else 0
    
    direct_precision = direct_correct / direct_predicted if direct_predicted > 0 else 0
    direct_recall = direct_correct / direct_expected if direct_expected > 0 else 0
    
    rag_precision = rag_correct / rag_predicted if rag_predicted > 0 else 0
    rag_recall = rag_correct / rag_expected if rag_expected > 0 else 0

    print("\n" + "="*40)
    print("ROUTER EVALUATION RESULTS")
    print("="*40)
    print(f"Total Questions: {total}")
    print(f"Accuracy:        {accuracy:.2%}\n")
    
    print("DIRECT ROUTE:")
    print(f"Precision:       {direct_precision:.2%}")
    print(f"Recall:          {direct_recall:.2%}\n")
    
    print("RAG ROUTE:")
    print(f"Precision:       {rag_precision:.2%}")
    print(f"Recall:          {rag_recall:.2%}")
    print("="*40)

    # Output to file for dashboard
    output_dir = Path(__file__).resolve().parent.parent / "evaluation" / "results"
    output_dir.mkdir(parents=True, exist_ok=True)
    results = {
        "accuracy": accuracy,
        "direct": {
            "precision": direct_precision,
            "recall": direct_recall
        },
        "rag": {
            "precision": rag_precision,
            "recall": rag_recall
        },
        "total": total
    }
    with open(output_dir / "latest_router.json", "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    asyncio.run(main())
