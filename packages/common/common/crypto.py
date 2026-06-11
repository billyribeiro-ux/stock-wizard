"""Symmetric encryption for vendor API keys (Fernet / AES-128-CBC + HMAC).

The master key comes from the environment (never the DB, never the repo, never the
browser). ``key_version`` on stored rows lets us rotate keys: encrypt always uses the
current key; decrypt tries current then previous. If MASTER_KEY is lost, stored vendor
keys are unrecoverable by design.
"""

from __future__ import annotations

from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken, MultiFernet


@dataclass(frozen=True)
class SecretBox:
    """Wraps Fernet encryption with optional key rotation support."""

    current_key: str
    previous_key: str | None = None
    key_version: int = 1

    def _current(self) -> Fernet:
        if not self.current_key:
            raise ValueError("MASTER_KEY is not set; cannot encrypt/decrypt vendor keys")
        return Fernet(self.current_key.encode())

    def _multi(self) -> MultiFernet:
        keys = [self._current()]
        if self.previous_key:
            keys.append(Fernet(self.previous_key.encode()))
        return MultiFernet(keys)

    def encrypt(self, plaintext: str) -> bytes:
        return self._current().encrypt(plaintext.encode())

    def decrypt(self, token: bytes) -> str:
        try:
            return self._multi().decrypt(token).decode()
        except InvalidToken as exc:  # pragma: no cover - defensive
            raise ValueError("could not decrypt vendor key (wrong/rotated MASTER_KEY?)") from exc

    @staticmethod
    def mask(plaintext: str, visible: int = 4) -> str:
        """Return a safe display form like ``••••1234``."""
        if not plaintext:
            return ""
        tail = plaintext[-visible:] if len(plaintext) > visible else plaintext
        return "•" * 4 + tail

    @staticmethod
    def generate_key() -> str:
        """Generate a new urlsafe-base64 Fernet key."""
        return Fernet.generate_key().decode()
