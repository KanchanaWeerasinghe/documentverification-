import os
import pytest
from types import SimpleNamespace
from fastapi.testclient import TestClient


def test_reference_ingest_end_to_end(monkeypatch):
    """End-to-end run of the reference ingestion pipeline against a real DOCX

    - Reads the first .docx file under `backend/data/references`
    - Runs `reference_ingest_task` (monkeypatched DB/repo/embedder)
    - Verifies: status updates, chunks inserted, embeddings present, metadata source preserved
    """

    base_dir = os.path.dirname(__file__)
    # backend/data/references
    data_dir = os.path.join(os.path.dirname(base_dir), "data", "references")
    if not os.path.isdir(data_dir):
        pytest.skip("No reference data directory; create backend/data/references with DOCX files to run this test")

    files = [f for f in os.listdir(data_dir) if f.lower().endswith(".docx")]
    if not files:
        pytest.skip("No .docx reference files found in backend/data/references")

    file_path = os.path.join(data_dir, files[0])
    monkeypatch.setenv("REFERENCE_WORKER_STORAGE_PATH", data_dir)

    # Prepare fake DB and repository to capture calls
    created_repos = []

    class DummyDB:
        def close(self):
            return None

    class FakeRepo:
        def __init__(self, db):
            self.db = db
            self.statuses = []
            self.inserted = []
            self.created = []
            created_repos.append(self)

        def create_reference(self, filename, uploader_user_id, mime_type, content_hash, revision=None, effective_date=None):
            self.created.append({
                "filename": filename,
                "mime_type": mime_type,
                "content_hash": content_hash,
            })
            return SimpleNamespace(id=9999)

        def update_status(self, reference_id, status):
            self.statuses.append(status)
            return None

        def insert_chunks(self, reference_id, chunks):
            # record inserted chunks
            self.inserted.extend(chunks)
            return chunks

    # Monkeypatch database and repository dependencies used by the API and worker
    monkeypatch.setattr("backend.app.db.session.SessionLocal", lambda: DummyDB())
    import backend.app.api.v1.endpoints.references as refs_module
    import backend.app.domain.reference_ingestion_service as ingestion_module
    monkeypatch.setattr(refs_module, "SessionLocal", lambda: DummyDB())
    monkeypatch.setattr(ingestion_module, "SessionLocal", lambda: DummyDB())
    monkeypatch.setattr("backend.app.db.repositories.reference_repository.ReferenceRepository", FakeRepo)
    monkeypatch.setattr(refs_module, "ReferenceRepository", FakeRepo)
    monkeypatch.setattr(ingestion_module, "ReferenceRepository", FakeRepo)

    # Monkeypatch embedder to avoid heavy model download and produce deterministic vectors
    class FakeEmbedder:
        def __init__(self, model_name=None):
            self.model_name = model_name

        def encode(self, texts, show_progress_bar=False):
            # Return a vector of length 384 for each text
            return [[0.01] * 384 for _ in texts]

    monkeypatch.setattr("backend.app.domain.reference_ingestion_service.SentenceTransformer", FakeEmbedder)

    # Make the API's Celery submission execute the real task synchronously.
    from backend.app.workers.tasks.reference_ingest_task import reference_ingest_task
    def fake_delay(reference_id, task_file_path, metadata):
        reference_ingest_task(reference_id, task_file_path, metadata)
        return SimpleNamespace(id="synchronous-task-id")

    monkeypatch.setattr(
        refs_module,
        "reference_ingest_task",
        SimpleNamespace(delay=fake_delay),
    )

    from backend.app.main import app
    client = TestClient(app)
    response = client.post("/api/v1/references")

    assert response.status_code == 202
    assert response.json()["reference_id"] == 9999
    assert response.json()["ingest_job_id"] == "synchronous-task-id"

    assert created_repos, "FakeRepo was not instantiated"
    assert len(created_repos) >= 2, "Worker repository was not instantiated"
    worker_repos = created_repos[1:]
    statuses = [status for worker_repo in worker_repos for status in worker_repo.statuses]
    inserted = [chunk for worker_repo in worker_repos for chunk in worker_repo.inserted]

    assert created_repos[0].created[0]["filename"] == os.path.basename(file_path)

    # Check that status moved to INGESTING then to READY
    from backend.app.db.models.reference_document import ReferenceStatus

    assert any(s == ReferenceStatus.INGESTING for s in statuses), "INGESTING status not set"
    assert any(s == ReferenceStatus.READY for s in statuses), "READY status not set"

    # Ensure chunks were inserted
    assert len(inserted) > 0, "No chunks were inserted"

    # Check embeddings and metadata
    for c in inserted:
        assert "content" in c and c["content"].strip(), "Chunk content empty"
        assert "metadata" in c and c["metadata"].get("source") == os.path.basename(file_path)
        emb = c.get("embedding")
        assert isinstance(emb, list)
        # embedding dims
        assert len(emb) == 384
