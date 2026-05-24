import pytest

from gateway.security import AdminSessionCipher, CookieCipher, PlaybackTokenCipher


def test_cookie_cipher_round_trip() -> None:
    cipher = CookieCipher("x" * 32)

    encrypted = cipher.encrypt("UID=1; CID=2")

    assert encrypted != "UID=1; CID=2"
    assert cipher.decrypt(encrypted) == "UID=1; CID=2"


def test_playback_token_cipher_round_trip() -> None:
    cipher = PlaybackTokenCipher("x" * 32)

    token = cipher.issue(user_id=7, media_id=42)

    assert token
    assert cipher.verify(token) == {"user_id": 7, "media_id": 42}


def test_playback_token_cipher_rejects_invalid_token() -> None:
    cipher = PlaybackTokenCipher("x" * 32)

    with pytest.raises(ValueError, match="invalid playback token"):
        cipher.verify("broken-token")


def test_admin_session_cipher_round_trip() -> None:
    cipher = AdminSessionCipher("x" * 32)

    token = cipher.issue()

    assert token
    cipher.verify(token, ttl_seconds=3600)


def test_admin_session_cipher_rejects_invalid_token() -> None:
    cipher = AdminSessionCipher("x" * 32)

    with pytest.raises(ValueError, match="invalid admin session"):
        cipher.verify("broken-token", ttl_seconds=3600)
