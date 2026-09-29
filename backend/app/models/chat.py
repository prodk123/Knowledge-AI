"""Chat models — Pydantic schemas for query/response."""

import uuid

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Incoming chat/query request."""
    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Natural language question to ask against the document corpus.",
        examples=["What is the annual leave policy?"],
    )


class SourceReference(BaseModel):
    """A source document chunk that contributed to the answer."""
    document_id: str
    filename: str
    page_number: int | None = None
    section: str | None = None
    chunk_id: str
    score: float
    text_preview: str = Field(
        description="First ~200 chars of the chunk text for verification."
    )


class ChatResponse(BaseModel):
    """Response containing the generated answer and source references."""
    answer: str
    sources: list[SourceReference]
    is_async: bool = False
    job_id: str | None = None


class RetrievalResult(BaseModel):
    """Internal model for a single retrieval result from the vector store."""
    chunk_id: str
    document_id: str
    text: str
    score: float | None = None
    # --- Stage 2 Tracking Fields ---
    dense_score: float | None = None
    dense_rank: int | None = None
    bm25_score: float | None = None
    bm25_rank: int | None = None
    rrf_score: float | None = None
    rrf_rank: int | None = None
    reranker_score: float | None = None
    final_rank: int | None = None
    retriever: str | None = None
    metadata: dict

    @property
    def filename(self) -> str:
        return self.metadata.get("filename", "unknown")

    @property
    def page_number(self) -> int | None:
        return self.metadata.get("page_number")

    @property
    def section(self) -> str | None:
        return self.metadata.get("section")

    def to_source_reference(self) -> SourceReference:
        return SourceReference(
            document_id=self.document_id,
            filename=self.filename,
            page_number=self.page_number,
            section=self.section,
            chunk_id=self.chunk_id,
            score=round(self.score, 4) if self.score is not None else 0.0,
            text_preview=self.text[:200],
        )
