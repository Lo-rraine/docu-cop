import jwt
import logging
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.database.models import User

security = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Verify JWT token from cookie or Authorization header and return the authenticated user.

    Tries to extract JWT from:
    1. HttpOnly cookie (primary) - set by /auth/register and /auth/login
    2. Authorization: Bearer header (fallback) - for migration and API clients

    Verifies the signature and returns the corresponding user.
    Creates user on first login if they don't exist (legacy behavior).

    Args:
        request: FastAPI Request object (for cookie access)
        credentials: Optional Authorization header (HTTPBearer)
        db: Database session

    Returns:
        User object for the authenticated email

    Raises:
        401: If no valid token found in cookie or header, or token is invalid/expired
    """
    token = None

    # Primary: Try to get token from HttpOnly cookie
    token = request.cookies.get("access_token")

    # Fallback: Try to get token from Authorization header (migration support)
    if not token and credentials:
        token = credentials.credentials

    # No token found anywhere
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify JWT signature and claims
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
        )
    except jwt.InvalidTokenError as e:
        logger.error(f"JWT decode failed: {type(e).__name__}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    email = payload.get("sub")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(email=email)
        db.add(user)
        db.commit()
        db.refresh(user)

    return user
