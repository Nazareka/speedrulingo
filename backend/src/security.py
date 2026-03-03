from datetime import UTC, datetime, timedelta

import jwt
from passlib.context import CryptContext

from settings import get_settings

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    return str(pwd_context.hash(password))


def verify_password(password: str, password_hash: str) -> bool:
    return bool(pwd_context.verify(password, password_hash))


def create_access_token(user_id: str) -> str:
    settings = get_settings()
    payload = {"sub": user_id, "exp": datetime.now(UTC) + timedelta(days=7)}
    return str(jwt.encode(payload, settings.jwt_secret, algorithm="HS256"))


def decode_access_token(token: str) -> str:
    settings = get_settings()
    payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    subject = payload.get("sub")
    if not isinstance(subject, str):
        raise ValueError("Invalid subject claim")
    return subject
