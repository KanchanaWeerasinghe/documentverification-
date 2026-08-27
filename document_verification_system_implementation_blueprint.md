# Document Verification System — System Design & Implementation Blueprint

## 1. Purpose

This document is the **implementation contract for GitHub Copilot / engineering work**.

The system is a medical-document verification MVP. It accepts a primary PDF/DOCX document, allows the user to select an institutional reference/formulary document, processes the request asynchronously, generates a summary and critical patient-facing points, extracts structured medication entities, retrieves relevant reference evidence, verifies prescribing parameters, and presents grounded results with citations.

This document must be treated as the architectural source of truth **before generating application code**.

---

## 2. Scope

### In scope

1. User authentication.
2. Primary PDF/DOCX upload.
3. Institutional reference-document selection.
4. Asynchronous processing.
5. Document parsing.
6. Reference-document ingestion and indexing.
7. Summary generation.
8. Critical patient-facing point extraction.
9. Medication/entity extraction.
10. Targeted RAG retrieval from the institutional reference.
11. Medication verification.
12. Supported / Contradicted / Unsupported classification.
13. Grounded explanations and citations.
14. Per-stage progress and failure reporting.
15. Persistence of documents, jobs, evidence and results.
16. Unit, integration, evaluation and end-to-end testing.
17. CI/CD and containerized deployment.

### Out of scope unless explicitly added later

- Clinical diagnosis.
- Independent clinical decision-making.
- External medical web search as an authority.
- Recommending a treatment alternative.
- Autonomous medication changes.
- Replacing clinician judgment.

The institutional reference document is the authority for the MVP verification task.

---

# 3. Architectural Principles

## 3.1 Separation of concerns

The system must keep the following responsibilities separate:

```text
UI
  ↓
API
  ↓
Application / Business Services
  ↓
Async Orchestration
  ↓
Domain Capabilities
  ├── Ingestion
  ├── LLM
  ├── RAG
  ├── Verification Rules
  └── Validation
  ↓
Persistence
```

## 3.2 RAG is evidence retrieval, not the final decision

RAG retrieves authoritative passages from the selected institutional reference.

It must not independently decide whether a prescription is safe or correct.

## 3.3 LLM is not the final verification authority

The LLM may be used for:

- structured extraction;
- semantic interpretation;
- summarization;
- explanation generation.

The final Supported / Contradicted / Unsupported decision must be controlled by the verification business logic using retrieved evidence.

## 3.4 Business rules must be independently testable

The verification engine must be executable without an LLM, vector database, API server or database.

This allows deterministic unit tests for the core decision logic.

## 3.5 Evidence must be traceable

Every supported or contradicted verification must preserve:

- reference document ID;
- page where available;
- section;
- chunk ID;
- retrieved text;
- retrieval metadata where useful.

Never fabricate citations.

## 3.6 No evidence means no unsupported inference

If sufficient authoritative evidence cannot be retrieved, classify the medication as:

```text
UNSUPPORTED
```

Do not guess.

---

# 4. Target Architecture

