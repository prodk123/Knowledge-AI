"""Test the reliability framework (circuit breakers, retries, fallbacks)."""

import asyncio
import logging
from app.core.reliability import get_circuit_breaker, CircuitBreakerError
from app.core.models import model_registry, ModelInfo
from app.services.generation_service import GenerationService
from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_circuit_breaker():
    logger.info("--- Testing Circuit Breaker ---")
    cb = get_circuit_breaker("test_tool", failure_threshold=2, recovery_timeout=2.0)
    
    async def failing_func():
        raise ValueError("Simulated failure")
        
    async def success_func():
        return "OK"
        
    # 1. Fail twice to trip the breaker
    for i in range(2):
        try:
            await cb.call(failing_func)
        except ValueError:
            pass
            
    # 2. Next call should raise CircuitBreakerError (OPEN)
    try:
        await cb.call(success_func)
        logger.error("FAIL: Circuit breaker did not trip.")
    except CircuitBreakerError:
        logger.info("PASS: Circuit breaker tripped successfully (OPEN).")
        
    # 3. Wait for recovery timeout
    await asyncio.sleep(2.1)
    
    # 4. Next call should succeed and close the breaker (HALF_OPEN -> CLOSED)
    try:
        res = await cb.call(success_func)
        logger.info(f"PASS: Circuit breaker recovered successfully (CLOSED). Result: {res}")
    except Exception as e:
        logger.error(f"FAIL: Circuit breaker failed to recover: {e}")

async def test_llm_fallback():
    logger.info("--- Testing LLM Fallback ---")
    gs = GenerationService(settings)
    # Mock the client to always fail for the primary model
    original_client = gs.client
    
    class MockClient:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    if kwargs.get("model") == "google/gemma-3-27b-it:free":
                        raise RuntimeError("Primary model is down!")
                    # Mock successful response for fallback
                    class MockMsg:
                        content = "Fallback response"
                    class MockChoice:
                        message = MockMsg()
                    class MockUsage:
                        prompt_tokens = 10
                        completion_tokens = 10
                        total_tokens = 20
                    class MockResponse:
                        choices = [MockChoice()]
                        usage = MockUsage()
                    return MockResponse()
    
    gs.client = MockClient()
    
    try:
        res = gs.generate([{"role": "user", "content": "Hello"}])
        logger.info(f"PASS: Fallback succeeded. Result: {res}")
    except Exception as e:
        logger.error(f"FAIL: Fallback did not work: {e}")
    finally:
        gs.client = original_client

async def main():
    await test_circuit_breaker()
    await test_llm_fallback()
    logger.info("Reliability tests complete.")

if __name__ == "__main__":
    asyncio.run(main())
