"""Test suite for POST /auth/register endpoint.

Run with: pytest tests/test_auth_register.py -v
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database.models import User
from app.auth.password import verify_password


client = TestClient(app)


class TestRegister:
    """Test registration endpoint."""

    def test_register_success(self, db: Session):
        """Register with valid email and password returns access token."""
        response = client.post(
            "/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "securepassword123",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert isinstance(data["access_token"], str)
        assert len(data["access_token"]) > 0

        # Verify user was created in database
        user = db.query(User).filter(User.email == "newuser@example.com").first()
        assert user is not None
        assert user.email == "newuser@example.com"
        assert verify_password("securepassword123", user.password_hash)

    def test_register_duplicate_email(self, db: Session):
        """Register with existing email returns 409 Conflict."""
        # Create first user
        client.post(
            "/auth/register",
            json={"email": "existing@example.com", "password": "password123"},
        )

        # Try to register with same email
        response = client.post(
            "/auth/register",
            json={"email": "existing@example.com", "password": "different123"},
        )

        assert response.status_code == 409
        assert response.json()["detail"] == "Email already registered"

    def test_register_invalid_email(self):
        """Register with invalid email format returns 422."""
        response = client.post(
            "/auth/register",
            json={
                "email": "not-an-email",
                "password": "securepassword123",
            },
        )

        assert response.status_code == 422
        assert "email" in response.json()["detail"][0]["loc"]

    def test_register_short_password(self):
        """Register with password < 8 chars returns 422."""
        response = client.post(
            "/auth/register",
            json={
                "email": "user@example.com",
                "password": "short",
            },
        )

        assert response.status_code == 422
        assert "password" in str(response.json()).lower()

    def test_register_empty_password(self):
        """Register with empty password returns 422."""
        response = client.post(
            "/auth/register",
            json={
                "email": "user@example.com",
                "password": "",
            },
        )

        assert response.status_code == 422

    def test_register_missing_email(self):
        """Register without email returns 422."""
        response = client.post(
            "/auth/register",
            json={"password": "securepassword123"},
        )

        assert response.status_code == 422
        assert "email" in response.json()["detail"][0]["loc"]

    def test_register_missing_password(self):
        """Register without password returns 422."""
        response = client.post(
            "/auth/register",
            json={"email": "user@example.com"},
        )

        assert response.status_code == 422
        assert "password" in response.json()["detail"][0]["loc"]

    def test_register_token_can_authenticate(self, db: Session):
        """Token from registration can authenticate subsequent requests."""
        register_response = client.post(
            "/auth/register",
            json={
                "email": "authtest@example.com",
                "password": "testpassword123",
            },
        )

        access_token = register_response.json()["access_token"]

        # Use token to call /me endpoint
        me_response = client.get(
            "/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert me_response.status_code == 200
        user_data = me_response.json()
        assert user_data["email"] == "authtest@example.com"

    def test_register_password_hashed_not_stored(self, db: Session):
        """Password is hashed and not stored in plaintext."""
        plaintext_password = "myplaintextpassword"

        client.post(
            "/auth/register",
            json={
                "email": "hash@example.com",
                "password": plaintext_password,
            },
        )

        user = db.query(User).filter(User.email == "hash@example.com").first()
        # Password should not be plaintext
        assert user.password_hash != plaintext_password
        # But should verify correctly
        assert verify_password(plaintext_password, user.password_hash)


class TestLogin:
    """Test login endpoint."""

    def test_login_success(self, db: Session):
        """Login with correct credentials returns access token."""
        # Register user first
        register_email = "login@example.com"
        register_password = "correctpassword123"
        client.post(
            "/auth/register",
            json={
                "email": register_email,
                "password": register_password,
            },
        )

        # Login with correct credentials
        response = client.post(
            "/auth/login",
            json={
                "email": register_email,
                "password": register_password,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert isinstance(data["access_token"], str)
        assert len(data["access_token"]) > 0

    def test_login_wrong_password(self, db: Session):
        """Login with wrong password returns 401."""
        # Register user
        client.post(
            "/auth/register",
            json={
                "email": "wrongpwd@example.com",
                "password": "correctpassword123",
            },
        )

        # Login with wrong password
        response = client.post(
            "/auth/login",
            json={
                "email": "wrongpwd@example.com",
                "password": "wrongpassword123",
            },
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid email or password"

    def test_login_nonexistent_user(self):
        """Login with non-existent email returns 401."""
        response = client.post(
            "/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "anypassword123",
            },
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid email or password"

    def test_login_invalid_email_format(self):
        """Login with invalid email format returns 422."""
        response = client.post(
            "/auth/login",
            json={
                "email": "not-an-email",
                "password": "password123",
            },
        )

        assert response.status_code == 422

    def test_login_missing_email(self):
        """Login without email returns 422."""
        response = client.post(
            "/auth/login",
            json={"password": "password123"},
        )

        assert response.status_code == 422

    def test_login_missing_password(self):
        """Login without password returns 422."""
        response = client.post(
            "/auth/login",
            json={"email": "user@example.com"},
        )

        assert response.status_code == 422

    def test_login_token_can_authenticate(self, db: Session):
        """Token from login can authenticate subsequent requests."""
        # Register user
        register_email = "authtest2@example.com"
        register_password = "testpassword123"
        client.post(
            "/auth/register",
            json={
                "email": register_email,
                "password": register_password,
            },
        )

        # Login
        login_response = client.post(
            "/auth/login",
            json={
                "email": register_email,
                "password": register_password,
            },
        )

        access_token = login_response.json()["access_token"]

        # Use token to call /me endpoint
        me_response = client.get(
            "/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert me_response.status_code == 200
        user_data = me_response.json()
        assert user_data["email"] == register_email


class TestAuthFlow:
    """Test complete auth flows."""

    def test_register_then_login_then_me(self, db: Session):
        """Complete flow: register → login → get /me."""
        email = "flowtest@example.com"
        password = "flowpassword123"

        # Step 1: Register
        register_response = client.post(
            "/auth/register",
            json={"email": email, "password": password},
        )
        assert register_response.status_code == 200
        register_token = register_response.json()["access_token"]

        # Verify registered user can access /me with registration token
        me_response_1 = client.get(
            "/me",
            headers={"Authorization": f"Bearer {register_token}"},
        )
        assert me_response_1.status_code == 200
        assert me_response_1.json()["email"] == email

        # Step 2: Login
        login_response = client.post(
            "/auth/login",
            json={"email": email, "password": password},
        )
        assert login_response.status_code == 200
        login_token = login_response.json()["access_token"]

        # Both tokens should work (same user)
        me_response_2 = client.get(
            "/me",
            headers={"Authorization": f"Bearer {login_token}"},
        )
        assert me_response_2.status_code == 200
        assert me_response_2.json()["email"] == email

    def test_register_multiple_users_independent_logins(self, db: Session):
        """Multiple users can register and login independently."""
        user1_email = "user1@example.com"
        user1_password = "password1"
        user2_email = "user2@example.com"
        user2_password = "password2"

        # Register user 1
        client.post(
            "/auth/register",
            json={"email": user1_email, "password": user1_password},
        )

        # Register user 2
        client.post(
            "/auth/register",
            json={"email": user2_email, "password": user2_password},
        )

        # Login as user 1
        token1 = client.post(
            "/auth/login",
            json={"email": user1_email, "password": user1_password},
        ).json()["access_token"]

        # Login as user 2
        token2 = client.post(
            "/auth/login",
            json={"email": user2_email, "password": user2_password},
        ).json()["access_token"]

        # Verify user 1 sees correct identity
        me1 = client.get(
            "/me",
            headers={"Authorization": f"Bearer {token1}"},
        ).json()
        assert me1["email"] == user1_email

        # Verify user 2 sees correct identity
        me2 = client.get(
            "/me",
            headers={"Authorization": f"Bearer {token2}"},
        ).json()
        assert me2["email"] == user2_email

        # Verify they're different users
        assert me1["id"] != me2["id"]


@pytest.fixture
def db():
    """Provide a test database session.

    NOTE: This is a placeholder. Implement actual DB fixture based on your test setup.
    You'll need to:
    1. Create a test database
    2. Run migrations on test DB
    3. Yield a session
    4. Clean up after test
    """
    from app.database import SessionLocal

    db = SessionLocal()
    yield db
    db.close()