```text
┌──────────────────────────────────────────────────────────────────────┐
│                         PRESENTATION LAYER                           │
│ Streamlit UI                                                       │
│ Upload • Document Viewer • Progress • Results • Citations • Metrics│
└───────────────────────────────┬──────────────────────────────────────┘
                                │ HTTPS / SSE
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                              API LAYER                               │
│ FastAPI                                                            │
│ Auth • Documents • Jobs • Results                                   │
│ Request validation • Rate limiting • CORS • Tracing                │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    APPLICATION / BUSINESS LAYER                      │
│                                                                      │
│ DocumentService                                                     │
│ JobService                                                          │
│ SummaryService                                                      │
│ ExtractionService                                                   │
│ EvidenceService                                                     │
│ VerificationService                                                 │
│ ResultService                                                       │
│ DocumentVerificationService                                         │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      ASYNC ORCHESTRATION LAYER                       │
│ Celery / Worker                                                     │
│ State Machine                                                       │
│ Stage execution • Retry • Failure handling                          │
└──────────────┬───────────────────┬────────────────────┬──────────────┘
               │                   │                    │
               ▼                   ▼                    ▼
┌──────────────────────┐ ┌────────────────────┐ ┌─────────────────────┐
│ DATA INGESTION       │ │ LLM / GENAI        │ │ RAG PIPELINE        │
│                      │ │                    │ │                     │
│ PDF parser           │ │ Extraction         │ │ Embeddings          │
│ DOCX parser          │ │ Summary            │ │ Hybrid retrieval    │
│ Text cleaning        │ │ Explanation        │ │ Reranking           │
│ Structure-aware      │ │                    │ │ pgvector            │
│ chunking              │ │                    │ │                     │
└──────────┬───────────┘ └─────────┬──────────┘ └──────────┬──────────┘
           │                       │                       │
           └───────────────────────┼───────────────────────┘
                                   ▼
                    ┌──────────────────────────────┐
                    │ VERIFICATION / RULE ENGINE  │
                    │                              │
                    │ Drug existence              │
                    │ Dose                         │
                    │ Route                        │
                    │ Frequency                    │
                    │ Timing                       │
                    │ Duration                     │
                    │ Indication                   │
                    │ Contraindications            │
                    └───────────────┬──────────────┘
                                    │
                                    ▼
                    ┌──────────────────────────────┐
                    │ VALIDATION / EVALUATION      │
                    │ Schema • Groundedness        │
                    │ Retrieval • Verification     │
                    └───────────────┬──────────────┘
                                    │
                                    ▼
                    ┌──────────────────────────────┐
                    │ PERSISTENCE                  │
                    │ PostgreSQL + pgvector        │
                    │ Documents • Jobs • Results   │
                    │ Evidence • Audit metadata    │
                    └──────────────────────────────┘

Cross-cutting:
Security • Configuration • Logging • Tracing • Error handling • Audit
```

---

# 5. Existing Project Structure

The implementation should evolve the existing structure rather than replacing it.

```text
document-verification-system/
│
├── .github/workflows/
│   ├── ci-tests.yml
│   ├── eval-pipeline.yml
│   └── deploy-prod.yml
│
├── docker/
│   ├── Dockerfile.api
│   ├── Dockerfile.worker
│   ├── Dockerfile.ui
│   └── docker-compose.yml
│
├── infra/
│   ├── terraform/
│   └── k8s/
│
├── docs/
│   └── adr/
│
├── frontend/
│   └── src/
│       ├── components/
│       ├── features/
│       ├── hooks/
│       ├── services/
│       └── types/
│
├── backend/
│   └── app/
│       ├── api/
│       ├── core/
│       ├── domain/
│       ├── rules/
│       ├── ingestion/
│       ├── rag/
│       ├── llm/
│       ├── db/
│       └── workers/
│
└── tests/
    ├── unit/
    ├── integration/
    ├── api/
    ├── eval/
    └── e2e/
```

---

# 6. Layer Responsibilities

## 6.1 Presentation Layer — Streamlit

Location:

```text
frontend/
```

### Technology

Use **Streamlit** for the presentation/demo application.

Recommended entry point:

```text
frontend/app.py
```

### Responsibilities

The Streamlit application provides the user-facing workflow:

1. Authenticate or establish a demo user session.
2. Upload the primary PDF/DOCX document.
3. Select the institutional reference document.
4. Start verification.
5. Show asynchronous processing progress.
6. Show document summary.
7. Show critical patient-facing points.
8. Show extracted medications.
9. Show Supported / Contradicted / Unsupported results.
10. Show parameter-level comparisons.
11. Show grounded evidence and citations.
12. Show failures and retry/status information.
13. Show evaluation/analytics information where required.

### Recommended Streamlit UI modules

```text
frontend/
├── app.py
├── pages/
│   ├── upload.py
│   ├── verification.py
│   └── analytics.py
├── components/
│   ├── document_viewer.py
│   ├── citation_card.py
│   ├── progress.py
│   ├── medication_result.py
│   └── comparison_table.py
├── services/
│   └── api_client.py
├── state/
│   └── session.py
└── utils/
    └── formatting.py
```

### Streamlit state

Use `st.session_state` only for presentation/session state such as:

```text
current_user
primary_document_id
reference_document_id
job_id
job_status
selected_medication
```

Do not use Streamlit session state as the system's source of truth for jobs or verification results.

The backend database remains authoritative.

### Streamlit interaction model

