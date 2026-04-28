"""Comprehensive unit tests for all security functions in src/core/security.py."""

from datetime import UTC, datetime, timedelta

import pytest
from jose import jwt

from src.core.config import settings
from src.core.security import (
    ALGORITHM,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decrypt_token,
    encrypt_token,
    generate_api_key,
    hash_password,
    verify_api_key,
    verify_password,
)


def test_encrypt_decrypt_roundtrip():
    plaintext = "sk-ant-api03-supersecretkey"
    encrypted = encrypt_token(plaintext)
    assert decrypt_token(encrypted) == plaintext


def test_encrypt_produces_different_ciphertext_each_time():
    """AES-GCM uses a random 12-byte nonce — same plaintext → different ciphertext."""
    plain = "same-secret-value"
    enc1 = encrypt_token(plain)
    enc2 = encrypt_token(plain)
    assert enc1 != enc2


def test_decrypt_returns_original_plaintext():
    plain = "hello world"
    assert decrypt_token(encrypt_token(plain)) == plain


def test_encrypt_output_is_base64_string():
    import base64

    encrypted = encrypt_token("test-token")
    # Should be valid base64
    decoded = base64.b64decode(encrypted)
    # nonce (12 bytes) + ciphertext (at least as long as plaintext) + GCM tag (16 bytes)
    assert len(decoded) >= 12 + len("test-token") + 16


def test_encrypt_empty_string():
    encrypted = encrypt_token("")
    assert decrypt_token(encrypted) == ""


def test_encrypt_long_token():
    long_token = "sk-ant-" + "x" * 200
    encrypted = encrypt_token(long_token)
    assert decrypt_token(encrypted) == long_token


def test_encrypt_unicode_token():
    unicode_token = "tök€n-wïth-ünïcödé"
    encrypted = encrypt_token(unicode_token)
    assert decrypt_token(encrypted) == unicode_token


def test_decrypt_invalid_base64_raises():
    with pytest.raises(Exception):
        decrypt_token("this is not base64!!!")


def test_decrypt_tampered_ciphertext_raises():
    encrypted = encrypt_token("original")
    # Tamper with the ciphertext (flip a byte in the middle)
    import base64

    raw = bytearray(base64.b64decode(encrypted))
    raw[20] ^= 0xFF  # flip bits in ciphertext portion
    tampered = base64.b64encode(bytes(raw)).decode()
    with pytest.raises(Exception):
        decrypt_token(tampered)


def test_hash_password_returns_string():
    hashed = hash_password("mysecret")
    assert isinstance(hashed, str)
    assert len(hashed) > 0


def test_hash_password_starts_with_bcrypt_prefix():
    hashed = hash_password("mysecret")
    assert hashed.startswith("$2b$")


def test_verify_password_correct():
    hashed = hash_password("correcthorse")
    assert verify_password("correcthorse", hashed) is True


def test_verify_password_wrong():
    hashed = hash_password("correcthorse")
    assert verify_password("wrong", hashed) is False


def test_verify_password_empty_vs_nonempty():
    hashed = hash_password("notempty")
    assert verify_password("", hashed) is False


def test_verify_password_empty_password():
    hashed = hash_password("")
    assert verify_password("", hashed) is True
    assert verify_password("notempty", hashed) is False


def test_hash_same_password_produces_different_hashes():
    """bcrypt uses a random salt — each call produces a unique hash."""
    h1 = hash_password("same")
    h2 = hash_password("same")
    assert h1 != h2
    # Both should still verify correctly
    assert verify_password("same", h1)
    assert verify_password("same", h2)


def test_verify_password_invalid_hash_returns_false():
    assert verify_password("anypass", "not-a-valid-bcrypt-hash") is False


def test_verify_password_case_sensitive():
    hashed = hash_password("Secret123")
    assert verify_password("Secret123", hashed) is True
    assert verify_password("secret123", hashed) is False
    assert verify_password("SECRET123", hashed) is False


def test_generate_api_key_returns_tuple():
    result = generate_api_key()
    assert isinstance(result, tuple)
    assert len(result) == 3


def test_generate_api_key_raw_starts_with_ccp():
    raw, _, _ = generate_api_key()
    assert raw.startswith("ccp_")


def test_generate_api_key_prefix_is_first_12_chars():
    raw, _, prefix = generate_api_key()
    assert prefix == raw[:12]
    assert prefix.startswith("ccp_")


def test_generate_api_key_prefix_length():
    _, _, prefix = generate_api_key()
    assert len(prefix) == 12


