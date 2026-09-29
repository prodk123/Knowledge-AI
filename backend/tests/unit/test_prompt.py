import pytest
from app.rag.prompt import ContextBuilder
from app.models.chat import RetrievalResult

def test_build_prompt_empty_context():
    builder = ContextBuilder()
    messages = builder.build_prompt("What is the policy?", contexts=[])
    
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "No relevant documents found." in messages[1]["content"]
    assert "What is the policy?" in messages[1]["content"]

def test_build_prompt_with_context():
    builder = ContextBuilder()
    ctx1 = RetrievalResult(
        chunk_id="chunk1",
        document_id="doc1",
        text="Annual leave is 20 days.",
        score=0.9,
        metadata={"filename": "hr.md", "section": "Leave", "page_number": 1}
    )
    
    messages = builder.build_prompt("How much leave?", contexts=[ctx1])
    
    assert len(messages) == 2
    user_msg = messages[1]["content"]
    assert "hr.md" in user_msg
    assert "Section: Leave" in user_msg
    assert "Page: 1" in user_msg
    assert "Annual leave is 20 days." in user_msg
    assert "How much leave?" in user_msg
