import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from backend.app.db.models.reference_document import ReferenceDocument
from backend.app.db.models.job import Job, JobStage
from backend.app.db.session import SessionLocal
from backend.app.domain.document_verification_service import DocumentVerificationService
from backend.app.main import app


STAGES = tuple(DocumentVerificationService.STAGES)


def main():
    default_primary_dir = PROJECT_ROOT / "backend" / "data" / "primary"
    primary_dir = Path(os.getenv("PRIMARY_STORAGE_PATH", str(default_primary_dir)))
    timeout_seconds = int(os.getenv("PRIMARY_TEST_TIMEOUT", "300"))
    primary_files = sorted(
        file_path
        for file_path in primary_dir.iterdir()
        if file_path.is_file() and file_path.suffix.lower() in {".docx", ".pdf"}
    ) if primary_dir.is_dir() else []
    if not primary_files:
        raise FileNotFoundError(f"No DOCX or PDF primary document found in {primary_dir}")

    with SessionLocal() as db:
        reference_id = os.getenv("PRIMARY_REFERENCE_ID")
        if reference_id is None:
            reference = db.query(ReferenceDocument).order_by(ReferenceDocument.id.desc()).first()
            if reference is None:
                raise RuntimeError("No reference document exists; ingest a reference document first")
            reference_id = str(reference.id)

    print(f"Processing {primary_files[0].name} from {primary_dir}")
    response = TestClient(app).post(
        f"/api/v1/primary-documents?reference_id={reference_id}"
    )

    if response.status_code != 202:
        raise RuntimeError(f"Primary document request failed ({response.status_code}): {response.text}")

    payload = response.json()
    job_id = payload["job_id"]
    print(f"API returned 202; job_id={job_id}, task_id={payload['task_id']}")

    deadline = time.monotonic() + timeout_seconds
    last_stage = None
    while time.monotonic() < deadline:
        with SessionLocal() as db:
            job = db.query(Job).filter(Job.id == job_id).one()
            stages = db.query(JobStage).filter(JobStage.job_id == job_id).order_by(JobStage.id).all()
            stage_status = {stage.name: stage.status for stage in stages}
            completed = [stage for stage in STAGES if stage_status.get(stage) == "COMPLETED"]
            current = job.current_stage or "queued"
            if current != last_stage:
                print(f"{current}: {job.status} ({len(completed)}/{len(STAGES)} stages completed)")
                last_stage = current
            if job.status == "FAILED":
                error = next((stage.error for stage in reversed(stages) if stage.error), "unknown worker error")
                raise RuntimeError(f"Primary document job {job_id} failed at {current}: {error}")
            if job.status == "COMPLETED" and stage_status.get("done") == "COMPLETED":
                print("Primary document verification completed: DONE")
                return
        time.sleep(2)

    raise TimeoutError(f"Primary document job {job_id} did not reach DONE within {timeout_seconds} seconds")


if __name__ == "__main__":
    main()