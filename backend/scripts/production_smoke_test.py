import asyncio
import httpx
import logging
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

API_URL = "http://localhost/api"

async def main():
    logger.info("Starting production smoke test...")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        # 1. Health check
        try:
            logger.info("Checking API health...")
            resp = await client.get(f"http://localhost:8000/health")
            if resp.status_code == 200:
                logger.info(f"Health check passed: {resp.json()}")
            else:
                logger.error(f"Health check failed: {resp.status_code} {resp.text}")
        except Exception as e:
            logger.error(f"Could not connect to health endpoint: {e}")
            
        # 2. Test RAG / async routing via direct LLM route if possible, or just standard route
        # Wait, the proxy might not be running if we just run it directly. Let's hit the backend directly for smoke tests in the script.
        pass
        
    logger.info("Production smoke test script completed.")

if __name__ == "__main__":
    asyncio.run(main())
