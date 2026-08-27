from fastapi import APIRouter
from backend.app.api.v1.endpoints import references

router = APIRouter()

# For now only register the references endpoint. Other endpoints will be included
# when their routers are implemented.
router.include_router(references.router, prefix="", tags=["references"])

