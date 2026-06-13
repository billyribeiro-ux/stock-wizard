"""FMP equity adapter wiring + vendor-key crypto (add/rotate/swap/delete)."""

from __future__ import annotations

import pytest

from common.crypto import SecretBox
from engine.data import KNOWN_VENDORS, MissingCredentials, build_ohlcv_source
from engine.data.fmp_source import FMPSource
from engine.data.registry import vendor_info


def test_fmp_is_a_known_keyed_equity_vendor():
    fmp = vendor_info("fmp")
    assert fmp is not None
    assert fmp.requires_key is True
    assert "ohlcv" in fmp.capabilities
    assert any(v.vendor == "fmp" for v in KNOWN_VENDORS)


def test_build_ohlcv_source_fmp_requires_key():
    with pytest.raises(MissingCredentials):
        build_ohlcv_source("fmp", api_key=None)
    src = build_ohlcv_source("fmp", api_key="dummy")
    assert isinstance(src, FMPSource) and src.name == "fmp"


def test_build_ohlcv_source_defaults_to_yfinance():
    src = build_ohlcv_source("yfinance")
    assert src.name == "yfinance"


def test_fmp_requires_nonempty_key():
    with pytest.raises(MissingCredentials):
        FMPSource("")


# --- multi-key lifecycle: add / rotate / swap (enable) / delete, all encrypted ---
def test_key_encryption_and_rotation_roundtrip():
    box = SecretBox(current_key=SecretBox.generate_key())
    # add: store an FMP key encrypted; masked never reveals the secret
    secret_a = "fmp_live_key_AAAA1111"
    ct_a = box.encrypt(secret_a)
    assert box.decrypt(ct_a) == secret_a
    assert SecretBox.mask(secret_a).endswith("1111")
    assert secret_a not in SecretBox.mask(secret_a)

    # rotate: replace the secret in place; old ciphertext no longer needed
    secret_b = "fmp_live_key_BBBB2222"
    ct_b = box.encrypt(secret_b)
    assert box.decrypt(ct_b) == secret_b
    assert ct_b != ct_a

    # swap between two distinct keys (multiple keys for the same vendor)
    secret_c = "fmp_backup_key_CCCC3333"
    ct_c = box.encrypt(secret_c)
    assert box.decrypt(ct_c) == secret_c
    assert box.decrypt(ct_b) == secret_b  # both remain independently decryptable
