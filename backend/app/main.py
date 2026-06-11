import jwt
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.auth import get_current_user
from app.database.models import User

app = FastAPI(title="Document Copilot")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    """Health check endpoint (no auth required)."""
    return {"status": "ok"}


@app.post("/auth/token")
def get_token(email: str = "test@example.com"):
    """Generate a JWT token for the given email.

    Usage: POST /auth/token?email=user@example.com
    Returns: {"access_token": "eyJ...", "token_type": "bearer"}
    """
    payload = {
        "sub": email,
        "exp": datetime.utcnow() + timedelta(hours=24),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    return {"access_token": token, "token_type": "bearer"}


@app.get("/me")
def get_me(user: User = Depends(get_current_user)):
    """Get current authenticated user info."""
    return {"id": str(user.id), "email": user.email}
