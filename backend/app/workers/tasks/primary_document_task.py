from backend.app.workers.celery_app import celery_app


@celery_app.task(bind=True)
def primary_document_pipeline(self, job_id: int):
    """Orchestrate primary document processing for a given job_id."""
    # local imports to avoid startup ordering
    from backend.app.domain.document_verification_service import DocumentVerificationService

    try:
        svc = DocumentVerificationService()
        svc.start_job(job_id)
    except Exception:
        # ensure job stage updated inside service; re-raise
        raise
    return True
