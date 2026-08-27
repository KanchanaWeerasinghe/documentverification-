from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.db.models.result import VerificationResultModel
from backend.app.db.session import SessionLocal

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/jobs/{job_id}/results")
def get_results(job_id: int, db: Session = Depends(get_db)):
    results = (
        db.query(VerificationResultModel)
        .filter(VerificationResultModel.job_id == job_id)
        .order_by(VerificationResultModel.id)
        .all()
    )
    return {"job_id": job_id, "results": [
        {
            "medication_name": result.medication_name,
            "status": result.status,
            "comparisons": result.comparisons or [],
            "explanation": result.explanation,
            "evidence": result.evidence,
        }
        for result in results
    ]}