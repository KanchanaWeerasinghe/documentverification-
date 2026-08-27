from __future__ import annotations
import os
from celery import Celery

# Celery configuration: broker/url read from env
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)

celery_app = Celery("document_verification")
celery_app.conf.broker_url = CELERY_BROKER_URL
celery_app.conf.result_backend = CELERY_RESULT_BACKEND

# Import task modules explicitly because the project uses descriptive module names
# rather than Celery's conventional tasks.py module name.
celery_app.conf.imports = (
	"backend.app.workers.tasks.reference_ingest_task",
	"backend.app.workers.tasks.primary_document_task",
)
