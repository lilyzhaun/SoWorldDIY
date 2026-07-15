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


def test_encrypt_decrypt_none_and_invalid_token() -> None:
    from app.security import create_password_cipher, decrypt_password, encrypt_password

    cipher = create_password_cipher("unit-test-key-for-security")
    assert encrypt_password(cipher, None) is None
    assert decrypt_password(cipher, None) is None
    assert decrypt_password(cipher, "") is None
    assert decrypt_password(cipher, "not-a-valid-fernet-token") is None


def test_csrf_token_matches_edge_cases() -> None:
    from app.security import csrf_token_matches, new_csrf_token

    token = new_csrf_token()
    assert csrf_token_matches(token, token) is True
    assert csrf_token_matches(None, token) is False
    assert csrf_token_matches(token, None) is False
    assert csrf_token_matches("", token) is False
    assert csrf_token_matches(token, "wrong") is False
