import asyncio
import httpx
import os
import sys

# Production configuration assumes Nginx terminates TLS and serves on port 80/443
# By default we test against localhost assuming we run this from the production host.
API_BASE = os.getenv("SMOKE_TEST_API_URL", "http://localhost/api")

async def run_smoke_test():
    print(f"Starting Production Go-Live Smoke Test against {API_BASE}...")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        # 1. Health check
        print("1. Checking GET /health...")
        try:
            r = await client.get(f"{API_BASE}/health")
            r.raise_for_status()
            data = r.json()
            assert data["status"] == "ok", "App status not ok"
            assert data["database"] == "connected", "Database not connected"
            assert data["qdrant"] == "connected", "Qdrant not connected"
            print("   ✅ Health check passed")
        except Exception as e:
            print(f"   ❌ Health check failed: {e}")
            sys.exit(1)

        # 2. Authentication Test
        print("2. Checking Authentication (login)...")
        # In production, we assume an initial admin is seeded or we use a pre-provisioned test account
        admin_email = os.getenv("SMOKE_TEST_USER", "admin@example.com")
        admin_password = os.getenv("SMOKE_TEST_PASSWORD")
        if not admin_password:
            print("   ⚠️ SMOKE_TEST_PASSWORD not set. Skipping authenticated checks.")
            sys.exit(0)
            
        try:
            r = await client.post(f"{API_BASE}/auth/login", json={"email": admin_email, "password": admin_password})
            r.raise_for_status()
            token = r.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            print("   ✅ Authentication passed")
        except Exception as e:
            print(f"   ❌ Authentication failed: {e}")
            sys.exit(1)

        # 3. Conversation Creation
        print("3. Checking Conversation Creation...")
        try:
            r = await client.post(f"{API_BASE}/conversations/", json={"title": "Smoke Test Conversation"}, headers=headers)
            r.raise_for_status()
            conv_id = r.json()["id"]
            print(f"   ✅ Conversation created ({conv_id})")
        except Exception as e:
            print(f"   ❌ Conversation creation failed: {e}")
            sys.exit(1)

        # 4. Direct Generation
        print("4. Checking Direct Generation & Streaming...")
        try:
            r = await client.post(
                f"{API_BASE}/conversations/{conv_id}/messages",
                json={"content": "Respond with the single word: OK"},
                headers=headers
            )
            r.raise_for_status()
            print("   ✅ Generation successful")
        except Exception as e:
            print(f"   ❌ Generation failed: {e}")
            sys.exit(1)

    print("\n🎉 All smoke tests passed successfully!")

if __name__ == "__main__":
    asyncio.run(run_smoke_test())
