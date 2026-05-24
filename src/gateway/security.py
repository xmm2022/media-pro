import base64
import hashlib
import json

from cryptography.fernet import Fernet, InvalidToken


class CookieCipher:
    def __init__(self, secret: str) -> None:
        key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
        self._fernet = Fernet(key)

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, value: str) -> str:
        return self._fernet.decrypt(value.encode()).decode()


class PlaybackTokenCipher:
    def __init__(self, secret: str) -> None:
        key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
        self._fernet = Fernet(key)

    def issue(self, *, user_id: int, media_id: int) -> str:
        payload = json.dumps({"user_id": user_id, "media_id": media_id}, separators=(",", ":"))
        return self._fernet.encrypt(payload.encode()).decode()

    def verify(self, token: str, *, ttl_seconds: int = 3600) -> dict[str, int]:
        try:
            payload = self._fernet.decrypt(token.encode(), ttl=ttl_seconds)
        except InvalidToken as exc:
            raise ValueError("invalid playback token") from exc
        data = json.loads(payload.decode())
        user_id = data.get("user_id")
        media_id = data.get("media_id")
        if not isinstance(user_id, int) or not isinstance(media_id, int):
            raise ValueError("invalid playback token")
        return {"user_id": user_id, "media_id": media_id}


class AdminSessionCipher:
    def __init__(self, secret: str) -> None:
        key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
        self._fernet = Fernet(key)

    def issue(self) -> str:
        payload = json.dumps({"role": "admin"}, separators=(",", ":"))
        return self._fernet.encrypt(payload.encode()).decode()

    def verify(self, token: str, *, ttl_seconds: int) -> None:
        try:
            payload = self._fernet.decrypt(token.encode(), ttl=ttl_seconds)
        except InvalidToken as exc:
            raise ValueError("invalid admin session") from exc
        try:
            data = json.loads(payload.decode())
        except ValueError as exc:
            raise ValueError("invalid admin session") from exc
        if data.get("role") != "admin":
            raise ValueError("invalid admin session")