```text
User
  ↓
Streamlit
  ↓
FastAPI API
  ↓
Business/Application Services
  ↓
Async Worker / Processing Pipeline
  ↓
Database
  ↓
FastAPI
  ↓
Streamlit
```

### Progress display

For the MVP, Streamlit can poll the job-status endpoint periodically.

Example:

```text
CREATED
  ↓
PARSING        ████████░░
  ↓
EXTRACTING     ██████████
  ↓
RETRIEVING     ██████████
  ↓
VERIFYING      ███████░░░
  ↓
VALIDATING     ██████████
  ↓
COMPLETED      ██████████
```

If SSE is retained in the backend, Streamlit may consume it through a backend client, but **polling is preferred for the first MVP because it is simpler and more reliable for a presentation/demo**.

### Streamlit must NOT

- implement verification rules;
- directly query PostgreSQL;
- directly query pgvector;
- execute LLM prompts;
- run Celery tasks;
- implement RAG;
- determine Supported / Contradicted / Unsupported.

The Streamlit application is a thin presentation client.

It only renders API results.

---

# 6.2 Streamlit Presentation Flow

The presentation should demonstrate the complete verification journey without exposing internal implementation complexity.

```text
┌───────────────────────────────┐
│ Streamlit                     │
│                               │
│ 1. Upload Primary Document    │
│ 2. Select Reference Document  │
│ 3. Start Verification        │
└───────────────┬───────────────┘
                │
                ▼
        FastAPI /jobs
                │
                ▼
        Async Processing
                │
       ┌────────┼─────────┐
       ▼        ▼         ▼
    Parsing   RAG       LLM
       │        │         │
       └────────┼─────────┘
                ▼
          Verification
                │
                ▼
          Validation
                │
                ▼
          PostgreSQL
                │
                ▼
        FastAPI /results
                │
                ▼
        Streamlit Results
```

### Recommended presentation screens

#### Screen 1 — Document Upload

Show:

- Primary document uploader.
- Institutional reference selector.
- Selected filenames.
- Start Verification button.

#### Screen 2 — Processing

Show:

- Job ID.
- Current processing stage.
- Stage progress.
- Errors if any.
- Refresh/status control.

#### Screen 3 — Document Intelligence

Show:

- Document summary.
- Critical patient-facing points.
- Extracted medications.

#### Screen 4 — Verification Results

Show a table:

| Medication | Status | Key Finding |
|---|---|---|
| Medication A | SUPPORTED | Parameters align |
| Medication B | CONTRADICTED | Timing differs |
| Medication C | UNSUPPORTED | No sufficient reference evidence |

Use clear status indicators, but do not encode the decision logic in the UI.

#### Screen 5 — Evidence / Explainability

For each medication show:

```text
Medication
    ↓
Extracted parameters
    ↓
Comparison
    ↓
Reference evidence
    ↓
Citation
    ↓
Explanation
```

The user should be able to see why the system reached the displayed result.

#### Screen 6 — Evaluation / Analytics

Show MVP-level quality indicators such as:

- retrieval metrics;
- extraction quality;
- verification accuracy;
- groundedness;
- processing duration.

These values must come from evaluation/backend data rather than being calculated from UI events.

---

# 7. API Layer

Location:

```text
backend/app/api/
```

### Endpoints

```text
POST /api/v1/auth/...
POST /api/v1/documents
GET  /api/v1/documents/{document_id}

POST /api/v1/jobs
GET  /api/v1/jobs/{job_id}
GET  /api/v1/jobs/{job_id}/events

GET  /api/v1/results/{job_id}
```

Exact route naming may be adjusted to the existing implementation.

Reference-document endpoints (async ingest):

```text
POST /api/v1/references        # upload a reference document (DOCX/PDF) -> returns ingestion job_id
GET  /api/v1/references/{reference_id}
GET  /api/v1/references/{reference_id}/status
```

Notes: reference upload must be restricted to admin/editor roles. The `POST /api/v1/references` endpoint should create a `reference_documents` record and immediately enqueue an ingestion job (returning a `job_id` for ingestion) rather than processing synchronously.

### API responsibilities

- Authentication.
- Authorization.
- Request validation.
- Response serialization.
- Calling application/domain services.
- Returning job IDs.
- Returning persisted results.
- Streaming or exposing job progress.

