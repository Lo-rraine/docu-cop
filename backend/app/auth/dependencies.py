import jwt
import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.database.models import User

security = HTTPBearer()
logger = logging.getLogger(__name__)


async def get_current_user(
    credentials=Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Verify JWT token and return the authenticated user.

    Extracts the JWT from Authorization: Bearer header, verifies its signature,
    and returns or creates the corresponding user. Rejects expired/invalid tokens
    with 401 Unauthorized.
    """
    token = credentials.credentials

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
