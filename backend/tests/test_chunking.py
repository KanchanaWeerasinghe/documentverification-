from backend.app.domain.reference_ingestion_service import ReferenceIngestionService


def make_long_monograph(title: str, n_paras: int = 100):
    paras = [f"{title} - intro paragraph {i}." for i in range(3)]
    # add many paras to exceed CHAR_LIMIT
    for i in range(n_paras):
        paras.append(f"Field{i}: details about the drug field content paragraph {i}.")
    return {"title": title, "paragraphs": paras}


def test_chunk_monograph_preserves_medication_name_and_splits():
    svc = ReferenceIngestionService()
    mono = make_long_monograph("Velantine", n_paras=200)
    chunks = svc.chunk_monograph(mono)
    assert isinstance(chunks, list)
    assert len(chunks) > 1
    # Each chunk metadata must contain medication_name
    for i, c in enumerate(chunks):
        assert "medication_name" in c["metadata"]
        assert c["metadata"]["medication_name"] == "Velantine"
        assert c["content"].strip()


def test_small_monograph_kept_whole():
    svc = ReferenceIngestionService()
    mono = {"title": "Cordizem-XR", "paragraphs": ["Short intro.", "Dose: 100mg once daily."]}
    chunks = svc.chunk_monograph(mono)
    assert len(chunks) == 1
    assert chunks[0]["metadata"]["medication_name"] == "Cordizem-XR"
    assert "Dose" in chunks[0]["content"]
