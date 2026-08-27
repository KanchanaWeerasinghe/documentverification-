from typing import List, Optional
import os
from .schemas import MedicationEntity, ReferenceEvidence


class EvidenceService:
    """Retrieve relevant institutional evidence for a medication entity using RAG.

    This service must be configured with retrieval parameters (top_k, threshold)
    and must return a ranked list of `ReferenceEvidence` objects.
    """

    def retrieve_evidence(self, entity: MedicationEntity, reference_document_id: int, top_k: int = 10, similarity_threshold: float = 0.75) -> List[ReferenceEvidence]:
        """Return top-k evidence passages for the given entity.

        If no passage meets `similarity_threshold`, return an empty list.
        """
        # Minimal retrieval implementation using in-Python similarity over stored embeddings.
        # This implementation expects embeddings to be stored as lists (JSON) or pgvector vectors.
        from backend.app.db.session import SessionLocal
        from backend.app.db.repositories.reference_repository import ReferenceRepository
        from backend.app.domain.reference_ingestion_service import SentenceTransformer
        import numpy as np

        db = SessionLocal()
        try:
            repo = ReferenceRepository(db)
            chunks = repo.get_chunks_by_reference(reference_document_id)

            if not chunks:
                return []

            # Compute query embedding
            query_text = entity.name
            embedder = SentenceTransformer(os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"))
            qvec = np.array(embedder.encode([query_text], show_progress_bar=False)[0], dtype=float)

            # Collect chunk embeddings and compute cosine similarity
            emb_list = []
            for ch in chunks:
                emb = getattr(ch, "embedding", None)
                if emb is None:
                    emb_list.append(None)
                else:
                    emb_arr = np.array(emb, dtype=float)
                    emb_list.append(emb_arr)

            sims = []
            for idx, emb in enumerate(emb_list):
                if emb is None:
                    sims.append((idx, -1.0))
                    continue
                # cosine similarity
                denom = np.linalg.norm(qvec) * np.linalg.norm(emb)
                score = float(np.dot(qvec, emb) / denom) if denom > 0 else 0.0
                sims.append((idx, score))

            sims.sort(key=lambda x: x[1], reverse=True)

            from backend.app.domain.schemas import ReferenceEvidence

            results = []
            for idx, score in sims[:top_k]:
                if score < similarity_threshold:
                    continue
                ch = chunks[idx]
                evidence = ReferenceEvidence(
                    medication_name=ch.meta.get("medication_name") if hasattr(ch, "meta") and ch.meta else None,
                    text=ch.content,
                    document_id=ch.reference_document_id,
                    page=ch.page,
                    section=ch.section,
                    chunk_id=str(ch.id),
                    retrieval_score=score,
                )
                results.append(evidence)

            return results
        finally:
            db.close()