Implementation note: authentication for the MVP uses JWT-based tokens. The API layer must validate JWTs on every request and enforce ownership/authorization checks before returning any document, job, or result.

### API must NOT

- contain RAG code;
- contain prompt construction;
- perform medication comparison;
- directly manipulate vector search;
- contain business rules.

---

# 8. Application / Business Logic Layer

Location:

```text
backend/app/domain/
```

Implemented services:

```text
evidence_service.py
document_verification_service.py
job_service_impl.py
reference_ingestion_service.py
schemas.py
```

## 8.1 DocumentService

Responsible for:

- document registration;
- document metadata;
- document validation;
- primary/reference document relationships;
- document lifecycle.

It delegates parsing to the ingestion layer.

It does not parse PDF/DOCX itself.

---

## 8.2 JobService

Responsible for:

- creating jobs;
- stage state;
- stage timestamps;
- failure state;
- retry metadata;
- job status retrieval.

Example states:

```text
CREATED
PARSING
CHUNKING
EMBEDDING
SUMMARIZING
KEY_POINTS
EXTRACTING_ENTITIES
VERIFYING
VALIDATING
COMPLETED
FAILED
```

Each stage should capture:

```text
stage
status
started_at
completed_at
error
metadata
```

---

## 8.3 SummaryService

Responsible for:

- generating the document summary;
- extracting critical patient-facing points.

It calls the LLM abstraction.

The summary must be based on the parsed primary document.

---

## 8.4 ExtractionService

Responsible for converting primary-document text into structured medication entities.

Input:

```text
parsed primary document
```

Output:

```text
MedicationEntity[]
```

It may call the LLM extractor but must validate the returned schema.

---

## 8.5 EvidenceService

Responsible for business-level evidence retrieval.

Input:

```text
MedicationEntity
ReferenceDocumentID
```

Output:

```text
ReferenceEvidence[]
```

It calls the RAG retriever.

It does not know whether the medication is supported or contradicted.

---

## 8.6 VerificationService

This is the core business service.

Input:

```text
MedicationEntity
ReferenceEvidence[]
```

Output:

```text
VerificationResult
```

Responsibilities:

1. Determine whether sufficient evidence exists.
2. Compare prescribing parameters.
3. Apply verification rules.
4. Determine final status.
5. Preserve evidence.
6. Produce structured comparison results.

It delegates individual business rules to `RuleEngine`.

Verification implementation note: the verification service applies deterministic comparison rules to prescribing parameters (dose, frequency, duration, route, timing) with configurable tolerances. The LLM is used to produce grounded interpretation and human-readable explanations, but it does not replace the deterministic parameter comparisons; verification decisions are derived from deterministic comparisons against retrieved evidence.

---

## 8.7 ResultService

Responsible for:

- saving verification results;
- retrieving results;
- aggregating medication results;
- exposing results to the API.

It uses repositories.

It does not determine verification status.

---

## 8.8 DocumentVerificationService

Responsible for coordinating business services.

Example:

```text
DocumentService
      ↓
SummaryService
      ↓
ExtractionService
      ↓
EvidenceService
      ↓
VerificationService
      ↓
ResultService
```

DocumentVerificationService is an application coordinator.

It must not contain detailed dose/timing/frequency rules.

---

# 9. Verification Domain Model

## MedicationEntity

```python
MedicationEntity(
    medication_name,
    dose_value,
    dose_unit,
    route,
    frequency,
    timing,
    duration,
    indication,
    source_document_id,
    source_page,
    source_text
)
```

Missing information remains `None`.

Do not invent missing data.

---

## ReferenceEvidence

```python
ReferenceEvidence(
    medication_name,
    text,
    document_id,
    page,
    section,
    chunk_id,
    retrieval_score
)
```

---

## ParameterComparison

```python
ParameterComparison(
    parameter,
    primary_value,
    reference_value,
    status,
    explanation
)
```

Comparison statuses:

```text
MATCH
MISMATCH
NOT_SPECIFIED
NOT_APPLICABLE
```

---

## VerificationResult

```python
VerificationResult(
    medication_name,
    status,
    comparisons,
    explanation,
    evidence,
    source_page,
    confidence
)
```

Verification statuses:

```text
SUPPORTED
CONTRADICTED
UNSUPPORTED
```

---

# 10. Business Rules

