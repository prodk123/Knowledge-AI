"""Ingestion service — orchestrates document parsing, chunking, and embedding."""

import logging
import shutil
from pathlib import Path

from fastapi import UploadFile

from app.core.config import Settings
from app.db.repositories.document_repository import DocumentRepository
from app.models.document import DocumentRecord, DocumentStatus
from app.rag.chunker import DocumentChunker
from app.rag.embeddings import EmbeddingProvider
from app.rag.parser import DocumentParser
from app.rag.vector_store import QdrantVectorStore
from app.rag.bm25_retriever import BM25Retriever

logger = logging.getLogger(__name__)


class IngestionService:
    """Orchestrates the ingestion pipeline for a document.

    Upload -> Save -> Parse -> Chunk -> Embed -> Qdrant -> Update DB
    """

    def __init__(
        self,
        settings: Settings,
        embedding_provider: EmbeddingProvider,
        vector_store: QdrantVectorStore,
        bm25_retriever: BM25Retriever,
    ):
        self.settings = settings
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.bm25_retriever = bm25_retriever
        
        # Instantiate parser and chunker locally since they don't hold heavy state
        self.parser = DocumentParser()
        self.chunker = DocumentChunker(
            chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap
        )
        
        self.upload_dir = Path(settings.upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def process_upload(
        self, file: UploadFile, repository: DocumentRepository
    ) -> DocumentRecord:
        """Process an uploaded document end-to-end.

        Note: In Stage 1, this is synchronous blocking the API request.
        For production with large files, this would be moved to Celery/background tasks.
        """
        logger.info("Starting ingestion for file: %s", file.filename)

        if not file.filename:
            raise ValueError("File must have a filename")

        file_type = Path(file.filename).suffix.lower()
        file_size = file.size or 0

        # 1. Save file to disk securely
        # Using a sanitized filename to prevent path traversal
        safe_filename = file.filename.replace("/", "").replace("\\", "")
        file_path = self.upload_dir / safe_filename
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 2. Create database record
        doc_record = await repository.create(
            filename=safe_filename,
            original_filename=file.filename,
            file_type=file_type,
            file_size=file_size,
            storage_path=str(file_path),
        )

        # 3. Update status to processing
        await repository.update_status(doc_record.id, DocumentStatus.PROCESSING)

        try:
            # 4. Parse document
            parsed_doc = self.parser.parse(file_path)

            # 5. Chunk document
            chunks = self.chunker.chunk_document(
                text=parsed_doc.text,
                document_id=str(doc_record.id),
                filename=doc_record.original_filename,
                pages=parsed_doc.pages,
            )

            if not chunks:
                raise RuntimeError("Document parsing resulted in zero chunks.")

            # 6. Deduplicate existing chunks if document is being re-ingested
            # (In Stage 1 we didn't track chunk lifecycle well, but in Stage 2 we must
            # clear old chunks from BM25. Qdrant upserts will overwrite if IDs match, but 
            # if chunk IDs change, we'd leak chunks. For simplicity, we remove by doc_id.)
            self.bm25_retriever.remove_document_chunks(document_id=str(doc_record.id))
            # Qdrant client delete payload or points by doc_id is possible, but we'll 
            # rely on upserts using consistent UUID generation in DocumentChunker for now.

            # 7. Generate embeddings
            texts_to_embed = [chunk.text for chunk in chunks]
            embeddings = self.embedding_provider.embed_documents(texts_to_embed)

            # 8. Store in Qdrant
            self.vector_store.store_chunks(chunks=chunks, embeddings=embeddings)

            # 9. Store in BM25
            self.bm25_retriever.add_chunks(chunks)

            # 10. Mark as processed
            await repository.update_status(
                doc_record.id, DocumentStatus.PROCESSED, chunk_count=len(chunks)
            )
            
            logger.info("Ingestion complete for %s", file.filename)
            return await repository.get_by_id(doc_record.id)

        except Exception as e:
            logger.error("Ingestion failed for %s: %s", file.filename, e)
            await repository.update_status(
                doc_record.id, DocumentStatus.FAILED, error_message=str(e)
            )
            # Re-raise to let the API layer handle the HTTP response
            raise
