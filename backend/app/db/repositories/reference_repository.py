from typing import List, Dict, Any
from sqlalchemy.orm import Session
from backend.app.db.models.reference_document import ReferenceDocument, ReferenceStatus
from backend.app.db.models.reference_chunk import ReferenceChunk


class ReferenceRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_reference(self, filename: str, uploader_user_id: int, mime_type: str, content_hash: str, revision: str = None, effective_date: str = None) -> ReferenceDocument:
        ref = ReferenceDocument(
            filename=filename,
            uploader_user_id=uploader_user_id,
            mime_type=mime_type,
            content_hash=content_hash,
            status=ReferenceStatus.PENDING,
            revision=revision,
            effective_date=effective_date,
        )
        self.db.add(ref)
        self.db.commit()
        self.db.refresh(ref)
        return ref

    def update_status(self, reference_id: int, status: ReferenceStatus):
        ref = self.db.query(ReferenceDocument).filter(ReferenceDocument.id == reference_id).first()
        if not ref:
            return None
        ref.status = status
        self.db.add(ref)
        self.db.commit()
        self.db.refresh(ref)
        return ref

    def insert_chunks(self, reference_id: int, chunks: List[Dict[str, Any]]):
        objs = []
        for c in chunks:
            obj = ReferenceChunk(
                reference_document_id=reference_id,
                monograph_name=c.get("monograph_name"),
                section=c.get("section"),
                page=c.get("page"),
                content=c.get("content"),
                embedding=c.get("embedding"),
                meta=c.get("metadata"),
            )
            objs.append(obj)
            self.db.add(obj)
        self.db.commit()
        return objs

    def get_chunks_by_reference(self, reference_id: int):
        return self.db.query(ReferenceChunk).filter(ReferenceChunk.reference_document_id == reference_id).all()
