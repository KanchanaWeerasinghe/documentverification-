import os
from pathlib import Path
from typing import List, Dict, Any
from backend.app.db.session import SessionLocal
from backend.app.db.repositories.job_repo import JobRepository
from backend.app.db.repositories.document_repo import DocumentRepository
from backend.app.db.repositories.reference_repository import ReferenceRepository
from backend.app.domain.job_service_impl import JobServiceImpl
from backend.app.domain.schemas import MedicationEntity, VerificationResult, VerificationStatus, ParameterComparison, ParameterStatus
from backend.app.db.models.reference_chunk import ReferenceChunk
from sentence_transformers import SentenceTransformer
import re
import logging
from backend.app.ingestion.text_cleaner import clean_pages, clean_paragraphs, clean_text

logger = logging.getLogger(__name__)


class DocumentVerificationService:
    STAGES = [
        "parsed",
        "chunked",
        "embedded",
        "summarized",
        "key_points_extracted",
        "entities_extracted",
        "verified",
        "done",
    ]

    def __init__(self, embed_model: str = None):
        self.job_service = JobServiceImpl()
        self.embed_model = embed_model or os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

    def start_job(self, job_id: int):
        db = SessionLocal()
        job_repo = JobRepository(db)
        job = job_repo.get_job(job_id)
        if not job:
            db.close()
            raise ValueError("job not found")

        # stages executed sequentially
        try:
            # parsed
            self.job_service.update_stage(job_id, "parsed", "STARTED")
            parsed = self._parse_document(job.primary_document_id)
            self.job_service.update_stage(job_id, "parsed", "COMPLETED")

            # chunked
            self.job_service.update_stage(job_id, "chunked", "STARTED")
            chunks = self._chunk_parsed(parsed)
            # persist chunks
            doc_repo = DocumentRepository(db)
            doc_repo.insert_chunks(job.primary_document_id, chunks)
            self.job_service.update_stage(job_id, "chunked", "COMPLETED")

            # embedded
            self.job_service.update_stage(job_id, "embedded", "STARTED")
            texts = [c.get("content") for c in chunks]
            model = SentenceTransformer(self.embed_model)
            vectors = model.encode(texts, show_progress_bar=False)
            for i, vec in enumerate(vectors):
                if hasattr(vec, "tolist"):
                    chunks[i]["embedding"] = vec.tolist()
                else:
                    chunks[i]["embedding"] = list(vec)
            # update persisted chunks with embeddings (simple re-insert)
            doc_repo.insert_chunks(job.primary_document_id, chunks)
            self.job_service.update_stage(job_id, "embedded", "COMPLETED")

            # summarized
            self.job_service.update_stage(job_id, "summarized", "STARTED")
            summary = self._summarize(parsed)
            self.job_service.update_stage(job_id, "summarized", "COMPLETED", metadata={"summary_length": len(summary)})

            # critical points
            self.job_service.update_stage(job_id, "key_points_extracted", "STARTED")
            critical = self._extract_critical_points(parsed)
            self.job_service.update_stage(job_id, "key_points_extracted", "COMPLETED", metadata={"points": len(critical)})

            job.meta = {"summary": summary, "critical_points": critical}
            db.add(job)
            db.commit()

            # entities
            self.job_service.update_stage(job_id, "entities_extracted", "STARTED")
            entities = self._extract_entities(parsed)
            self.job_service.update_stage(job_id, "entities_extracted", "COMPLETED", metadata={"entities": len(entities)})

            # verified
            self.job_service.update_stage(job_id, "verified", "STARTED")
            results = []
            ref_repo = ReferenceRepository(db)
            for ent in entities:
                res = self._verify_entity(ent, ref_repo)
                results.append(res)
            # persist results
            from backend.app.db.repositories.job_repo import JobRepository as JR
            from backend.app.db.repositories import ReferenceRepository as RR
            # simple persistence of verification results
            from backend.app.db.models.result import VerificationResultModel
            for r in results:
                vr = VerificationResultModel(job_id=job_id, medication_name=r.medication_name, status=r.status.value, comparisons=[c.dict() for c in r.comparisons], explanation=r.explanation, evidence=r.evidence.dict() if r.evidence else None)
                db.add(vr)
            db.commit()
            self.job_service.update_stage(job_id, "verified", "COMPLETED", metadata={"results": len(results)})

            # done
            self.job_service.update_stage(job_id, "done", "COMPLETED")
            db.close()
            return True
        except Exception as exc:
            logger.exception("Job %s failed at workflow stage", job_id)
            try:
                self.job_service.update_stage(job_id, "failed", "FAILED", error=str(exc))
            except Exception:
                logger.exception("Failed to record failure for job %s", job_id)
            db.close()
            raise

    def _parse_document(self, document_id: int) -> Dict[str, Any]:
        from backend.app.db.session import SessionLocal
        from backend.app.db.models.document import Document
        db = SessionLocal()
        doc = db.query(Document).filter(Document.id == document_id).first()
        db.close()
        if not doc:
            raise ValueError("document not found")

        default_storage = Path(__file__).resolve().parents[2] / "data" / "primary"
        storage = os.getenv("PRIMARY_STORAGE_PATH", str(default_storage))
        path = os.path.join(storage, doc.filename)
        text = ""
        pages: List[str] = []
        if doc.filename.lower().endswith('.docx'):
            try:
                from docx import Document as DocxDocument
                d = DocxDocument(path)
                paras = clean_paragraphs(p.text for p in d.paragraphs)
                text = "\n".join(paras)
                # DOCX doesn't provide reliable page numbers; leave pages empty
            except Exception:
                text = ""
        elif doc.filename.lower().endswith('.pdf'):
            try:
                import PyPDF2
                reader = PyPDF2.PdfReader(path)
                for p in reader.pages:
                    ptext = p.extract_text() or ""
                    pages.append(ptext)
                pages = clean_pages(pages)
                text = "\n".join(pages)
            except Exception:
                text = ""
        else:
            text = ""

        return {"pages": pages, "text": clean_text(text)}

    def _chunk_parsed(self, parsed: Dict[str, Any]) -> List[Dict[str, Any]]:
        # naive chunker: split by 2000 chars, preserve page if available
        chunks = []
        pages = parsed.get("pages") or []
        if pages:
            for pi, ptext in enumerate(pages, start=1):
                text = ptext.strip()
                if not text:
                    continue
                # split page into 2000-char chunks
                for i in range(0, len(text), 2000):
                    chunks.append({"content": text[i:i+2000], "metadata": {"page": pi}, "page": pi})
        else:
            text = parsed.get("text", "")
            for i in range(0, len(text), 2000):
                chunks.append({"content": text[i:i+2000], "metadata": {}, "page": None})
        return chunks

    def _summarize(self, parsed: Dict[str, Any]) -> str:
        # deterministic: return first 512 chars
        text = "\n".join(parsed.get("pages") or [parsed.get("text", "")])
        return text[:512]

    def _extract_critical_points(self, parsed: Dict[str, Any]) -> List[Dict[str, Any]]:
        text = parsed.get("text", "")
        # naive heuristic: sentences containing keywords
        keywords = ["follow up", "monitor", "warning", "report", "side effect", "caution", "precaution"]
        points = []
        for sent in re.split(r"(?<=[\.\n])\s+", text):
            ls = sent.lower()
            if any(k in ls for k in keywords):
                points.append({"point": sent.strip(), "importance": "high", "source_page": None, "source_text": sent.strip()})
        return points

    def _extract_entities(self, parsed: Dict[str, Any]) -> List[MedicationEntity]:
        text = parsed.get("text", "")
        # very simple regex to find lines like 'DrugName 100 mg once daily'
        ents: List[MedicationEntity] = []
        for line in text.splitlines():
            m = re.search(r"([A-Z][A-Za-z0-9\-]+)\s+(\d+(?:\.\d+)?)\s*(mg|g|mcg|ml)?\s*(.*)", line)
            if m:
                name = m.group(1)
                dose = float(m.group(2))
                unit = m.group(3)
                rest = m.group(4).strip()
                ent = MedicationEntity(medication_name=name, dose_value=dose, dose_unit=unit, route=None, frequency=None, timing=None, duration=None, indication=None, source_document_id=None, source_page=None, source_text=line.strip(), confidence=0.5)
                ents.append(ent)
        return ents

    def _verify_entity(self, ent: MedicationEntity, ref_repo: ReferenceRepository) -> VerificationResult:
        # targeted retrieval: find reference chunks where monograph_name roughly matches
        db_chunks = ref_repo.get_chunks_by_reference(ent.source_document_id or 1)
        # find by substring
        best = None
        for c in db_chunks:
            if c.monograph_name and ent.medication_name.lower() in (c.monograph_name or "").lower():
                best = c
                break

        if not best:
            return VerificationResult(medication_name=ent.medication_name, status=VerificationStatus.UNSUPPORTED, comparisons=[], explanation="No relevant reference passage found", evidence=None, source_page=ent.source_page, confidence=0.0)

        # simple numeric dose comparison (if reference contains digits)
        ref_text = (best.content or "")
        ref_dose_match = re.search(r"(\d+(?:\.\d+)?)\s*(mg|g|mcg|ml)", ref_text)
        comparisons = []
        if ent.dose_value is not None and ref_dose_match:
            ref_dose = float(ref_dose_match.group(1))
            status = ParameterStatus.MATCH if abs(ent.dose_value - ref_dose) < 1e-6 else ParameterStatus.MISMATCH
            comparisons.append(ParameterComparison(parameter="dose", primary_value=ent.dose_value, reference_value=ref_dose, status=status, explanation=None))
        else:
            comparisons.append(ParameterComparison(parameter="dose", primary_value=ent.dose_value, reference_value=None, status=ParameterStatus.NOT_SPECIFIED, explanation=None))

        # determine overall status
        overall = VerificationStatus.SUPPORTED
        for c in comparisons:
            if c.status == ParameterStatus.MISMATCH:
                overall = VerificationStatus.CONTRADICTED

        evidence = None
        from backend.app.domain.schemas import ReferenceEvidence
        if best:
            evidence = ReferenceEvidence(medication_name=best.monograph_name, text=best.content, document_id=best.reference_document_id, page=best.page, section=best.section, chunk_id=str(best.id), retrieval_score=1.0)

        from backend.app.domain.schemas import VerificationResult as VRes
        # convert ParameterComparison pydantic objects
        return VRes(medication_name=ent.medication_name, status=overall, comparisons=comparisons, explanation=None, evidence=evidence, source_page=ent.source_page, confidence=0.9)
