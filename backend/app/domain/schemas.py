from __future__ import annotations
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime


class VerificationStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    UNSUPPORTED = "UNSUPPORTED"


class ParameterStatus(str, Enum):
    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    NOT_SPECIFIED = "NOT_SPECIFIED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class MedicationEntity(BaseModel):
    medication_name: str
    dose_value: Optional[float]
    dose_unit: Optional[str]
    route: Optional[str]
    frequency: Optional[str]
    timing: Optional[str]
    duration: Optional[str]
    indication: Optional[str]
    source_document_id: Optional[int]
    source_page: Optional[int]
    source_text: Optional[str]
    confidence: Optional[float] = None


class ReferenceEvidence(BaseModel):
    medication_name: Optional[str]
    text: str
    document_id: int
    page: Optional[int]
    section: Optional[str]
    chunk_id: str
    retrieval_score: float


class ParameterComparison(BaseModel):
    parameter: str
    primary_value: Optional[Any]
    reference_value: Optional[Any]
    status: ParameterStatus
    explanation: Optional[str]


class VerificationResult(BaseModel):
    medication_name: str
    status: VerificationStatus
    comparisons: List[ParameterComparison]
    explanation: Optional[str]
    evidence: Optional[ReferenceEvidence]
    source_page: Optional[int]
    confidence: Optional[float]


class DocumentRecord(BaseModel):
    document_id: int
    user_id: int
    filename: str
    mime_type: str
    content_hash: str
    pages: Optional[int]
    created_at: datetime


class JobStage(BaseModel):
    name: str
    status: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error: Optional[str]
    metadata: Optional[Dict[str, Any]]


class JobRecord(BaseModel):
    job_id: int
    primary_document_id: int
    reference_document_id: int
    user_id: int
    status: str
    current_stage: Optional[str]
    stages: Optional[List[JobStage]]
    created_at: datetime
