from typing import Any

import requests


class APIError(Exception):
    """User-safe error raised for failed API calls."""


class APIClient:
    def __init__(self, base_url: str, token: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.token = token

    def request(self, method: str, path: str, **kwargs) -> Any:
        headers = kwargs.pop("headers", {})
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            response = requests.request(
                method,
                f"{self.base_url}{path}",
                headers=headers,
                timeout=30,
                **kwargs,
            )
            if not response.ok:
                raise APIError("The server could not complete that request.")
            return response.json()
        except requests.RequestException as exc:
            raise APIError("The verification service is unavailable.") from exc

    def login(self, username: str, password: str):
        return self.request(
            "POST",
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )

    def ingest_reference(self):
        return self.request("POST", "/api/v1/references")

    def start_verification(self, reference_id: int):
        return self.request(
            "POST",
            "/api/v1/primary-documents",
            params={"reference_id": reference_id},
        )

    def get_job_status(self, job_id: int):
        return self.request("GET", f"/api/v1/jobs/{job_id}")

    def get_results(self, job_id: int):
        return self.request("GET", f"/api/v1/jobs/{job_id}/results")
