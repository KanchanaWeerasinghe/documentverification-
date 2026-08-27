from backend.app.workers.celery_app import celery_app


@celery_app.task(bind=True)
def reference_ingest_task(self, reference_document_id: int, file_path: str, metadata: dict = None):
    """Celery task to run the reference ingestion workflow.

    The actual services are imported here to avoid worker startup ordering issues.
    """
    # local import to avoid import-time cycles
    from backend.app.domain.reference_ingestion_service import ReferenceIngestionService
    from backend.app.db.session import SessionLocal
    from backend.app.db.repositories.reference_repository import ReferenceRepository
    from backend.app.db.models.reference_document import ReferenceStatus

    db = SessionLocal()
    repo = ReferenceRepository(db)
    # mark as ingesting
    repo.update_status(reference_document_id, ReferenceStatus.INGESTING)

    try:
        service = ReferenceIngestionService()
        service.ingest(reference_document_id, file_path, metadata=metadata or {})
        repo.update_status(reference_document_id, ReferenceStatus.READY)
    except Exception as exc:
        repo.update_status(reference_document_id, ReferenceStatus.FAILED)
        raise
    finally:
        db.close()
    return True
