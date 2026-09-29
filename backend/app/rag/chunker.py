"""Document chunker — split parsed documents into meaningful chunks.

Respects document structure (Markdown headings) rather than blindly
splitting at fixed character boundaries.
"""

import logging
import re
import uuid
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class DocumentChunk:
    """A single chunk of text with metadata."""
    chunk_id: str
    document_id: str
    text: str
    filename: str
    page_number: int | None = None
    section: str | None = None
    chunk_index: int = 0
    metadata: dict = field(default_factory=dict)


class DocumentChunker:
    """Split parsed documents into chunks suitable for embedding.

    Strategy:
    1. Split on Markdown headings (##, ###) to preserve section boundaries.
    2. Within sections, use recursive character splitting with overlap.
    3. Attach metadata (document_id, filename, section, page_number) to each chunk.

    This ensures chunks respect document structure rather than being
    arbitrary character slices.
    """

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if chunk_overlap < 0:
            raise ValueError("chunk_overlap must be non-negative")
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_document(
        self,
        text: str,
        document_id: str,
        filename: str,
        pages: list[str] | None = None,
        allowed_roles: list[str] | None = None,
    ) -> list[DocumentChunk]:
        """Split document text into chunks with metadata.

        Args:
            text: Full document text (Markdown format preferred).
            document_id: UUID of the parent document.
            filename: Original filename.
            pages: Optional list of page texts for page number mapping.
            allowed_roles: Optional list of roles allowed to access this document.

        Returns:
            List of DocumentChunk objects with metadata.
        """
        if not text or not text.strip():
            return []

        sections = self._split_into_sections(text)
        chunks: list[DocumentChunk] = []
        chunk_index = 0

        for section_title, section_text in sections:
            if not section_text.strip():
                continue

            # Split section text into smaller chunks if needed
            text_chunks = self._recursive_split(section_text)

            for chunk_text in text_chunks:
                if not chunk_text.strip():
                    continue

                page_number = self._estimate_page_number(chunk_text, pages)
                
                metadata = {
                    "document_id": document_id,
                    "filename": filename,
                    "section": section_title,
                    "page_number": page_number,
                    "source": filename,
                }
                if allowed_roles is not None:
                    metadata["allowed_roles"] = allowed_roles

                chunk = DocumentChunk(
                    chunk_id=str(uuid.uuid4()),
                    document_id=document_id,
                    text=chunk_text.strip(),
                    filename=filename,
                    page_number=page_number,
                    section=section_title,
                    chunk_index=chunk_index,
                    metadata=metadata,
                )
                chunks.append(chunk)
                chunk_index += 1

        logger.info(
            "Chunked document %s into %d chunks (chunk_size=%d, overlap=%d)",
            filename, len(chunks), self.chunk_size, self.chunk_overlap,
        )
        return chunks

    def _split_into_sections(self, text: str) -> list[tuple[str | None, str]]:
        """Split text by Markdown headings to preserve document structure.

        Returns list of (section_title, section_text) tuples.
        """
        # Match Markdown headings (## or ###)
        heading_pattern = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)
        matches = list(heading_pattern.finditer(text))

        if not matches:
            return [(None, text)]

        sections: list[tuple[str | None, str]] = []

        # Text before first heading
        if matches[0].start() > 0:
            preamble = text[: matches[0].start()].strip()
            if preamble:
                sections.append((None, preamble))

        # Each heading and its content
        for i, match in enumerate(matches):
            title = match.group(2).strip()
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            content = text[start:end].strip()

            # Include the heading in the content for context
            full_content = f"{match.group(0).strip()}\n\n{content}" if content else match.group(0).strip()
            sections.append((title, full_content))

        return sections

    def _recursive_split(self, text: str) -> list[str]:
        """Recursively split text into chunks respecting natural boundaries.

        Tries to split on (in order): double newlines, single newlines,
        sentences, then characters.
        """
        if len(text) <= self.chunk_size:
            return [text]

        separators = ["\n\n", "\n", ". ", " "]
        return self._split_with_separators(text, separators)

    def _split_with_separators(
        self, text: str, separators: list[str]
    ) -> list[str]:
        """Split text using a hierarchy of separators."""
        if len(text) <= self.chunk_size:
            return [text]

        if not separators:
            # Last resort: hard split at chunk_size
            return self._hard_split(text)

        separator = separators[0]
        remaining_separators = separators[1:]

        parts = text.split(separator)
        chunks: list[str] = []
        current_chunk = ""

        for part in parts:
            candidate = (
                current_chunk + separator + part if current_chunk else part
            )

            if len(candidate) <= self.chunk_size:
                current_chunk = candidate
            else:
                if current_chunk:
                    chunks.append(current_chunk)

                if len(part) > self.chunk_size:
                    # Recursively split with finer separators
                    sub_chunks = self._split_with_separators(
                        part, remaining_separators
                    )
                    chunks.extend(sub_chunks[:-1])
                    current_chunk = sub_chunks[-1] if sub_chunks else ""
                else:
                    current_chunk = part

        if current_chunk:
            chunks.append(current_chunk)

        # Apply overlap
        return self._apply_overlap(chunks)

    def _hard_split(self, text: str) -> list[str]:
        """Split text at exact character boundaries (last resort)."""
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            chunks.append(text[start:end])
            start = end - self.chunk_overlap if end < len(text) else end
        return chunks

    def _apply_overlap(self, chunks: list[str]) -> list[str]:
        """Apply overlap between adjacent chunks for context continuity."""
        if self.chunk_overlap == 0 or len(chunks) <= 1:
            return chunks

        overlapped: list[str] = [chunks[0]]
        for i in range(1, len(chunks)):
            prev = chunks[i - 1]
            overlap_text = prev[-self.chunk_overlap :] if len(prev) > self.chunk_overlap else prev
            overlapped.append(overlap_text + chunks[i])

        return overlapped

    def _estimate_page_number(
        self, chunk_text: str, pages: list[str] | None
    ) -> int | None:
        """Estimate which page a chunk belongs to based on text overlap."""
        if not pages or len(pages) <= 1:
            return 1

        best_page = 1
        best_overlap = 0

        for i, page_text in enumerate(pages, start=1):
            if not page_text:
                continue
            # Simple heuristic: count shared words
            chunk_words = set(chunk_text.lower().split()[:20])
            page_words = set(page_text.lower().split())
            overlap = len(chunk_words & page_words)
            if overlap > best_overlap:
                best_overlap = overlap
                best_page = i

        return best_page
