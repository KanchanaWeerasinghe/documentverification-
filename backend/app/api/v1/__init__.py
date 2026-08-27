from fastapi import APIRouter
from backend.app.api.v1.endpoints import references
from backend.app.api.v1.endpoints import primary_documents
from backend.app.api.v1.endpoints import auth, jobs, results

router = APIRouter()

router.include_router(references.router, prefix="")
router.include_router(primary_documents.router, prefix="")
router.include_router(auth.router, prefix="")
router.include_router(jobs.router, prefix="")
router.include_router(results.router, prefix="")
