import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
from app.main import app

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

def test_health_check_mocked(client):
    # We use TestClient but since we don't have DB/Qdrant running in this basic test env, 
    # the health check will return 'degraded' or we mock it.
    
    with patch("app.main.check_db_connection", new_callable=AsyncMock) as mock_db:
        mock_db.return_value = True
        
        with patch("app.main.get_vector_store") as mock_vs:
            mock_client = MagicMock()
            mock_vs.return_value.client = mock_client
            
            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert data["database"] == "connected"
            assert data["qdrant"] == "connected"

def test_chat_endpoint_validation(client):
    # Since chat is protected, we must mock get_current_user to test Pydantic validation
    from app.models.auth import User
    from app.api.auth import get_current_user
    
    mock_user = User(email="test@example.com", is_active=True)
    app.dependency_overrides[get_current_user] = lambda: mock_user
    
    try:
        # Missing question
        response = client.post("/chat/", json={})
        assert response.status_code == 422
        
        # Empty question
        response = client.post("/chat/", json={"question": ""})
        assert response.status_code == 422
    finally:
        del app.dependency_overrides[get_current_user]
    
    # Valid schema (but will fail processing since we don't mock the pipeline here)
    # We just want to check Pydantic validation passes
    with patch("app.api.chat.RAGPipeline") as MockPipeline:
        # Override the dependency
        pass
