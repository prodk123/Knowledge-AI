"""Document models — SQLAlchemy ORM and Pydantic schemas."""

import enum
import uuid
from datetime import datetime

from pydantic import BaseModel, Field
from sqlalchemy import String, Integer, DateTime, Text, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


# =============================================================================
# Enums
# =============================================================================

class DocumentStatus(str, enum.Enum):
    """Processing states for an uploaded document."""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


# =============================================================================
# SQLAlchemy ORM Model
# =============================================================================

class DocumentRecord(Base):
    """PostgreSQL table for document metadata.

    Designed for future extensibility — fields like department,
    classification, allowed_roles, owner_id can be added cleanly.
    """

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=DocumentStatus.UPLOADED.value
    )
    chunk_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # --- RBAC extension points ---
    allowed_roles: Mapped[list[str] | None] = mapped_column(
        postgresql.ARRAY(String), nullable=True
    )


# =============================================================================
# Pydantic Response Schemas
# =============================================================================

class DocumentUploadResponse(BaseModel):
    """Response after uploading a document."""
    document_id: uuid.UUID
    filename: str
    status: str

    model_config = {"from_attributes": True}


class DocumentStatusResponse(BaseModel):
    """Response for document status queries."""
    document_id: uuid.UUID = Field(alias="id")
    filename: str
    original_filename: str
    file_type: str
    file_size: int
    status: str
    chunk_count: int | None = None
    error_message: str | None = None
    allowed_roles: list[str] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}
