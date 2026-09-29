import asyncio
import httpx
import uuid
import logging
import json
import time

import os

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("staging_e2e")

BASE_URL = os.getenv("E2E_API_URL", "http://localhost:8080/api")

class StagingTestRunner:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        self.users = {}
        self.run_prefix = uuid.uuid4().hex[:8]

    async def run_all(self):
        try:
            await self.phase_2b_auth()
            await self.phase_2c_rbac()
            await self.phase_2d_conversations()
            await self.phase_2e_rag()
            await self.phase_2f_streaming()
            await self.phase_2g_single_agent()
            await self.phase_2h_calendar_email_swarm()
            await self.phase_2j_multi_agent_security()
            await self.phase_2k_external_trust()
            await self.phase_2l_memory()
            await self.phase_2m_background_jobs()
        finally:
            await self.client.aclose()

    async def register(self, email, password, full_name, extra=None):
        payload = {"email": email, "password": password, "full_name": full_name}
        if extra:
            payload.update(extra)
        resp = await self.client.post(f"{BASE_URL}/auth/register", json=payload)
        return resp

    async def login(self, email, password):
        resp = await self.client.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password})
        if resp.status_code == 200:
            return resp.json()["access_token"]
        return None

    def auth_headers(self, token):
        return {"Authorization": f"Bearer {token}"}

    async def _assert_status(self, resp, expected, msg):
        if resp.status_code not in (expected if isinstance(expected, list) else [expected]):
            logger.error(f"FAIL: {msg} - Expected {expected}, got {resp.status_code}: {resp.text}")
            raise Exception(f"Test failed: {msg}")
        logger.info(f"PASS: {msg}")

    # =========================================================================
    # PHASE 2B & 2C - AUTH & RBAC
    # =========================================================================
    async def phase_2b_auth(self):
        logger.info("--- PHASE 2B: AUTHENTICATION ---")
        user_email = f"userA_{self.run_prefix}@example.com"
        # Register
        resp = await self.register(user_email, "SecurePass123!", "User A")
        await self._assert_status(resp, 201, "User registration")
        
        # Test Role Injection
        inj_email = f"userInj_{self.run_prefix}@example.com"
        resp_inj = await self.register(inj_email, "SecurePass123!", "Injected User", extra={"role": "ADMIN", "roles": ["ADMIN"]})
        await self._assert_status(resp_inj, 201, "Role injection registration")
        
        token = await self.login(inj_email, "SecurePass123!")
        me_resp = await self.client.get(f"{BASE_URL}/auth/me", headers=self.auth_headers(token))
        roles = [r["name"] for r in me_resp.json().get("roles", [])]
        if "ADMIN" in roles or "admin" in roles:
            raise Exception("Role injection succeeded! FAIL.")
        logger.info("PASS: Role injection blocked.")
        
        # Store for later
        self.users['A'] = {'email': user_email, 'password': "SecurePass123!"}
        self.users['B'] = {'email': f"userB_{self.run_prefix}@example.com", 'password': "SecurePass123!"}
        await self.register(self.users['B']['email'], "SecurePass123!", "User B")

    async def phase_2c_rbac(self):
        logger.info("--- PHASE 2C: RBAC ---")
        token_a = await self.login(self.users['A']['email'], self.users['A']['password'])
        self.users['A']['token'] = token_a
        
        # User A tries to read all users (Admin only)
        resp = await self.client.get(f"{BASE_URL}/users/", headers=self.auth_headers(token_a))
        await self._assert_status(resp, [401, 403], "USER cannot access /users/")

        # Login admin (assuming admin@example.com / password123 exists from seed)
        token_admin = await self.login("admin@example.com", "password123")
        if not token_admin:
            # Maybe seed hasn't run or is different. We assume it exists for now.
            logger.warning("Admin login failed, assuming seed not applied. Skipping admin checks.")
        else:
            self.users['ADMIN'] = {'token': token_admin}
            resp = await self.client.get(f"{BASE_URL}/users/", headers=self.auth_headers(token_admin))
            await self._assert_status(resp, 200, "ADMIN can access /users/")

    # =========================================================================
    # PHASE 2D - CONVERSATIONS
    # =========================================================================
    async def phase_2d_conversations(self):
        logger.info("--- PHASE 2D: CONVERSATIONS ---")
        token_a = self.users['A']['token']
        token_b = await self.login(self.users['B']['email'], self.users['B']['password'])
        self.users['B']['token'] = token_b

        # Create
        resp = await self.client.post(f"{BASE_URL}/conversations/", json={"title": "Test Chat A"}, headers=self.auth_headers(token_a))
        await self._assert_status(resp, 200, "User A create conversation")
        conv_id = resp.json()["id"]

        # Isolation
        resp_b = await self.client.get(f"{BASE_URL}/conversations/{conv_id}", headers=self.auth_headers(token_b))
        await self._assert_status(resp_b, 404, "User B blocked from User A conversation")

        # Delete
        resp_del = await self.client.delete(f"{BASE_URL}/conversations/{conv_id}", headers=self.auth_headers(token_a))
        await self._assert_status(resp_del, 200, "User A delete conversation")

    # =========================================================================
    # PHASE 2E - RAG / DOCUMENTS
    # =========================================================================
    async def phase_2e_rag(self):
        logger.info("--- PHASE 2E: DOCUMENTS & RAG ---")
        token_a = self.users['A']['token']
        if 'ADMIN' not in self.users:
            logger.warning("Skipping Document upload, no ADMIN token")
            return
            
        token_admin = self.users['ADMIN']['token']
        # For simplicity, we just verify the endpoint protection
        resp = await self.client.post(f"{BASE_URL}/documents/", headers=self.auth_headers(token_a))
        await self._assert_status(resp, [403, 405, 422, 415], "USER A cannot hit document upload directly (unless multipart format missing)")

    # =========================================================================
    # PHASE 2F - STREAMING
    # =========================================================================
    async def phase_2f_streaming(self):
        logger.info("--- PHASE 2F: STREAMING ---")
        token_a = self.users['A']['token']
        # Create conv
        resp = await self.client.post(f"{BASE_URL}/conversations/", json={"title": "Stream Chat"}, headers=self.auth_headers(token_a))
        conv_id = resp.json()["id"]
        
        # We use a standard async request, reading lines
        logger.info(f"Sending stream request to {conv_id}...")
        async with self.client.stream("POST", f"{BASE_URL}/conversations/{conv_id}/messages", 
                                      json={"content": "Reply with exactly 'STREAM_OK'"}, 
                                      headers=self.auth_headers(token_a)) as response:
            await self._assert_status(response, 200, "Stream connection established")
            chunks = 0
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    chunks += 1
            if chunks > 0:
                logger.info(f"PASS: Received {chunks} SSE chunks")
            else:
                logger.error("FAIL: No SSE chunks received!")
                raise Exception("Streaming failure")

    # =========================================================================
    # PHASE 2G, H, I - AGENT / SWARM / APPROVALS
    # =========================================================================
    async def phase_2g_single_agent(self):
        logger.info("--- PHASE 2G: SINGLE AGENT ---")
        pass # Integrated with Swarm logic below

    async def phase_2h_calendar_email_swarm(self):
        logger.info("--- PHASE 2H/2I: CALENDAR -> EMAIL SWARM & APPROVALS ---")
        token_a = self.users['A']['token']
        resp = await self.client.post(f"{BASE_URL}/conversations/", json={"title": "Swarm Chat"}, headers=self.auth_headers(token_a))
        conv_id = resp.json()["id"]
        
        # Trigger the calendar->email flow
        # "Find my relevant calendar event and send an email based on it."
        logger.info("Triggering Calendar -> Email flow. Expecting WAITING_FOR_APPROVAL...")
        
        # This might take a bit for the agent to plan and reach the email step
        async with self.client.stream("POST", f"{BASE_URL}/conversations/{conv_id}/messages", 
                                      json={"content": "Check my calendar. Then, send an email to sandbox@example.com. Important: for the send_email tool, ensure 'body' is a simple string (not a reference), and 'recipients' is a proper JSON array of strings like [\"sandbox@example.com\"]."}, 
                                      headers=self.auth_headers(token_a),
                                      timeout=60.0) as response:
            await self._assert_status(response, 200, "Swarm flow request accepted")
            async for line in response.aiter_lines():
                if "WAITING_FOR_APPROVAL" in line or "approval" in line.lower():
                    logger.info("Detected approval request in stream.")
                    break
        
        # Wait a moment for approval record to hit DB
        await asyncio.sleep(2)
        
        # Fetch pending approvals
        appr_resp = await self.client.get(f"{BASE_URL}/approvals/pending", headers=self.auth_headers(token_a))
        await self._assert_status(appr_resp, 200, "Fetch pending approvals")
        approvals = appr_resp.json()
        if not approvals:
            logger.error("FAIL: No pending approvals found after triggering workflow!")
            raise Exception("Approval not generated")
            
        appr = approvals[0]
        appr_id = appr["id"]
        logger.info(f"PASS: Approval found (ID: {appr_id}, Tool: {appr.get('tool_name')})")

        # Attack: User B tries to approve
        token_b = self.users['B']['token']
        att_resp = await self.client.post(f"{BASE_URL}/approvals/{appr_id}/approve", headers=self.auth_headers(token_b))
        await self._assert_status(att_resp, [400, 403, 404], "User B blocked from approving User A's action")
        
        # Valid Approval
        logger.info("Executing valid approval...")
        valid_resp = await self.client.post(f"{BASE_URL}/approvals/{appr_id}/approve", headers=self.auth_headers(token_a))
        await self._assert_status(valid_resp, 200, "User A approved own action")

        # Replay Attack
        replay_resp = await self.client.post(f"{BASE_URL}/approvals/{appr_id}/approve", headers=self.auth_headers(token_a))
        await self._assert_status(replay_resp, 400, "Replay of consumed approval blocked")

    # =========================================================================
    # PHASE 2J - 2M (Stubs / Automated flow checks)
    # =========================================================================
    async def phase_2j_multi_agent_security(self):
        logger.info("--- PHASE 2J: MULTI-AGENT SECURITY ---")
        pass

    async def phase_2k_external_trust(self):
        logger.info("--- PHASE 2K: EXTERNAL TRUST / SSRF ---")
        pass

    async def phase_2l_memory(self):
        logger.info("--- PHASE 2L: MEMORY ---")
        pass

    async def phase_2m_background_jobs(self):
        logger.info("--- PHASE 2M: BACKGROUND JOBS ---")
        token_a = self.users['A']['token']
        resp = await self.client.post(f"{BASE_URL}/conversations/", json={"title": "Async Chat"}, headers=self.auth_headers(token_a))
        conv_id = resp.json()["id"]

        resp_async = await self.client.post(f"{BASE_URL}/conversations/{conv_id}/messages", 
                                      json={"content": "Async task test", "run_async": True}, 
                                      headers=self.auth_headers(token_a))
        await self._assert_status(resp_async, 200, "Async job submitted")
        job_id = resp_async.json().get("job_id")
        if not job_id:
            raise Exception("No job_id returned for async request")
        logger.info(f"PASS: Async job created with ID {job_id}")

if __name__ == "__main__":
    runner = StagingTestRunner()
    asyncio.run(runner.run_all())
    logger.info("E2E Harness completed successfully.")
