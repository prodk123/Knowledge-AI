import pytest
from app.rag.chunker import DocumentChunker


def test_chunker_initialization():
    chunker = DocumentChunker(chunk_size=100, chunk_overlap=20)
    assert chunker.chunk_size == 100
    assert chunker.chunk_overlap == 20


def test_chunker_invalid_params():
    with pytest.raises(ValueError):
        DocumentChunker(chunk_size=0)

    with pytest.raises(ValueError):
        DocumentChunker(chunk_size=100, chunk_overlap=100)

    with pytest.raises(ValueError):
        DocumentChunker(chunk_size=100, chunk_overlap=-1)


def test_split_into_sections_with_preamble():
    chunker = DocumentChunker(chunk_size=1000)
    text = "Preamble text.\n\n## Section 1\nContent 1.\n\n### Section 1.1\nSubcontent."

    sections = chunker._split_into_sections(text)
    # Preamble + 2 headings = 3 sections
    assert len(sections) == 3
    assert sections[0][0] is None  # preamble has no title
    assert "Preamble text" in sections[0][1]
    assert sections[1][0] == "Section 1"
    assert sections[2][0] == "Section 1.1"


def test_split_into_sections_no_headings():
    chunker = DocumentChunker(chunk_size=1000)
    text = "Just plain text without any headings."

    sections = chunker._split_into_sections(text)
    assert len(sections) == 1
    assert sections[0][0] is None
    assert sections[0][1] == text


def test_chunk_document_basic():
    chunker = DocumentChunker(chunk_size=500, chunk_overlap=50)
    text = "## Leave Policy\nEmployees get 20 days of annual leave."

    chunks = chunker.chunk_document(
        text=text,
        document_id="doc1",
        filename="test.md",
    )

    assert len(chunks) == 1
    assert chunks[0].section == "Leave Policy"
    assert chunks[0].document_id == "doc1"
    assert chunks[0].filename == "test.md"
    assert "20 days" in chunks[0].text


def test_chunk_document_empty_text():
    chunker = DocumentChunker(chunk_size=100, chunk_overlap=20)
    chunks = chunker.chunk_document(text="", document_id="doc1", filename="empty.md")
    assert chunks == []


def test_chunk_document_metadata():
    chunker = DocumentChunker(chunk_size=500, chunk_overlap=50)
    text = "## Finance\nExpense reimbursement policy details."

    chunks = chunker.chunk_document(
        text=text,
        document_id="doc-uuid-123",
        filename="finance.md",
    )

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.metadata["document_id"] == "doc-uuid-123"
    assert chunk.metadata["filename"] == "finance.md"
    assert chunk.metadata["section"] == "Finance"
    assert chunk.chunk_id  # UUID should be assigned
