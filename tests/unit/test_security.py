"""Vendor-key encryption (Fernet) + masking + rotation."""

from __future__ import annotations

import pytest

from common.crypto import SecretBox


def test_encrypt_decrypt_round_trip():
    box = SecretBox(current_key=SecretBox.generate_key())
    token = box.encrypt("super-secret-api-key")
    assert isinstance(token, bytes)
    assert token != b"super-secret-api-key"
    assert box.decrypt(token) == "super-secret-api-key"


def test_mask_hides_all_but_tail():
    assert SecretBox.mask("abcd1234efgh5678") == "••••5678"
    assert SecretBox.mask("") == ""


def test_missing_key_raises():
    box = SecretBox(current_key="")
    with pytest.raises(ValueError):
        box.encrypt("x")


def test_rotation_decrypts_with_previous_key():
    old = SecretBox.generate_key()
    new = SecretBox.generate_key()
    old_box = SecretBox(current_key=old)
    token = old_box.encrypt("rotate-me")
    # New deployment: current=new, previous=old -> still decrypts old tokens.
    rotated = SecretBox(current_key=new, previous_key=old, key_version=2)
    assert rotated.decrypt(token) == "rotate-me"


def test_wrong_key_fails():
    box1 = SecretBox(current_key=SecretBox.generate_key())
    box2 = SecretBox(current_key=SecretBox.generate_key())
    token = box1.encrypt("x")
    with pytest.raises(ValueError):
        box2.decrypt(token)
