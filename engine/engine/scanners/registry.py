"""Scanner registry — maps scanner_id to class, powering /scanners and dispatch."""

from __future__ import annotations

from ..schemas import ScannerSpec
from .base import Scanner
from .insider_congress import InsiderCongressScanner
from .mtf_structure import MtfStructureScanner
from .spx_gamma_command import SpxGammaCommandScanner
from .volume_profile_poc import VolumeProfilePocScanner

_SCANNERS: dict[str, type[Scanner]] = {
    cls.scanner_id: cls
    for cls in (
        MtfStructureScanner,
        VolumeProfilePocScanner,
        SpxGammaCommandScanner,
        InsiderCongressScanner,
    )
}


def list_scanner_ids() -> list[str]:
    return list(_SCANNERS)


def list_specs() -> list[ScannerSpec]:
    return [cls.spec() for cls in _SCANNERS.values()]


def get_scanner_class(scanner_id: str) -> type[Scanner]:
    if scanner_id not in _SCANNERS:
        raise KeyError(f"unknown scanner_id: {scanner_id}")
    return _SCANNERS[scanner_id]


def build_scanner(scanner_id: str, params: dict | None = None) -> Scanner:
    return get_scanner_class(scanner_id)(params)
