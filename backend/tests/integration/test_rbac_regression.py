import pytest
import uuid
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import TEST_ADMIN_PASSWORD


def unique_email(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}@test.com"

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

def auth_headers(token: str):
    return {"Authorization": f"Bearer {token}"}

def register_user(client, email: str, password: str, full_name: str, extra: dict = None):
    payload = {"email": email, "password": password, "full_name": full_name}
    if extra:
        payload.update(extra)
    return client.post("/auth/register", json=payload)

def login_user(client, email: str, password: str):
    res = client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


def test_rbac_new_registration(client):
    """Test A: New Registration creates USER role with chat.use permission."""
    res = register_user(client, unique_email("rbac_new"), "securepass123", "New RBAC User")
    assert res.status_code == 201
    token = res.json()["access_token"]

    me_res = client.get("/auth/me", headers=auth_headers(token))
    assert me_res.status_code == 200
    user_data = me_res.json()

    # Verify USER role
    roles = [r["name"] for r in user_data.get("roles", [])]
    assert "USER" in roles

    # Verify chat.use permission via the role
    perms = set()
    for r in user_data.get("roles", []):
        for p in r.get("permissions", []):
            perms.add(p["name"])
    
    assert "chat.use" in perms
    assert "admin" not in roles


def test_rbac_user_restrictions(client):
    """Test C: USER administrative restrictions."""
    res = register_user(client, unique_email("rbac_restrict"), "securepass123", "Restrict User")
    assert res.status_code == 201
    token = res.json()["access_token"]
    headers = auth_headers(token)

    # Cannot get users list
    res = client.get("/users/", headers=headers)
    assert res.status_code in [401, 403, 404], f"Should be blocked, got {res.status_code}"

    # Cannot delete documents
    # Using a fake UUID
    res = client.delete("/documents/00000000-0000-0000-0000-000000000000", headers=headers)
    assert res.status_code in [401, 403], f"Should be blocked, got {res.status_code}"


def test_rbac_privilege_escalation(client):
    """Test E: Privilege escalation."""
    # Attempt to inject admin role
    res = register_user(
        client, 
        unique_email("rbac_escalate"), 
        "securepass123", 
        "Escalate User",
        extra={"role": "admin", "roles": ["admin"]}
    )
    assert res.status_code == 201
    token = res.json()["access_token"]

    me_res = client.get("/auth/me", headers=auth_headers(token))
    roles = [r["name"] for r in me_res.json().get("roles", [])]
    assert "admin" not in roles
    assert "USER" in roles


def test_rbac_conversation_sync_regression(client):
    """Test F: Conversation Sync Regression (Backend creation logic)."""
    res = register_user(client, unique_email("rbac_conv"), "securepass123", "Conv User")
    assert res.status_code == 201
    token = res.json()["access_token"]
    headers = auth_headers(token)

    # Create conversation
    conv_res = client.post("/conversations/", json={"title": "Test Chat"}, headers=headers)
    assert conv_res.status_code == 200
    conv_id = conv_res.json()["id"]

    # Verify it appears in list
    list_res = client.get("/conversations/", headers=headers)
    assert list_res.status_code == 200
    conv_ids = [c["id"] for c in list_res.json()]
    assert conv_id in conv_ids


def test_rbac_admin_privileges(client):
    """Test D: ADMIN privileges."""
    token = login_user(client, "admin@example.com", TEST_ADMIN_PASSWORD)
    headers = auth_headers(token)

    # Can get users list
    res = client.get("/users/", headers=headers)
    assert res.status_code == 200

    # Can get documents
    res = client.get("/documents/", headers=headers)
    assert res.status_code == 200