def test_generate_api_key_raw_length():
    """ccp_ (4) + token_urlsafe(32) should be at least 4+43=47 chars."""
    raw, _, _ = generate_api_key()
    assert len(raw) >= 40


def test_generate_api_key_is_unique():
    raw1, _, _ = generate_api_key()
    raw2, _, _ = generate_api_key()
    assert raw1 != raw2


def test_verify_api_key_correct():
    raw, hashed, _ = generate_api_key()
    assert verify_api_key(raw, hashed) is True


def test_verify_api_key_wrong_key():
    _, hashed, _ = generate_api_key()
    assert verify_api_key("ccp_wrong_key_totally_wrong", hashed) is False


def test_verify_api_key_empty_string():
    _, hashed, _ = generate_api_key()
    assert verify_api_key("", hashed) is False


def test_verify_api_key_invalid_hash_returns_false():
    assert verify_api_key("ccp_somekey", "not-valid-bcrypt") is False


def test_verify_api_key_cross_keys():
    """Key from one generation should not match hash from another."""
    raw1, hashed1, _ = generate_api_key()
    raw2, hashed2, _ = generate_api_key()
    assert verify_api_key(raw1, hashed2) is False
    assert verify_api_key(raw2, hashed1) is False


def test_create_access_token_returns_string():
    token = create_access_token("user-123")
    assert isinstance(token, str)
    assert len(token) > 0


def test_decode_access_token_returns_subject():
    token = create_access_token("user-abc")
    subject = decode_access_token(token)
    assert subject == "user-abc"


def test_decode_access_token_uuid_subject():
    import uuid

    user_id = str(uuid.uuid4())
    token = create_access_token(user_id)
    assert decode_access_token(token) == user_id


def test_decode_access_token_invalid_returns_none():
    assert decode_access_token("notavalidtoken") is None


def test_decode_access_token_garbage_returns_none():
    assert decode_access_token("") is None
    assert decode_access_token("garbage.garbage.garbage") is None
    assert decode_access_token("   ") is None


def test_decode_access_token_expired_returns_none():
    """Forge an expired token manually."""
    expired_payload = {
        "sub": "user-expired",
        "exp": datetime.now(UTC) - timedelta(minutes=1),
        "type": "access",
    }
    expired_token = jwt.encode(expired_payload, settings.SECRET_KEY, algorithm=ALGORITHM)
    result = decode_access_token(expired_token)
    assert result is None


def test_decode_access_token_wrong_type_returns_none():
    """Token with type != 'access' should be rejected."""
    payload = {
        "sub": "user-123",
        "exp": datetime.now(UTC) + timedelta(minutes=15),
        "type": "refresh",  # wrong type
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)
    assert decode_access_token(token) is None


def test_decode_access_token_no_type_field_returns_none():
    """Token missing 'type' claim should be rejected."""
    payload = {
        "sub": "user-123",
        "exp": datetime.now(UTC) + timedelta(minutes=15),
        # no "type" field
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)
    assert decode_access_token(token) is None


def test_decode_access_token_wrong_secret_returns_none():
    payload = {
        "sub": "user-123",
        "exp": datetime.now(UTC) + timedelta(minutes=15),
        "type": "access",
    }
    token = jwt.encode(payload, "wrong-secret-key", algorithm=ALGORITHM)
    assert decode_access_token(token) is None


def test_create_access_token_contains_correct_claims():
    """Decode raw JWT to verify structure."""
    token = create_access_token("user-xyz")
    # Decode without verification to inspect claims
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["sub"] == "user-xyz"
    assert payload["type"] == "access"
    assert "exp" in payload


def test_access_token_expiry_is_in_future():
    token = create_access_token("user-123")
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    exp = datetime.fromtimestamp(payload["exp"], tz=UTC)
    assert exp > datetime.now(UTC)


def test_access_token_expiry_respects_settings():
    token = create_access_token("user-123")
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    exp = datetime.fromtimestamp(payload["exp"], tz=UTC)
    expected_exp = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    # Allow 5 seconds of tolerance
    assert abs((exp - expected_exp).total_seconds()) < 5


def test_create_refresh_token_returns_string():
    token = create_refresh_token()
    assert isinstance(token, str)
    assert len(token) > 0


def test_create_refresh_token_is_unique():
    t1 = create_refresh_token()
    t2 = create_refresh_token()
    assert t1 != t2


def test_create_refresh_token_length():
    """token_urlsafe(64) produces at least 64 chars (base64url-encoded)."""
    token = create_refresh_token()
    assert len(token) >= 64
