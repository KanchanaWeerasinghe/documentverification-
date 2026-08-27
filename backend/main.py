"""Run the backend FastAPI app with Uvicorn.

Usage (from repository root):
    python -m backend.main
or:
    python backend/main.py

This starts the app at http://0.0.0.0:8000 and exposes the Swagger UI at /docs.
"""
import uvicorn


def main():
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
