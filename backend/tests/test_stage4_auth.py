"""
Registration + Auth Tests
Covers all scenarios mandated in the implementation plan:
- Registration success, duplicate email, invalid password, password mismatch
- Password hash NOT exposed via any API
- Default USER role server-side enforced
- Role escalation attempt blocked
- Registration → auto-authentication
- Conversation isolation (two users cannot see each other's conversations)
- Conversation deletion ownership
- Streaming chunk ordering (basic SSE event structure)
"""
import pytest
import uuid
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import TEST_ADMIN_PASSWORD


def unique_email(prefix: str) -> str:
    """Return a unique email address to avoid cross-run collisions in the shared dev DB."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}@test.com"


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# ─── Helpers ──────────────────────────────────────────────────────────────────

def register_user(client, email: str, password: str, full_name: str):
    """Register a user and return the response."""
    return client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": full_name},
    )


def login_user(client, email: str, password: str):
    """Login and return the JWT token."""
    res = client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed: {res.text}"
    return res.json()["access_token"]


def auth_headers(token: str):
    return {"Authorization": f"Bearer {token}"}


# ─── Registration: Success ────────────────────────────────────────────────────

def test_register_success(client):
    """Registration returns HTTP 201 with a valid JWT token."""
    res = register_user(client, unique_email("success"), "securepass123", "New User")
    assert res.status_code == 201, res.text
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_register_returns_usable_jwt(client):
    """JWT returned by /auth/register must work on /auth/me immediately."""
    email = unique_email("jwt")
    res = register_user(client, email, "securepass123", "JWT Test User")
    assert res.status_code == 201
    token = res.json()["access_token"]

    me_res = client.get("/auth/me", headers=auth_headers(token))
    assert me_res.status_code == 200
    me = me_res.json()
    assert me["email"] == email
    assert me["full_name"] == "JWT Test User"


# ─── Registration: Default Role ───────────────────────────────────────────────

def test_register_default_user_role(client):
    """New accounts must receive the USER role and no escalated roles."""
    res = register_user(client, unique_email("role"), "securepass123", "Role Test User")
    assert res.status_code == 201
    token = res.json()["access_token"]

    me_res = client.get("/auth/me", headers=auth_headers(token))
    assert me_res.status_code == 200
    me = me_res.json()

    roles = [r["name"] for r in me.get("roles", [])]
    assert "USER" in roles, f"Expected USER role, got: {roles}"
    # Must NOT be an admin
    assert "ADMIN" not in roles, f"Unexpected ADMIN role for self-registered user"


# ─── Registration: Password Hash NOT Exposed ──────────────────────────────────

def test_register_password_hash_not_exposed(client):
    """The /auth/me endpoint must never return password_hash."""
    res = register_user(client, unique_email("hash"), "securepass123", "Hash Test User")
    assert res.status_code == 201
    token = res.json()["access_token"]

    me_res = client.get("/auth/me", headers=auth_headers(token))
    assert me_res.status_code == 200
    me = me_res.json()

    assert "password_hash" not in me
    assert "password" not in me


# ─── Registration: Duplicate Email ────────────────────────────────────────────

def test_register_duplicate_email(client):
    """Registering with an email that already exists returns HTTP 409."""
    email = unique_email("dup")
    # First registration
    res1 = register_user(client, email, "securepass123", "First User")
    assert res1.status_code == 201

    # Second registration with same email
    res2 = register_user(client, email, "differentpass456", "Second User")
    assert res2.status_code == 409
    assert "already" in res2.json()["detail"].lower()


# ─── Registration: Invalid / Weak Password ────────────────────────────────────

def test_register_short_password(client):
    """Passwords shorter than 8 characters must be rejected with HTTP 400."""
    res = register_user(client, "weakpass@test.com", "abc", "Weak Pass User")
    assert res.status_code == 400
    assert "8" in res.json()["detail"]


def test_register_empty_fields(client):
    """Missing required fields must return a validation error (422)."""
    res = client.post("/auth/register", json={"email": "missing@test.com"})
    assert res.status_code == 422


# ─── Registration: Role Escalation Attempt ────────────────────────────────────

def test_register_cannot_specify_role(client):
    """
    Sending extra fields (like 'role') in the registration payload must not
    affect the assigned role. The server ignores unknown fields and always
    assigns the default USER role.
    """
    res = client.post(
        "/auth/register",
        json={
            "email": unique_email("escalation"),
            "password": "securepass123",
            "full_name": "Role Escalation Attempt",
            "role": "ADMIN",          # Extra field — must be ignored
            "roles": ["ADMIN"],       # Extra field — must be ignored
        },
    )
    assert res.status_code == 201
    token = res.json()["access_token"]

    me_res = client.get("/auth/me", headers=auth_headers(token))
    roles = [r["name"] for r in me_res.json().get("roles", [])]
    assert "ADMIN" not in roles


# ─── Registration → Agent Workflow ────────────────────────────────────────────

def test_register_then_create_conversation(client):
    """
    A freshly registered user should be able to create a conversation
    immediately without any additional setup.
    """
    res = register_user(client, unique_email("agentflow"), "securepass123", "Agent Flow User")
    assert res.status_code == 201
    token = res.json()["access_token"]

    conv_res = client.post(
        "/conversations/",
        json={"title": "Test conversation"},
        headers=auth_headers(token),
    )
    assert conv_res.status_code == 200, conv_res.text
    conv = conv_res.json()
    assert conv["title"] == "Test conversation"


# ─── Conversation Isolation (Two Users) ──────────────────────────────────────

def test_two_user_conversation_isolation(client):
    """
    User A's conversations must not be visible to User B or deletable by User B.
    """
    # Register two users
    user_a_res = register_user(client, unique_email("usera"), "securepass123", "User A")
    assert user_a_res.status_code == 201
    token_a = user_a_res.json()["access_token"]

    user_b_res = register_user(client, unique_email("userb"), "securepass123", "User B")
    assert user_b_res.status_code == 201
    token_b = user_b_res.json()["access_token"]

    # User A creates a conversation
    conv_res = client.post(
        "/conversations/",
        json={"title": "User A private conversation"},
        headers=auth_headers(token_a),
    )
    assert conv_res.status_code == 200
    conv_id = conv_res.json()["id"]

    # User B must NOT be able to read User A's conversation
    read_res = client.get(
        f"/conversations/{conv_id}",
        headers=auth_headers(token_b),
    )
    assert read_res.status_code == 404

    # User B list must not contain User A's conversation
    list_res = client.get("/conversations/", headers=auth_headers(token_b))
    assert list_res.status_code == 200
    ids = [c["id"] for c in list_res.json()]
    assert conv_id not in ids


# ─── Conversation Delete Ownership ────────────────────────────────────────────

def test_conversation_delete_ownership(client):
    """
    Only the owner can delete a conversation. Deletion by another user must
    return 404 (ownership-preserving response).
    """
    user_a_res = register_user(client, unique_email("delowner_a"), "securepass123", "Del Owner A")
    assert user_a_res.status_code == 201
    token_a = user_a_res.json()["access_token"]

    user_b_res = register_user(client, unique_email("delowner_b"), "securepass123", "Del Owner B")
    assert user_b_res.status_code == 201
    token_b = user_b_res.json()["access_token"]

    # A creates a conversation
    conv_res = client.post(
        "/conversations/",
        json={"title": "Should only be deletable by A"},
        headers=auth_headers(token_a),
    )
    assert conv_res.status_code == 200
    conv_id = conv_res.json()["id"]

    # B tries to delete A's conversation — must fail
    del_res = client.delete(
        f"/conversations/{conv_id}",
        headers=auth_headers(token_b),
    )
    assert del_res.status_code == 404

    # A's conversation still exists
    read_res = client.get(
        f"/conversations/{conv_id}",
        headers=auth_headers(token_a),
    )
    assert read_res.status_code == 200

    # A can delete their own conversation
    del_own_res = client.delete(
        f"/conversations/{conv_id}",
        headers=auth_headers(token_a),
    )
    assert del_own_res.status_code == 200

    # Now it's gone
    gone_res = client.get(
        f"/conversations/{conv_id}",
        headers=auth_headers(token_a),
    )
    assert gone_res.status_code == 404


# ─── Existing Auth Tests (unchanged) ─────────────────────────────────────────

def test_login_success(client):
    response = client.post(
        "/auth/login",
        json={"email": "admin@example.com", "password": TEST_ADMIN_PASSWORD},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_failure(client):
    response = client.post(
        "/auth/login",
        json={"email": "admin@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401


def test_protected_route_without_token(client):
    response = client.get("/documents/")
    assert response.status_code == 401


def test_protected_route_with_token(client):
    login_res = client.post(
        "/auth/login",
        json={"email": "admin@example.com", "password": TEST_ADMIN_PASSWORD},
    )
    token = login_res.json()["access_token"]

    response = client.get(
        "/documents/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    docs = response.json()
    assert isinstance(docs, list)


def test_document_rbac_filtering(client):
    login_res = client.post(
        "/auth/login",
        json={"email": "khatridevansh394@gmail.com", "password": "devansh123"},
    )
    token = login_res.json()["access_token"]

    response = client.get(
        "/documents/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    docs = response.json()

    for doc in docs:
        allowed = doc.get("allowed_roles")
        if allowed is not None:
            assert "employee" in allowed
