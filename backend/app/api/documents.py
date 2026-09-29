"""API routes for document upload and management."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session, get_ingestion_service, get_current_user
from app.db.repositories.document_repository import DocumentRepository
from app.models.auth import User
from app.models.document import DocumentStatusResponse, DocumentUploadResponse
from app.services.ingestion_service import IngestionService

router = APIRouter(prefix="/documents", tags=["documents"])


def get_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)]
) -> DocumentRepository:
    return DocumentRepository(session)


@router.post("/upload", response_model=DocumentUploadResponse, status_code=202)
async def upload_document(
    file: Annotated[UploadFile, File(...)],
    ingestion_service: Annotated[IngestionService, Depends(get_ingestion_service)],
    repository: Annotated[DocumentRepository, Depends(get_repository)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Upload a document (PDF, TXT, MD, DOCX) for parsing and embedding."""
    
    # Check permission
    permissions = {p.name for r in current_user.roles for p in r.permissions}
    if "documents.upload" not in permissions:
        raise HTTPException(status_code=403, detail="Forbidden: missing documents.upload permission")

    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename missing")

    try:
        record = await ingestion_service.process_upload(file, repository)
        return DocumentUploadResponse(
            document_id=record.id,
            filename=record.original_filename,
            status=record.status,
        )
    except ValueError as e:
        # Client error (e.g., unsupported file type)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Server error during processing
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{document_id}", response_model=DocumentStatusResponse)
async def get_document_status(
    document_id: uuid.UUID,
    repository: Annotated[DocumentRepository, Depends(get_repository)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get the metadata and processing status of a specific document."""
    allowed_roles = [role.name for role in current_user.roles]
    record = await repository.get_by_id(document_id, allowed_roles=allowed_roles)
    if not record:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return record


@router.get("/", response_model=list[DocumentStatusResponse])
async def list_documents(
    repository: Annotated[DocumentRepository, Depends(get_repository)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """List all uploaded documents authorized for the user."""
    allowed_roles = [role.name for role in current_user.roles]
    records = await repository.list_all(allowed_roles=allowed_roles)
    return records


from pydantic import BaseModel

class UpdateDocumentRolesRequest(BaseModel):
    allowed_roles: list[str]

@router.patch("/{document_id}/roles", response_model=DocumentStatusResponse)
async def update_document_roles(
    document_id: uuid.UUID,
    request: UpdateDocumentRolesRequest,
    repository: Annotated[DocumentRepository, Depends(get_repository)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Update the RBAC allowed_roles for a document."""
    permissions = {p.name for r in current_user.roles for p in r.permissions}
    if "documents.manage" not in permissions:
        raise HTTPException(status_code=403, detail="Forbidden: missing documents.manage permission")
        
    record = await repository.update_roles(document_id, request.allowed_roles)
    if not record:
        raise HTTPException(status_code=404, detail="Document not found")
        
    return record


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: uuid.UUID,
    repository: Annotated[DocumentRepository, Depends(get_repository)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Delete a document and its embeddings (embeddings deletion assumes cascade or background cleanup)."""
    permissions = {p.name for r in current_user.roles for p in r.permissions}
    if "documents.delete" not in permissions and "documents.manage" not in permissions:
        raise HTTPException(status_code=403, detail="Forbidden: missing documents.delete permission")
        
    success = await repository.delete(document_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
