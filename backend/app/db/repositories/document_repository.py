"""Document repository — CRUD operations for document metadata in PostgreSQL."""

import uuid
import logging

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import DocumentRecord, DocumentStatus

logger = logging.getLogger(__name__)


class DocumentRepository:
    """Data access layer for document records."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        filename: str,
        original_filename: str,
        file_type: str,
        file_size: int,
        storage_path: str,
    ) -> DocumentRecord:
        """Create a new document metadata record."""
        record = DocumentRecord(
            id=uuid.uuid4(),
            filename=filename,
            original_filename=original_filename,
            file_type=file_type,
            file_size=file_size,
            storage_path=storage_path,
            status=DocumentStatus.UPLOADED.value,
        )
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        logger.info("Created document record: %s (%s)", record.id, original_filename)
        return record

    async def get_by_id(self, document_id: uuid.UUID, allowed_roles: list[str] | None = None) -> DocumentRecord | None:
        """Fetch a document record by its ID, optionally enforcing authorization."""
        stmt = select(DocumentRecord).where(DocumentRecord.id == document_id)
        if allowed_roles is not None:
            # Document is accessible if allowed_roles is NULL OR there is an overlap
            stmt = stmt.where(
                (DocumentRecord.allowed_roles.is_(None)) |
                (DocumentRecord.allowed_roles.overlap(allowed_roles))
            )
            
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_status(
        self,
        document_id: uuid.UUID,
        status: DocumentStatus,
        chunk_count: int | None = None,
        error_message: str | None = None,
    ) -> None:
        """Update the processing status of a document."""
        values: dict = {"status": status.value}
        if chunk_count is not None:
            values["chunk_count"] = chunk_count
        if error_message is not None:
            values["error_message"] = error_message

        await self.session.execute(
            update(DocumentRecord)
            .where(DocumentRecord.id == document_id)
            .values(**values)
        )
        await self.session.commit()
        logger.info("Updated document %s status to %s", document_id, status.value)

    async def list_all(self, allowed_roles: list[str] | None = None) -> list[DocumentRecord]:
        """List all document records, ordered by creation time, optionally enforcing authorization."""
        stmt = select(DocumentRecord).order_by(DocumentRecord.created_at.desc())
        
        if allowed_roles is not None:
            stmt = stmt.where(
                (DocumentRecord.allowed_roles.is_(None)) |
                (DocumentRecord.allowed_roles.overlap(allowed_roles))
            )
            
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_roles(self, document_id: uuid.UUID, allowed_roles: list[str]) -> DocumentRecord | None:
        """Update the RBAC allowed roles for a document."""
        stmt = select(DocumentRecord).where(DocumentRecord.id == document_id)
        result = await self.session.execute(stmt)
        record = result.scalar_one_or_none()
        
        if record:
            record.allowed_roles = allowed_roles
            await self.session.commit()
            await self.session.refresh(record)
            
        return record

    async def delete(self, document_id: uuid.UUID) -> bool:
        """Delete a document record from the database."""
        stmt = select(DocumentRecord).where(DocumentRecord.id == document_id)
        result = await self.session.execute(stmt)
        record = result.scalar_one_or_none()
        
        if record:
            await self.session.delete(record)
            await self.session.commit()
            return True
        return False