The verification engine must explicitly compare:

1. Medication existence.
2. Dose.
3. Route.
4. Frequency.
5. Timing.
6. Duration.
7. Indication.
8. Contraindications where supported by the reference.

## Rule precedence

Use this decision model:

```text
No sufficient reference evidence
        ↓
UNSUPPORTED

Evidence exists
        ↓
Explicit authoritative conflict?
        ↓
YES → CONTRADICTED

NO
        ↓
Sufficient relevant parameters consistent?
        ↓
YES → SUPPORTED
```

Missing information is not automatically a contradiction.

---

# 11. Verification Example

Primary prescription:

```text
Pravoxil 20 mg PO every morning
```

Reference:

```text
Pravoxil 20 mg orally once daily at bedtime
```

Comparison:

```text
Drug       MATCH
Dose       MATCH
Route      MATCH
Frequency  MATCH
Timing     MISMATCH
```

Result:

```text
CONTRADICTED
```

Reason:

```text
The primary document specifies morning administration while
the institutional reference specifies bedtime administration.
```

The result must contain the reference evidence and citation metadata.

---

# 12. Unsupported Example

If a medication is not represented by a sufficiently relevant reference monograph:

```text
Medication
    ↓
Targeted retrieval
    ↓
No sufficient authoritative evidence
    ↓
UNSUPPORTED
```

Do not infer that the medication is supported because a similar medication exists.

Do not fabricate evidence.

---

# 13. Data Ingestion Layer

Location:

```text
backend/app/ingestion/
```

## PDF parser

```text
pdf_parser.py
```

Responsibilities:

- extract text;
- preserve page numbers;
- preserve useful structural metadata.

## DOCX parser

```text
docx_parser.py
```

Responsibilities:

- extract paragraphs;
- extract tables where relevant;
- preserve structure as far as practical.

## Text cleaner

```text
text_cleaner.py
```

Responsibilities:

- normalize whitespace;
- remove parsing artifacts;
- preserve medically meaningful text.

## Chunking

```text
chunking.py
```

The institutional reference is structured into discrete monographs.

Prefer structure-aware chunks over arbitrary fixed-size chunks.

Example:

```text
Section
 └── Medication Monograph
       ├── indication
       ├── dosing
       ├── administration
       ├── contraindications
       ├── interactions
       └── monitoring
```

Metadata must identify:

```text
document_id
page
section
medication
chunk_id
```

---

# 14. RAG Pipeline

Location:

```text
backend/app/rag/
```

Components:

```text
embeddings.py
vector_store.py
hybrid_retriever.py
reranker.py
```

## Reference ingestion

```text
Reference document
       ↓
Parser
       ↓
Structure-aware chunks
       ↓
Embeddings
       ↓
PostgreSQL + pgvector
```

Embeddings implementation note: use a Hugging Face embedding model for the MVP and persist vectors in PostgreSQL via the `pgvector` extension. Record the embedding model name and version in ingestion metadata to support reproducibility and audits.

## Query-time retrieval

```text
MedicationEntity
       ↓
Query construction
       ↓
Hybrid retrieval
       ↓
Metadata filtering
       ↓
Reranking
       ↓
ReferenceEvidence[]
```

The retriever should prioritize the selected reference document.

Do not retrieve evidence from unrelated documents.

Retrieval configuration: retrieval behavior must be configurable via environment or config values (for example `TOP_K` and `SIMILARITY_THRESHOLD`). Only passages meeting the configured similarity threshold (or otherwise marked sufficiently relevant) should be forwarded to the verification service; if no passage meets the threshold, the verification stage must treat the entity as having insufficient evidence rather than guessing.

---

# 15. LLM Layer

Location:

```text
backend/app/llm/
```

Components:

```text
client.py
extractors.py
explainers.py

prompts/
    medication_extraction.json
    explanation_builder.json
```

## LLM responsibilities

### Extraction

Convert document text into structured entities.

### Summary

Generate concise document summary.

### Critical points

Extract patient-facing points.

### Explanation

Turn structured verification findings into a readable explanation.

## LLM restrictions

The LLM must not:

- invent reference evidence;
- override the verification engine;
- independently determine unsupported/supported status;
- create citations that were not supplied;
- introduce unsupported clinical claims.

