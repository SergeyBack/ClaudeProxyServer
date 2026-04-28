"""Unit tests for security utilities."""

from src.core.security import (
    create_access_token,
    decode_access_token,
    decrypt_token,
    encrypt_token,
    generate_api_key,
    hash_password,
    verify_api_key,
    verify_password,
)


def test_password_hash_verify():
    hashed = hash_password("mysecret")
    assert verify_password("mysecret", hashed)
    assert not verify_password("wrong", hashed)


def test_api_key_generation():
    raw, hashed, prefix = generate_api_key()
    assert raw.startswith("ccp_")
    assert prefix == raw[:12]
    assert verify_api_key(raw, hashed)
    assert not verify_api_key("ccp_wrong", hashed)


def test_jwt_encode_decode():
    token = create_access_token("user-123")
    subject = decode_access_token(token)
    assert subject == "user-123"


def test_jwt_invalid_returns_none():
    assert decode_access_token("notavalidtoken") is None


def test_token_encrypt_decrypt():
    plaintext = "sk-ant-api03-supersecretkey"
    encrypted = encrypt_token(plaintext)
    assert encrypted != plaintext
    assert decrypt_token(encrypted) == plaintext


def test_token_encrypt_different_each_time():
    # AES-GCM uses random nonce — same input produces different ciphertext
    plain = "same-secret"
    assert encrypt_token(plain) != encrypt_token(plain)
