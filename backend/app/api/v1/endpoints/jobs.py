from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.db.models.job import Job
from backend.app.db.models.job import JobStage
from backend.app.db.session import SessionLocal

router = APIRouter()


def get_db():
	db = SessionLocal()
	try:
		yield db
	finally:
		db.close()


@router.get("/jobs/{job_id}")
def get_job_status(job_id: int, db: Session = Depends(get_db)):
	job = db.query(Job).filter(Job.id == job_id).first()
	if not job:
		raise HTTPException(status_code=404, detail="Job not found")
	stages = db.query(JobStage).filter(JobStage.job_id == job_id).order_by(JobStage.id).all()
	return {
		"job_id": job.id,
		"primary_document_id": job.primary_document_id,
		"reference_document_id": job.reference_document_id,
		"status": job.status,
		"current_stage": job.current_stage,
		"metadata": job.meta or {},
		"created_at": job.created_at,
		"stages": [
			{
				"name": stage.name,
				"status": stage.status,
				"started_at": stage.started_at,
				"completed_at": stage.completed_at,
				"error": stage.error,
				"metadata": stage.meta or {},
			}
			for stage in stages
		],
	}
