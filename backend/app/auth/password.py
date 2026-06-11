"""Password hashing utilities using Argon2."""

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError

hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2.

    Args:
        password: The plaintext password to hash.

    Returns:
        The Argon2 password hash (safe to store in database).

    Raises:
        argon2.exceptions.HashingError: If hashing fails.
    """
    return hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against its hash.

    Uses constant-time comparison to prevent timing attacks.

    Args:
        password: The plaintext password to verify.
        password_hash: The Argon2 hash from the database.

    Returns:
        True if the password matches the hash, False otherwise.
    """
    if not password_hash:
        return False

    try:
        hasher.verify(password_hash, password)
        return True
    except (VerifyMismatchError, VerificationError):
        return False
