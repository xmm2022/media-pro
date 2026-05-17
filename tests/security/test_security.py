from gateway.security import CookieCipher


def test_cookie_cipher_round_trip() -> None:
    cipher = CookieCipher("x" * 32)

    encrypted = cipher.encrypt("UID=1; CID=2")

    assert encrypted != "UID=1; CID=2"
    assert cipher.decrypt(encrypted) == "UID=1; CID=2"
