"""Seed real document content into Qdrant and BM25 for testing."""
import asyncio
import uuid
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

LEAVE_POLICY = """Company Leave Policy

1. Annual Leave
All full-time employees are entitled to 24 days of paid annual leave per calendar year. Leave accrues at a rate of 2 days per month. Unused leave can be carried forward up to a maximum of 10 days to the next calendar year.

2. Sick Leave
Employees are entitled to 12 days of paid sick leave per year. A medical certificate is required for absences exceeding 3 consecutive days. Unused sick leave cannot be carried forward or encashed.

3. Personal Leave
Employees may take up to 5 days of personal leave per year for personal emergencies or important personal matters. Prior approval from the reporting manager is required when possible.

4. Maternity and Paternity Leave
Female employees are entitled to 26 weeks of paid maternity leave. Male employees are entitled to 2 weeks of paid paternity leave. Leave must be applied for at least 4 weeks in advance.

5. How to Apply for Leave
To apply for leave, employees should submit a leave request through the HR portal at least 3 business days in advance for planned leave. The request should include the type of leave, start date, end date, and reason. The reporting manager must approve the request. Emergency leave can be applied retroactively within 2 business days of return.

6. Public Holidays
The company observes 12 public holidays per year as per the official holiday calendar published at the start of each year.

7. Compensatory Off
Employees who work on public holidays or weekends with prior approval are entitled to compensatory off days. These must be availed within 30 days of the extra working day."""

FINANCE_POLICY = """Company Finance Policy

1. Expense Reimbursement
All business-related expenses must be submitted within 30 days via the expense management portal. Receipts are required for any expense above $25. Manager approval is needed for expenses above $500.

2. Travel Policy
Business travel requires pre-approval from the department head. Economy class is standard for flights under 6 hours. Hotel accommodations should not exceed $200/night unless in high-cost cities.

3. Budget Approvals
Department budgets are approved annually. Any expenditure exceeding 10% of the approved budget requires CFO approval. Capital expenditures above $10,000 require board approval."""


async def seed():
    from app.core.config import settings
    from app.db.database import async_session_factory
    from app.models.document import DocumentRecord, DocumentStatus
    from app.rag.chunker import DocumentChunker
    from app.rag.embeddings import get_embedding_provider
    from app.rag.vector_store import QdrantVectorStore
    from app.rag.bm25_retriever import BM25Retriever

    embedding_provider = get_embedding_provider(settings)
    vector_store = QdrantVectorStore(settings)
    bm25 = BM25Retriever(settings)
    chunker = DocumentChunker(chunk_size=500, chunk_overlap=50)

    documents = [
        ("employee_handbook.txt", LEAVE_POLICY, ["employee", "hr", "manager", "c_level", "admin"]),
        ("finance_policy.txt", FINANCE_POLICY, ["finance", "manager", "c_level", "admin"]),
    ]

    for filename, content, allowed_roles in documents:
        doc_id = str(uuid.uuid4())

        # Write file
        upload_dir = settings.upload_dir
        os.makedirs(upload_dir, exist_ok=True)
        filepath = os.path.join(upload_dir, f"{doc_id}_{filename}")
        with open(filepath, "w") as f:
            f.write(content)

        # Create DB record
        async with async_session_factory() as session:
            doc = DocumentRecord(
                id=uuid.UUID(doc_id),
                filename=f"{doc_id}_{filename}",
                original_filename=filename,
                file_type="text/plain",
                file_size=len(content),
                storage_path=filepath,
                status=DocumentStatus.PROCESSED.value,
                allowed_roles=allowed_roles,
            )
            session.add(doc)
            await session.commit()

        # Chunk
        chunks = chunker.chunk_document(
            text=content, document_id=doc_id, filename=filename, pages=[content], allowed_roles=allowed_roles
        )
        logger.info("Created %d chunks for %s", len(chunks), filename)

        # Embed
        texts = [c.text for c in chunks]
        embeddings = embedding_provider.embed_documents(texts)
        logger.info("Generated %d embeddings for %s", len(embeddings), filename)

        # Store in Qdrant
        vector_store.store_chunks(chunks=chunks, embeddings=embeddings)
        logger.info("Stored %s in Qdrant", filename)

        # Store in BM25
        bm25.add_chunks(chunks)
        logger.info("Stored %s in BM25", filename)

        # Update chunk count
        async with async_session_factory() as session:
            doc = await session.get(DocumentRecord, uuid.UUID(doc_id))
            doc.chunk_count = len(chunks)
            await session.commit()

        logger.info("Done indexing %s (id=%s)", filename, doc_id)

    logger.info("All documents seeded and indexed successfully!")


if __name__ == "__main__":
    asyncio.run(seed())
