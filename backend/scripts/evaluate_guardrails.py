import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.config import settings
from app.core.dependencies import get_generation_service, get_guardrail_engine

async def main():
    print("Evaluating Guardrail Engine...")
    
    # Initialize services
    generation_service = get_generation_service()
    engine = get_guardrail_engine(generation_service)
    
    dataset_path = os.path.join(os.path.dirname(__file__), "guardrail_dataset.json")
    with open(dataset_path, "r") as f:
        dataset = json.load(f)
        
    correct = 0
    total = len(dataset)
    false_positives = 0
    false_negatives = 0
    
    for item in dataset:
        print(f"Testing {item['id']} ({item['category']})...")
        result = await engine.check_input(item["query"])
        
        actual_action = result.status
        expected_action = item["expected_action"]
        
        if actual_action == expected_action:
            correct += 1
            print(f"  [PASS] Expected {expected_action}, got {actual_action}")
        else:
            print(f"  [FAIL] Expected {expected_action}, got {actual_action}. Reason: {result.reason}")
            if expected_action == "ALLOW" and actual_action == "BLOCK":
                false_positives += 1
            elif expected_action == "BLOCK" and actual_action == "ALLOW":
                false_negatives += 1
                
    print("\n--- Evaluation Results ---")
    print(f"Total Tests: {total}")
    print(f"Accuracy: {correct / total * 100:.2f}%")
    print(f"False Positives: {false_positives}")
    print(f"False Negatives: {false_negatives}")
    
if __name__ == "__main__":
    # Ensure correct working directory
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    asyncio.run(main())
