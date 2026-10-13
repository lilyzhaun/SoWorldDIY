from __future__ import annotations

import base64
import logging
import secrets
from hashlib import sha256

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


def create_password_cipher(encryption_key: str) -> Fernet:
    return Fernet(base64.urlsafe_b64encode(sha256(encryption_key.encode()).digest()))


def encrypt_password(cipher: Fernet, password: str | None) -> str | None:
    if password is None:
        return None
    return cipher.encrypt(password.encode("utf-8")).decode("utf-8")


def decrypt_password(cipher: Fernet, encrypted_password: str | None) -> str | None:
    if not encrypted_password:
        return None
    try:
        return cipher.decrypt(encrypted_password.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        logger.warning("Stored password cannot be decrypted; silent relogin skipped")
        return None


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def csrf_token_matches(expected: str | None, provided: str | None) -> bool:
    if not expected or not provided or not expected.isascii() or not provided.isascii():
        return False
    return secrets.compare_digest(expected, provided)
