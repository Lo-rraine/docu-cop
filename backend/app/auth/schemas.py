"""Request and response schemas for authentication."""

from pydantic import BaseModel, EmailStr, field_validator


class RegisterRequest(BaseModel):
    """Register a new user with email and password."""

    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password meets minimum requirements.

        - At least 8 characters
        """
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    """Log in with email and password."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Successful authentication response with access token."""

    access_token: str
    token_type: str = "bearer"
