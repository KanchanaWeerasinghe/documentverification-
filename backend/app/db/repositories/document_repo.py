from typing import List, Dict, Any
from sqlalchemy.orm import Session
from backend.app.db.models.document import Document, DocumentStatus
from backend.app.db.models.document_chunk import DocumentChunk


class DocumentRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_document(self, filename: str, user_id: int, mime_type: str, content_hash: str) -> Document:
        doc = Document(
            filename=filename,
            user_id=user_id,
            mime_type=mime_type,
            content_hash=content_hash,
            status=DocumentStatus.PENDING,
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def update_status(self, document_id: int, status: DocumentStatus):
        doc = self.db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            return None
        doc.status = status
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def insert_chunks(self, document_id: int, chunks: List[Dict[str, Any]]):
        objs = []
        for c in chunks:
            obj = DocumentChunk(
                document_id=document_id,
                page=c.get("page"),
                content=c.get("content"),
                embedding=c.get("embedding"),
                meta=c.get("metadata"),
            )
            objs.append(obj)
            self.db.add(obj)
        self.db.commit()
        return objs
