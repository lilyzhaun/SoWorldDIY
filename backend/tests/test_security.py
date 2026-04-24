from app.security import (
    create_password_cipher,
    csrf_token_matches,
    decrypt_password,
    encrypt_password,
    new_csrf_token,
)


def test_password_encryption_roundtrip() -> None:
    cipher = create_password_cipher("test-key")
    encrypted = encrypt_password(cipher, "secret")
    assert encrypted is not None
    assert encrypted != "secret"
    assert decrypt_password(cipher, encrypted) == "secret"


def test_csrf_token_matching() -> None:
    token = new_csrf_token()
    assert csrf_token_matches(token, token)
    assert not csrf_token_matches(token, "bad")
    assert not csrf_token_matches(token, None)
