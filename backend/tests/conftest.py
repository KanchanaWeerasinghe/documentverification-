from fastapi.testclient import TestClient
import os
import pytest
from types import SimpleNamespace


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Use a temp directory for uploaded references
    storage = tmp_path / "references"
    os.environ["REFERENCE_STORAGE_PATH"] = str(storage)

    # Monkeypatch the repository and the Celery task used by the endpoint
    import backend.app.api.v1.endpoints.references as refs_module

    class FakeRepo:
        def __init__(self, db):
            pass

        def create_reference(self, filename, uploader_user_id, mime_type, content_hash, revision=None, effective_date=None):
            return SimpleNamespace(id=1)

        def update_status(self, *args, **kwargs):
            return None

        def insert_chunks(self, *args, **kwargs):
            return []

    monkeypatch.setattr(refs_module, "ReferenceRepository", FakeRepo)

    # fake Celery task object with .delay()
    def fake_delay(*args, **kwargs):
        return SimpleNamespace(id="dummy-task-id")

    monkeypatch.setattr(refs_module, "reference_ingest_task", SimpleNamespace(delay=fake_delay))

    # Create TestClient for the ASGI app
    from backend.app.main import app

    client = TestClient(app)
    return client
