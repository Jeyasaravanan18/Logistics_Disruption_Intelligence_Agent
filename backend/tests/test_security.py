from datetime import timedelta

from jose import jwt

from config import JWT_ALGORITHM, JWT_SECRET_KEY
from security import create_access_token, get_password_hash, hash_token, verify_password


def test_password_hash_roundtrip():
    hashed = get_password_hash("Secret123")
    assert hashed != "Secret123"
    assert verify_password("Secret123", hashed)
    assert not verify_password("wrongpass1", hashed)


def test_access_token_contains_subject():
    token = create_access_token("ops@example.com", timedelta(minutes=5))
    payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    assert payload["sub"] == "ops@example.com"
    assert payload["type"] == "access"


def test_refresh_token_hash_is_stable():
    assert hash_token("abc") == hash_token("abc")
    assert hash_token("abc") != hash_token("abd")
