import base64
import os
import secrets
from datetime import UTC, datetime, timedelta

import bcrypt
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from jose import JWTError, jwt

from src.core.config import settings

ALGORITHM = "HS256"
_NONCE_SIZE = 12


def _derive_aes_key() -> bytes:
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"claude-proxy-token-v1",
        info=b"aes-gcm-key",
    )
    return hkdf.derive(settings.SECRET_KEY.encode())


_aes_key = _derive_aes_key()
_cipher = AESGCM(_aes_key)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def generate_api_key() -> tuple[str, str, str]:
    """Return (raw_key, hashed_key, prefix_for_display)."""
    raw = "ccp_" + secrets.token_urlsafe(32)
    prefix = raw[:12]
    hashed = bcrypt.hashpw(raw.encode(), bcrypt.gensalt(rounds=12)).decode()
    return raw, hashed, prefix


def verify_api_key(raw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(raw.encode(), hashed.encode())
    except Exception:
        return False


def create_access_token(subject: str) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": subject, "exp": expire, "type": "access"},
        settings.SECRET_KEY,
        algorithm=ALGORITHM,
    )


def create_refresh_token() -> str:
    return secrets.token_urlsafe(64)


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            return None
        return payload.get("sub")
    except JWTError:
        return None


def encrypt_token(plaintext: str) -> str:
    nonce = os.urandom(_NONCE_SIZE)
    ciphertext = _cipher.encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ciphertext).decode()


def decrypt_token(ciphertext_b64: str) -> str:
    data = base64.b64decode(ciphertext_b64)
    nonce, ct = data[:_NONCE_SIZE], data[_NONCE_SIZE:]
    return _cipher.decrypt(nonce, ct, None).decode()
