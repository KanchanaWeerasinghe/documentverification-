from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.api.v1 import router as api_router

app = FastAPI(title="Document Verification API")

# Enable CORS for local development and tools (Swagger, Streamlit, local frontend)
app.add_middleware(
	CORSMiddleware,
	allow_origins=["http://localhost:3000", "http://localhost:8000", "http://localhost:8501", "*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
def health():
	return {"status": "ok"}
