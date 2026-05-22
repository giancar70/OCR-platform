from datetime import datetime, timedelta, timezone

from jose import jwt

from app.config import settings
from app.core.security import hash_password, verify_password, create_access_token, decode_access_token


def test_hash_is_not_plaintext():
    assert hash_password("secret") != "secret"


def test_verify_correct_password():
    hashed = hash_password("mypassword")
    assert verify_password("mypassword", hashed) is True


def test_verify_wrong_password():
    hashed = hash_password("mypassword")
    assert verify_password("wrong", hashed) is False


def test_create_and_decode_token():
    token = create_access_token("user@example.com")
    assert decode_access_token(token) == "user@example.com"


def test_decode_invalid_token():
    assert decode_access_token("not.a.valid.token") is None


def test_decode_expired_token():
    expired = datetime.now(timezone.utc) - timedelta(minutes=1)
    token = jwt.encode(
        {"sub": "user@example.com", "exp": expired},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    assert decode_access_token(token) is None
