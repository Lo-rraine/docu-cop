import os
import jwt
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from openai import OpenAI

from app.config import settings

# Ensure OpenAI credentials are in os.environ for pydantic-ai
os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)
from app.auth import get_current_user
from app.auth.password import hash_password, verify_password
from app.auth.schemas import RegisterRequest, LoginRequest
from app.database import get_db
from app.database.models import User
from app.api.chat import router as chat_router
from app.api.documents import router as documents_router
from app.retrieval.retriever import DocumentRetriever


app = FastAPI(title="Document Copilot")

# Include routers
app.include_router(chat_router, prefix="/chat", tags=["chat"])
app.include_router(documents_router, prefix="/documents", tags=["documents"])


@app.on_event("startup")
def startup():
    """Initialize OpenAI client and retriever on startup."""
    app.state.openai_client = OpenAI(api_key=settings.openai_api_key)
    app.state.retriever = DocumentRetriever(app.state.openai_client)

# Configure CORS
print("\n" + "="*60)
print("ALLOWED_ORIGINS RAW:", repr(settings.allowed_origins))
origins = [origin.strip() for origin in settings.allowed_origins.split(",")]
print("ALLOWED_ORIGINS PARSED:", origins)
print("="*60 + "\n")

# TEMPORARY TEST: Hardcode origins to isolate the issue
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.get("/health")
def health_check():
    """Health check endpoint (no auth required)."""
    return {"status": "ok"}


@app.post("/auth/register")
def register(
    request: RegisterRequest,
    db: Session = Depends(get_db),
):
    """Register a new user and set authentication cookie.

    Validates email and password, ensures email uniqueness, hashes the password,
    creates the user, generates a JWT, and sets it as an HttpOnly cookie.

    Args:
        request: RegisterRequest with email and password
        db: Database session

    Returns:
        JSON response with success status. JWT set as HttpOnly cookie.

    Raises:
        400: Invalid email or password
        409: Email already registered
    """
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Hash password and create user
    password_hash = hash_password(request.password)
    user = User(email=request.email, password_hash=password_hash)
    db.add(user)
    db.commit()
    db.refresh(user)

    # Generate JWT token
    payload = {
        "sub": user.email,
        "exp": datetime.utcnow() + timedelta(hours=24),
    }
    access_token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")

    # Set JWT as HttpOnly cookie
    response = JSONResponse({"success": True, "email": user.email})
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,  # HTTPS only in production
        samesite="lax",  # Works with HTTP in development, valid cross-origin setting
        max_age=86400,  # 24 hours
        path="/",
    )
    return response


@app.post("/auth/login")
def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
):
    """Authenticate a user with email and password.

    Looks up user by email, verifies the password hash, generates a JWT,
    and sets it as an HttpOnly cookie.

    Args:
        request: LoginRequest with email and password
        db: Database session

    Returns:
        JSON response with success status. JWT set as HttpOnly cookie.

    Raises:
        401: Invalid email/password combination or user not found
    """
    # Look up user by email
    user = db.query(User).filter(User.email == request.email).first()

    # Verify password (constant-time comparison)
    # Return 401 for both "user not found" and "password mismatch" for security
    if not user or not verify_password(request.password, user.password_hash or ""):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Generate JWT token
    payload = {
        "sub": user.email,
        "exp": datetime.utcnow() + timedelta(hours=24),
    }
    access_token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")

    # Set JWT as HttpOnly cookie
    response = JSONResponse({"success": True, "email": user.email})
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,  # HTTPS only in production
        samesite="lax",  # Works with HTTP in development, valid cross-origin setting
        max_age=86400,  # 24 hours
        path="/",
    )
    return response


@app.post("/auth/logout")
def logout():
    """Clear authentication cookie and log out user.

    Returns:
        JSON response with success status. access_token cookie cleared.
    """
    response = JSONResponse({"success": True})
    response.delete_cookie(
        key="access_token",
        path="/",
        samesite="lax",
        secure=False,
    )
    return response


@app.post("/auth/token")
def get_token(email: str = "test@example.com"):
    """Generate a JWT token for the given email.

    Usage: POST /auth/token?email=user@example.com
    Returns: {"access_token": "eyJ...", "token_type": "bearer"}

    DEPRECATED: Use /auth/register for production. This endpoint is for development only.
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
