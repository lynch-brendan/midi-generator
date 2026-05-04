import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from jose import jwt, JWTError
from fastapi import Request
from sqlalchemy.orm import Session

JWT_SECRET = os.environ.get("JWT_SECRET", "insecure-dev-secret-change-me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_DAYS = 30

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
APP_URL = os.environ.get("APP_URL", "http://localhost:8000")


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def create_jwt(user_id: str) -> str:
    expiry = datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRY_DAYS)
    payload = {"sub": user_id, "exp": expiry}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


def get_current_user(request: Request, db: Optional[Session]):
    """Return the User ORM object for the authenticated user, or None."""
    if db is None:
        return None

    token = request.cookies.get("token")
    if not token:
        return None

    user_id = decode_jwt(token)
    if not user_id:
        return None

    from core.models import User  # local import to avoid circular dependency
    return db.query(User).filter(User.id == user_id).first()


# ---------------------------------------------------------------------------
# Google OAuth helpers
# ---------------------------------------------------------------------------

def google_auth_url() -> str:
    redirect_uri = APP_URL.rstrip("/") + "/auth/callback"
    params = (
        "response_type=code"
        f"&client_id={GOOGLE_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        "&scope=openid%20email%20profile"
        "&access_type=offline"
        "&prompt=select_account"
    )
    return f"https://accounts.google.com/o/oauth2/v2/auth?{params}"


async def exchange_google_code(code: str) -> dict:
    """Exchange an OAuth authorization code for user profile data.

    Returns a dict with keys: google_id, email, name, picture.
    Raises httpx.HTTPStatusError on failure.
    """
    redirect_uri = APP_URL.rstrip("/") + "/auth/callback"

    async with httpx.AsyncClient() as client:
        # Exchange code for tokens
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        token_resp.raise_for_status()
        tokens = token_resp.json()
        access_token = tokens["access_token"]

        # Fetch user info
        userinfo_resp = await client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        userinfo_resp.raise_for_status()
        info = userinfo_resp.json()

    return {
        "google_id": info["sub"],
        "email": info.get("email", ""),
        "name": info.get("name", ""),
        "picture": info.get("picture"),
    }
