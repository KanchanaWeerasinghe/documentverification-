import hashlib
import hmac
import os

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

router = APIRouter()


class LoginRequest(BaseModel):
	username: str
	password: str


@router.post("/auth/login")
def login(request: LoginRequest):
	expected_username = os.getenv("DEMO_USERNAME", "demo@example.com")
	expected_password = os.getenv("DEMO_PASSWORD", "demo")
	if not (
		hmac.compare_digest(request.username, expected_username)
		and hmac.compare_digest(request.password, expected_password)
	):
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

	token = hashlib.sha256(f"{request.username}:{expected_password}".encode()).hexdigest()
	return {"access_token": token, "token_type": "bearer", "user": {"username": request.username}}
