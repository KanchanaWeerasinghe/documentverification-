from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
import hashlib
import mimetypes
import os
from pathlib import Path

from backend.app.db.session import SessionLocal
from backend.app.db.repositories.document_repo import DocumentRepository
from backend.app.db.repositories.job_repo import JobRepository
from backend.app.workers.tasks.primary_document_task import primary_document_pipeline

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/primary-documents", status_code=202)
async def upload_primary(
    reference_id: int = Query(...),
    db: Session = Depends(get_db),
):
    default_data_dir = Path(__file__).resolve().parents[4] / "data" / "primary"
    data_dir = Path(os.getenv("PRIMARY_STORAGE_PATH", str(default_data_dir)))
    primary_files = sorted(
        file_path
        for file_path in data_dir.iterdir()
        if file_path.is_file() and file_path.suffix.lower() in {".docx", ".pdf"}
    ) if data_dir.is_dir() else []
    if not primary_files:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No DOCX or PDF primary document found in {data_dir}",
        )

    primary_file = primary_files[0]
    filename = primary_file.name
    mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

    # compute content hash
    hasher = hashlib.sha256()
    with primary_file.open("rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            hasher.update(chunk)
    content_hash = hasher.hexdigest()

    repo = DocumentRepository(db)
    doc = repo.create_document(filename=filename, user_id=1, mime_type=mime_type, content_hash=content_hash)

    # create a job record and dispatch a Celery task after commit
    jr = JobRepository(db)
    job = jr.create_job(user_id=1, primary_document_id=doc.id, reference_document_id=reference_id)

    # dispatch Celery task
    task = primary_document_pipeline.delay(job.id)

    return {"job_id": job.id, "document_id": doc.id, "status": "queued", "task_id": task.id}
