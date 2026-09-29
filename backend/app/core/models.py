"""Model Registry and Routing."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

class ModelInfo:
    def __init__(
        self,
        model_id: str,
        provider: str,
        capabilities: list[str],
        cost_per_1k_input: float,
        cost_per_1k_output: float,
        context_window: int = 8192,
        is_fallback: bool = False
    ):
        self.model_id = model_id
        self.provider = provider
        self.capabilities = capabilities
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.context_window = context_window
        self.is_fallback = is_fallback


class ModelRegistry:
    def __init__(self):
        self.models: dict[str, ModelInfo] = {}

    def register(self, model: ModelInfo):
        self.models[model.model_id] = model

    def get_model(self, model_id: str) -> Optional[ModelInfo]:
        return self.models.get(model_id)

    def get_fallback_model(self, failed_model_id: str) -> Optional[ModelInfo]:
        """Get an appropriate fallback model."""
        # Simple fallback strategy for Stage 8.9
        for m in self.models.values():
            if m.is_fallback and m.model_id != failed_model_id:
                return m
        return None

# Global Model Registry
model_registry = ModelRegistry()

# Register the primary Nemotron model (NVIDIA NIM)
model_registry.register(ModelInfo(
    model_id="nvidia/nemotron-3-super-120b-a12b",
    provider="nvidia",
    capabilities=["chat", "json", "routing", "evaluation", "complex_planning", "synthesis"],
    cost_per_1k_input=0.0,   # Free-tier NIM
    cost_per_1k_output=0.0,
    context_window=8192
))

# Register the previous 11B model as a lightweight fallback within the same provider
model_registry.register(ModelInfo(
    model_id="meta/llama-3.2-11b-vision-instruct",
    provider="nvidia",
    capabilities=["chat", "routing"],
    cost_per_1k_input=0.0,
    cost_per_1k_output=0.0,
    context_window=8192,
    is_fallback=True
))

