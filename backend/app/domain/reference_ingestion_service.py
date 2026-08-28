from typing import List, Dict, Any
from backend.app.db.repositories.reference_repository import ReferenceRepository
from backend.app.db.session import SessionLocal
from sentence_transformers import SentenceTransformer
from docx import Document as DocxDocument
import os
from backend.app.ingestion.text_cleaner import clean_paragraphs


class ReferenceIngestionService:
    """Performs the ingestion workflow for a reference document.

    Steps:
    1. parse document into structured sections/monographs
    2. detect monograph boundaries (structure detection)
    3. chunk monographs into chunks with metadata
    4. compute embeddings and persist chunks via ReferenceIndexService
    5. validate indexing and mark reference ready
    """

    def ingest(self, reference_document_id: int, file_path: str, metadata: Dict[str, Any] = None) -> None:
        """Run ingestion for the given stored reference document.

        Typically invoked inside a worker (Celery task).
        """
        # Basic implementation: parse DOCX, detect monographs by headings, chunk per monograph,
        # compute embeddings and persist chunks.
        db = SessionLocal()
        repo = ReferenceRepository(db)

        # parse
        parsed = self.parse_document(file_path)
        monographs = self.detect_structure(parsed)

        # chunk and embed using structure-aware chunking
        chunks_to_store = []
        texts = []
        for mon in monographs:
            child_chunks = self.chunk_monograph(mon)
            for idx, cc in enumerate(child_chunks):
                content = cc.get("content")
                metadata = cc.get("metadata", {})
                # enrich metadata with source
                metadata.setdefault("source", os.path.basename(file_path))
                metadata.setdefault("chunk_index", idx)
                chunk = {
                    "monograph_name": mon.get("title"),
                    "section": mon.get("section"),
                    "page": mon.get("page"),
                    "content": content,
                    "metadata": metadata,
                }
                chunks_to_store.append(chunk)
                texts.append(content)

        # embeddings
        model_name = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        embedder = SentenceTransformer(model_name)
        vectors = embedder.encode(texts, show_progress_bar=False)

        for i, vec in enumerate(vectors):
            if hasattr(vec, "tolist"):
                chunks_to_store[i]["embedding"] = vec.tolist()
            else:
                chunks_to_store[i]["embedding"] = list(vec)

        # persist
        repo.insert_chunks(reference_document_id, chunks_to_store)

        db.close()

    def parse_document(self, file_path: str) -> Dict[str, Any]:
        """Parse DOCX/PDF into structured representation (sections, paragraphs, pages)."""
        # For MVP, support DOCX only using python-docx
        if file_path.lower().endswith('.docx'):
            doc = DocxDocument(file_path)
            paragraphs = clean_paragraphs(p.text for p in doc.paragraphs)
            return {"paragraphs": paragraphs}
        else:
            # PDF support could be added later
            raise ValueError("Unsupported reference document format; only DOCX supported in MVP")

    def detect_structure(self, parsed: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect monograph boundaries and return a list of monographs with metadata."""
        paragraphs = parsed.get("paragraphs", [])
        monographs = []
        current = None
        for p in paragraphs:
            # Heuristic: treat short lines (<=4 words) starting with Title-Case as monograph titles
            words = p.split()
            if (
                0 < len(words) <= 6
                and words[0][0].isupper()
                and ":" not in p
                and p.isprintable()
            ):
                # start new monograph
                if current:
                    monographs.append(current)
                current = {"title": p.strip(), "paragraphs": []}
            else:
                if current is None:
                    # skip leading content or attach to unnamed section
                    current = {"title": "__preamble__", "paragraphs": []}
                current["paragraphs"].append(p)

        if current:
            monographs.append(current)

        # attach section/page defaults minimally
        for m in monographs:
            m.setdefault("section", None)
            m.setdefault("page", None)

        return monographs

    def chunk_monograph(self, monograph: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Chunk a monograph into semantic chunks.

        Policy:
        - Treat the monograph as the primary semantic unit.
        - If the monograph length <= CHAR_LIMIT, keep it whole.
        - Otherwise, split at detected field/section boundaries (paragraph headers,
          lines ending with ':' or short ALL-Caps headings). Group adjacent fields
          into chunks not exceeding CHAR_LIMIT. Never split inside a paragraph.
        - Preserve `medication_name` (monograph title) in metadata for every chunk.

        Returns a list of dicts: {"content": str, "metadata": { ... }}
        """
        CHAR_LIMIT = 3000
        title = monograph.get("title") or ""
        paragraphs = monograph.get("paragraphs", [])

        # Fast path: whole monograph fits
        full = "\n".join(paragraphs).strip()
        if not full:
            return []
        if len(full) <= CHAR_LIMIT:
            return [{
                "content": full,
                "metadata": {"medication_name": title, "parent_monograph": title}
            }]

        # Heuristic: detect field boundaries (paragraphs that look like headings)
        fields = []  # list of (heading, [paras]) where heading may be None for initial body
        current_heading = None
        current_paras = []

        def is_heading(p: str) -> bool:
            p_stripped = p.strip()
            if not p_stripped:
                return False
            # ends with ':' or is short (<=6 words) and mostly Title-Case or UPPER
            if p_stripped.endswith(":"):
                return True
            words = p_stripped.split()
            if 0 < len(words) <= 6:
                # detect ALL CAPS headings or Title Case single-line headings
                if p_stripped.upper() == p_stripped:
                    return True
                # title-case heuristic: first char upper and contains a noun-like word
                if words[0][0].isupper():
                    return True
            return False

        for p in paragraphs:
            if is_heading(p):
                # start a new field
                if current_paras:
                    fields.append((current_heading, current_paras))
                current_heading = p.strip().rstrip(":")
                current_paras = []
            else:
                current_paras.append(p)

        if current_paras:
            fields.append((current_heading, current_paras))

        # Now group fields into chunks not exceeding CHAR_LIMIT
        chunks: List[Dict[str, Any]] = []
        buffer_parts: List[str] = []
        buffer_size = 0
        chunk_index = 0

        def flush_buffer():
            nonlocal buffer_parts, buffer_size, chunk_index
            if not buffer_parts:
                return
            content = "\n".join(buffer_parts).strip()
            chunks.append({
                "content": content,
                "metadata": {
                    "medication_name": title,
                    "parent_monograph": title,
                    "chunk_index": chunk_index,
                },
            })
            chunk_index += 1
            buffer_parts = []
            buffer_size = 0

        for heading, paras in fields:
            # represent the field as heading + paras
            field_parts = []
            if heading:
                field_parts.append(heading)
            field_parts.extend(paras)
            field_text = "\n".join(field_parts).strip()
            if not field_text:
                continue

            if len(field_text) > CHAR_LIMIT:
                # giant field: split by paragraph boundaries within this field
                sub_buffer: List[str] = []
                sub_size = 0
                for p in field_parts:
                    plen = len(p)
                    if sub_size + plen > CHAR_LIMIT and sub_buffer:
                        chunks.append({
                            "content": "\n".join(sub_buffer).strip(),
                            "metadata": {"medication_name": title, "parent_monograph": title, "chunk_index": chunk_index},
                        })
                        chunk_index += 1
                        sub_buffer = []
                        sub_size = 0
                    sub_buffer.append(p)
                    sub_size += plen
                if sub_buffer:
                    chunks.append({
                        "content": "\n".join(sub_buffer).strip(),
                        "metadata": {"medication_name": title, "parent_monograph": title, "chunk_index": chunk_index},
                    })
                    chunk_index += 1
                continue

            # fit field_text into buffer
            if buffer_size + len(field_text) <= CHAR_LIMIT:
                # add heading if present
                if heading:
                    buffer_parts.append(heading)
                    buffer_size += len(heading)
                buffer_parts.extend(paras)
                buffer_size += len(field_text)
            else:
                # flush and start new buffer
                flush_buffer()
                if heading:
                    buffer_parts.append(heading)
                    buffer_size += len(heading)
                buffer_parts.extend(paras)
                buffer_size += len(field_text)

        flush_buffer()
        return chunks