Provider and abstraction note: for the MVP prefer a Hugging Face-hosted/free inference model. The LLM client must be accessed through an application-level adapter/interface so the underlying provider (Hugging Face, OpenAI, Anthropic, or a local model) can be swapped without changing business rules or domain services. Record the model name and adapter version when producing outputs for auditability.

---

# 16. Validation Layer

Existing location:

```text
backend/app/rules/
```

## Schema validation

Validate:

- extraction output;
- verification output;
- API payloads.

## Groundedness validation

Validate:

```text
Evidence exists
        AND
Evidence belongs to selected reference
        AND
Evidence supports explanation
        AND
Citation metadata exists
```

If groundedness fails, do not present the result as a trusted grounded verification.

## Configuration

Configuration note: model names, retrieval thresholds (e.g., `TOP_K`, `SIMILARITY_THRESHOLD`), verification tolerances (dose/frequency/duration tolerances), and processing parameters must be provided via environment variables or a configuration system. These values must not be hard-coded in business logic; configuration should be injected into services and recorded with job metadata for reproducibility.

---

# 17. Async Orchestration

Location:

```text
backend/app/workers/
```

Components:

```text
celery_app.py
state_machine.py

tasks/
    parse_task.py
    verify_task.py
```

The current task structure may be expanded as needed.

Recommended logical stages:

```text
PARSE
CHUNK
EMBED
SUMMARIZE
KEY_POINTS
EXTRACT_ENTITIES
VERIFY
VALIDATE
PERSIST
```

The worker must update job state at every stage.

Failures must result in a terminal `FAILED` state with an actionable error.

Retries must be controlled and idempotent.

---

# 18. Persistence Layer

Location:

```text
backend/app/db/
```

Persistence implementation note: use SQLAlchemy ORM for DB access and manage schema changes with versioned Alembic migrations. Keep repository implementations separate from domain models and record the embedding/model metadata in the DB where applicable.

Models:

```text
document.py
job.py
result.py
```

Repositories:

```text
document_repo.py
job_repo.py
```

The MVP should persist at least:

## Document

```text
document_id
filename
document_type
role
status
content_hash
created_at
```

## Job

```text
job_id
primary_document_id
reference_document_id
status
current_stage
timestamps
error
```

## Result

```text
result_id
job_id
medication_name
status
comparisons
explanation
evidence
citation
created_at
```

The vector representation is stored in PostgreSQL + pgvector.

## Reference Documents

```text
reference_document_id
filename
uploader_user_id
mime_type
content_hash
status       # PENDING, INGESTING, READY, FAILED
revision
effective_date
created_at
```

## Reference Chunks

```text
chunk_id
reference_document_id
monograph_name
section
page
content
embedding  VECTOR
metadata   JSONB
created_at
```

Record `monograph_name`, `section`, `page`, and `metadata` to enable the highest-granularity citations (page/section/monograph).

---

# 19. API-to-Service Flow

Example:

```text
POST /documents
        ↓
DocumentService
        ↓
DocumentRepository
        ↓
document_id

POST /jobs
        ↓
JobService
        ↓
Celery
        ↓
job_id

GET /jobs/{job_id}
        ↓
JobService
        ↓
JobRepository

GET /results/{job_id}
        ↓
ResultService
        ↓
ResultRepository
```

---

# 20. Complete Processing Workflow

```text
1. Authenticate user
        ↓
2. Upload primary document
        ↓
3. Select institutional reference
        ↓
4. Create asynchronous job
        ↓
5. Parse primary document
        ↓
6. Parse/chunk/index reference if required
        ↓
7. Generate document summary
        ↓
8. Extract critical patient-facing points
        ↓
9. Extract medication entities
        ↓
10. For each medication:
        ↓
11. Retrieve targeted reference evidence
        ↓
12. Rerank evidence
        ↓
13. Compare dose
14. Compare route
15. Compare frequency
16. Compare timing
17. Compare duration
18. Compare indication
19. Check supported contraindications
        ↓
20. Determine:
        SUPPORTED
        CONTRADICTED
        UNSUPPORTED
        ↓
21. Validate groundedness
        ↓
22. Persist results
        ↓
23. Mark job COMPLETED
        ↓
24. UI retrieves/displays results
```

---

# 21. Observability

Observability is cross-cutting.

Every important operation should produce structured logs containing:

```text
request_id
user_id where appropriate
job_id
document_id
stage
operation
status
duration_ms
error
model
retrieval metadata where useful
```

Example:

```text
job_id=job-123
stage=EXTRACT_ENTITIES
status=COMPLETED
duration_ms=1250
```

Verification logs should include:

```text
medication=Pravoxil
retrieved_chunks=3
verification_status=CONTRADICTED
mismatch_parameters=["timing"]
```

Do not log sensitive document content unnecessarily.

---

# 22. Security

Implement:

- authentication;
- authorization;
- input validation;
- file-type validation;
- file-size limits;
- rate limiting;
- secure file handling;
- secrets through environment/configuration;
- restricted access to medical documents;
- audit logging.

Do not expose internal storage paths through API responses.

---

# 23. Testing Architecture

## Unit tests

Test independently:

```text
test_rule_engine.py
test_schema_val.py
test_chunking.py
test_verification.py
test_comparison.py
test_groundedness.py
```

The verification unit tests must run without an external LLM or vector database.

## Integration tests

Test:

```text
Document ingestion
RAG retrieval
Async worker
Database persistence
```

## API tests

Test:

```text
Authentication
Document upload
Job creation
Job status
Result retrieval
```

## Evaluation tests

Use a golden dataset:

```text
tests/eval/golden_datasets/formulary_discrepancies.json
```

Measure retrieval and verification quality separately.

## E2E

Test the complete Streamlit journey:

```text
Open Streamlit
→ upload primary document
→ select reference
→ start job
→ observe progress
→ view summary
→ view extracted medications
→ view verification result
→ open evidence/citation
```

---

# 24. Evaluation

Evaluation must be divided into:

## Retrieval evaluation

Examples:

```text
Recall@K
Precision@K
MRR
```

Question:

> Did the system retrieve the correct reference evidence?

## Extraction evaluation

Examples:

```text
field-level precision
field-level recall
exact/semantic match
```

Question:

> Did the system correctly extract medication and prescribing parameters?

## Verification evaluation

Measure:

```text
Supported classification accuracy
Contradicted classification accuracy
Unsupported classification accuracy
```

Question:

> Given correct evidence, did the business rules classify the prescription correctly?

## Groundedness evaluation

Question:

> Is the explanation supported by the retrieved evidence?

Do not combine these into a single opaque score.

---

# 25. Testing Golden Cases

The system should support deterministic cases such as:

### Supported

```text
Velantine
10 mg
PO
once daily
```

### Contradicted — timing

```text
Pravoxil
20 mg
morning
```

when the reference requires bedtime.

### Contradicted — duration

```text
Etrazolam
8 weeks
```

when the reference specifies a maximum of four weeks.

### Unsupported

A medication not represented by the reference.

### Supported — administration timing

A medication prescribed according to the reference's explicit timing instructions.

The expected results must be stored in the golden dataset and unit/integration tests.

---

# 26. Error Handling

Failures must be explicit.

Examples:

```text
InvalidDocumentError
ParsingError
ExtractionError
EvidenceRetrievalError
VerificationError
GroundednessError
PersistenceError
```

Each async stage must transition to:

```text
FAILED
```

with:

```text
error_code
message
stage
timestamp
```

Do not leave jobs permanently in an intermediate state.

---

# 27. Dependency Rules

Maintain these dependency boundaries:

```text
Frontend
    ↓
API
    ↓
Domain/Application Services
    ↓
Interfaces / Domain Models
    ↓
Infrastructure implementations
```

Business logic must not directly depend on:

- React;
- FastAPI request objects;
- Celery task objects;
- SQLAlchemy sessions;
- pgvector implementation details;
- specific LLM vendor SDKs.

Use interfaces/adapters where appropriate.

---

# 28. Recommended Implementation Order

Do not generate the complete system in one step.

Implement incrementally.

## Phase 1 — Domain contracts

Create:

```text
MedicationEntity
ReferenceEvidence
ParameterComparison
VerificationResult
```

Then write tests.

## Phase 2 — Verification core

Implement:

```text
rule_engine.py
verification_service.py
comparison.py
```

Verify with mocked evidence.

## Phase 3 — Ingestion

Implement:

```text
pdf_parser.py
docx_parser.py
text_cleaner.py
chunking.py
```

