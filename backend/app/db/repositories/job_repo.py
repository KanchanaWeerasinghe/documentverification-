from typing import List, Dict, Any
from sqlalchemy.orm import Session
from backend.app.db.models.job import Job, JobStage
from backend.app.db.models.document import Document
from backend.app.db.models.reference_document import ReferenceDocument


class JobRepository:
	def __init__(self, db: Session):
		self.db = db

	def create_job(self, user_id: int, primary_document_id: int, reference_document_id: int) -> Job:
		job = Job(
			primary_document_id=primary_document_id,
			reference_document_id=reference_document_id,
			user_id=user_id,
			status="QUEUED",
			current_stage=None,
		)
		self.db.add(job)
		self.db.commit()
		self.db.refresh(job)
		return job

	def update_stage(self, job_id: int, stage: str, status: str, error: str = None, metadata: Dict[str, Any] = None):
		from datetime import datetime, timezone
		job = self.db.query(Job).filter(Job.id == job_id).first()
		if not job:
			return None
		job.current_stage = stage
		job.status = status
		self.db.add(job)
		# also record a JobStage row
		now = datetime.now(timezone.utc)
		js = JobStage(
			job_id=job_id,
			name=stage,
			status=status,
			error=error,
			meta=metadata,
			started_at=now if status == "STARTED" else None,
			completed_at=now if status in {"COMPLETED", "FAILED"} else None,
		)
		self.db.add(js)
		self.db.commit()
		self.db.refresh(job)
		return js

	def get_job(self, job_id: int) -> Job:
		return self.db.query(Job).filter(Job.id == job_id).first()

	def list_job_stages(self, job_id: int) -> List[JobStage]:
		return self.db.query(JobStage).filter(JobStage.job_id == job_id).all()

