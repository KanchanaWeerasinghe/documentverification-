from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import os
import hashlib
import posixpath
from pathlib import Path

from backend.app.db.session import SessionLocal
from backend.app.db.repositories.reference_repository import ReferenceRepository
from backend.app.workers.tasks.reference_ingest_task import reference_ingest_task

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/references", status_code=202)
async def ingest_reference(db: Session = Depends(get_db)):
    data_dir = Path(os.getenv("REFERENCE_STORAGE_PATH", "backend/data/references"))
    reference_files = sorted(data_dir.glob("*.docx"))
    if not reference_files:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No DOCX reference file found in {data_dir}",
        )

    reference_file = reference_files[0]
    filename = reference_file.name
    mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    # compute content hash
    hasher = hashlib.sha256()
    with reference_file.open("rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            hasher.update(chunk)
    content_hash = hasher.hexdigest()

    repo = ReferenceRepository(db)
    ref = repo.create_reference(filename=filename, uploader_user_id=1, mime_type=mime_type, content_hash=content_hash)

    # enqueue ingestion Celery task
    worker_data_dir = os.getenv("REFERENCE_WORKER_STORAGE_PATH", "/data/uploads")
    task_file_path = posixpath.join(worker_data_dir.replace("\\", "/"), filename)
    task = reference_ingest_task.delay(ref.id, str(task_file_path), {})

    return {"reference_id": ref.id, "ingest_job_id": task.id}
