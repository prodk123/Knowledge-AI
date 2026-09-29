"""Deterministic metrics for Agent Evaluation."""

import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)

class DeterministicMetrics:
    @staticmethod
    def calculate_routing_accuracy(expected_route: str, actual_route: str) -> dict[str, Any]:
        """Check if the actual route matches the expected route."""
        if not expected_route:
            return {"score": 1.0, "reason": "No expected route specified."}
            
        score = 1.0 if expected_route == actual_route else 0.0
        return {
            "score": score,
            "reason": f"Expected '{expected_route}', got '{actual_route}'"
        }

    @staticmethod
    def calculate_tool_selection_accuracy(expected_tools: list[str], actual_tools: list[str]) -> dict[str, Any]:
        """Check if expected tools were used."""
        if not expected_tools:
            return {"score": 1.0, "reason": "No expected tools specified."}
            
        # Simplistic precision/recall average for tool selection
        expected_set = set(expected_tools)
        actual_set = set(actual_tools)
        
        if not expected_set:
            return {"score": 1.0, "reason": "Empty expected tools."}
            
        correct = expected_set.intersection(actual_set)
        
        # We value recall heavily here: did the agent use the required tools?
        # But we also penalize precision: did it use unnecessary tools?
        recall = len(correct) / len(expected_set)
        precision = len(correct) / len(actual_set) if actual_set else 1.0
        
        # F1 score approximation
        score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        
        return {
            "score": score,
            "reason": f"Expected tools: {expected_tools}, Actual tools: {actual_tools}"
        }

    @staticmethod
    def calculate_agent_selection_accuracy(expected_agents: list[str], actual_agents: list[str]) -> dict[str, Any]:
        """Check if the expected specialized agents were delegated to."""
        if not expected_agents:
            return {"score": 1.0, "reason": "No expected agents specified."}
            
        expected_set = set(expected_agents)
        actual_set = set(actual_agents)
        
        correct = expected_set.intersection(actual_set)
        recall = len(correct) / len(expected_set) if expected_set else 1.0
        precision = len(correct) / len(actual_set) if actual_set else 1.0
        
        score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        
        return {
            "score": score,
            "reason": f"Expected agents: {expected_agents}, Actual agents: {actual_agents}"
        }

    @staticmethod
    def calculate_budget_enforcement(cost: float, max_cost: float, tokens: int, max_tokens: int) -> dict[str, Any]:
        """Ensure budget constraints are not exceeded."""
        if cost > max_cost or tokens > max_tokens:
            return {
                "score": 0.0,
                "reason": f"Budget exceeded: Cost ${cost:.4f}/${max_cost}, Tokens {tokens}/{max_tokens}"
            }
        return {
            "score": 1.0,
            "reason": "Within budget constraints."
        }