## Phase 4 — RAG

Implement:

```text
embeddings.py
vector_store.py
hybrid_retriever.py
reranker.py
```

## Phase 5 — LLM

Implement:

```text
client.py
extractors.py
explainers.py
```

## Phase 6 — Application services

Implement:

```text
DocumentService
JobService
SummaryService
ExtractionService
EvidenceService
ResultService
DocumentVerificationService
```

## Phase 7 — Async processing

Connect the workflow to workers and state machine.

## Phase 8 — Persistence

Connect repositories and PostgreSQL.

## Phase 9 — API

Connect FastAPI endpoints.

## Phase 10 — Frontend

Connect React UI and SSE progress.

## Phase 11 — Evaluation

Run golden dataset and quality metrics.

## Phase 12 — CI/CD

Run unit, integration, evaluation and E2E tests in CI.

---

# 29. Coding Rules for GitHub Copilot

Before generating code, Copilot must inspect the existing repository and reuse existing abstractions.

Do not rewrite unrelated files.

Do not introduce unnecessary frameworks.

Do not create duplicate models/services.

Use:

- Python type hints;
- Pydantic for domain schemas;
- dependency injection where appropriate;
- clear interfaces;
- structured logging;
- small testable functions;
- deterministic business rules;
- repository pattern for persistence.

Do not hardcode medication names into production verification rules.

Medication-specific examples belong in tests/golden datasets.

---

# 30. Definition of Done

The system architecture is considered implemented when:

- [ ] User can authenticate.
- [ ] User can upload PDF/DOCX primary document.
- [ ] User can select reference document.
- [ ] Job is created asynchronously.
- [ ] Job exposes named processing stages.
- [ ] Primary document is parsed.
- [ ] Reference document is structured and indexed.
- [ ] Summary is generated.
- [ ] Critical patient-facing points are generated.
- [ ] Medications are extracted into structured objects.
- [ ] Targeted evidence is retrieved.
- [ ] Evidence is reranked.
- [ ] Dose is compared.
- [ ] Route is compared.
- [ ] Frequency is compared.
- [ ] Timing is compared.
- [ ] Duration is compared.
- [ ] Indication is compared where supported.
- [ ] Contraindications are checked where supported.
- [ ] Result is Supported / Contradicted / Unsupported.
- [ ] Every supported/contradicted result has evidence.
- [ ] Citations preserve document/page/section metadata where available.
- [ ] Unsupported cases do not hallucinate evidence.
- [ ] Groundedness is validated.
- [ ] Results are persisted.
- [ ] Job failures are visible.
- [ ] Unit tests pass.
- [ ] Integration tests pass.
- [ ] Golden evaluation runs.
- [ ] E2E verification flow works.
- [ ] CI pipeline runs automatically.

---

# 31. Final System Mental Model

The system should always be understood as:

```text
                  USER
                   │
                   ▼
                  UI
                   │
                   ▼
                  API
                   │
                   ▼
             CREATE JOB
                   │
                   ▼
        ASYNC ORCHESTRATOR
                   │
       ┌───────────┼───────────┐
       ▼           ▼           ▼
   INGESTION      LLM          RAG
       │           │           │
       │       Extraction      │
       │       Summary         │
       │       Explanation     │
       │           │           │
       └───────────┼───────────┘
                   ▼
             BUSINESS LOGIC
                   │
                   ▼
            VERIFICATION
                   │
          ┌────────┼────────┐
          ▼        ▼        ▼
      SUPPORTED CONTRADICTED UNSUPPORTED
                   │
                   ▼
              VALIDATION
                   │
          ┌────────┴────────┐
          ▼                 ▼
     GROUNDEDNESS       SCHEMA CHECK
          │                 │
          └────────┬────────┘
                   ▼
              PERSISTENCE
                   │
                   ▼
              Streamlit UI
                   │
                   ▼
          RESULT + EVIDENCE
```

## Critical rule

**The system must never collapse this into:**

```text
Document → LLM → Answer
```

The intended architecture is:

```text
Document
   ↓
Structured extraction
   ↓
Authoritative evidence retrieval
   ↓
Deterministic business-rule verification
   ↓
Grounded explanation
   ↓
Auditable result
```

This separation is the foundation for correctness, explainability, testability and future production hardening.
