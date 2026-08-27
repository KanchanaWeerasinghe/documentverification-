from backend.app.db.session import SessionLocal
from backend.app.db.repositories.job_repo import JobRepository
from backend.app.domain.schemas import JobRecord, JobStage
from backend.app.db.models.job import Job
from datetime import datetime


class JobServiceImpl:
    def __init__(self):
        pass

    def create_job(self, user_id: int, primary_document_id: int, reference_document_id: int) -> JobRecord:
        db = SessionLocal()
        repo = JobRepository(db)
        job = repo.create_job(user_id=user_id, primary_document_id=primary_document_id, reference_document_id=reference_document_id)
        stages = []
        jr = JobRecord(job_id=job.id, primary_document_id=job.primary_document_id, reference_document_id=job.reference_document_id, user_id=job.user_id, status=job.status, current_stage=job.current_stage, stages=stages, created_at=job.created_at)
        db.close()
        return jr

    def update_stage(self, job_id: int, stage: str, status: str, error: str = None, metadata: dict = None) -> JobStage:
        db = SessionLocal()
        repo = JobRepository(db)
        js = repo.update_stage(job_id, stage, status, error=error, metadata=metadata)
        db.close()
        if js is None:
            raise ValueError("job not found")
        return JobStage(name=js.name, status=js.status, started_at=js.started_at, completed_at=js.completed_at, error=js.error, metadata=js.meta)

    def get_job(self, job_id: int) -> JobRecord:
        db = SessionLocal()
        repo = JobRepository(db)
        job = repo.get_job(job_id)
        if not job:
            db.close()
            raise ValueError("job not found")
        stages = repo.list_job_stages(job_id)
        jr = JobRecord(job_id=job.id, primary_document_id=job.primary_document_id, reference_document_id=job.reference_document_id, user_id=job.user_id, status=job.status, current_stage=job.current_stage, stages=[JobStage(name=s.name, status=s.status, started_at=s.started_at, completed_at=s.completed_at, error=s.error, metadata=s.meta) for s in stages], created_at=job.created_at)
        db.close()
        return jr

    def list_job_stages(self, job_id: int):
        db = SessionLocal()
        repo = JobRepository(db)
        stages = repo.list_job_stages(job_id)
        db.close()
        return [JobStage(name=s.name, status=s.status, started_at=s.started_at, completed_at=s.completed_at, error=s.error, metadata=s.meta) for s in stages]
