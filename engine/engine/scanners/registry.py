"""Scanner registry — maps scanner_id to class, powering /scanners and dispatch."""

from __future__ import annotations

from ..schemas import ScannerSpec
from .base import Scanner
from .cross_asset import (
    CrossAssetRiskScanner,
    IndexDivergenceScanner,
    VixTailRiskScanner,
)
from .insider_congress import InsiderCongressScanner
from .levels_scanners import (
    AnchoredVwapScanner,
    GapScanner,
    KeyLevelScanner,
    OpeningRangeScanner,
)
from .ml_scanners import AnomalyDetectionScanner, RegimeClassificationScanner
from .mtf_structure import MtfStructureScanner
from .options_gamma import (
    BrokenWingButterflyScanner,
    CharmVannaScanner,
    DealerHedgeFlowScanner,
    ExpectedMoveScanner,
    GammaExposureScanner,
    GammaSqueezeScanner,
    GammaWallScanner,
    MaxPainScanner,
    OptionsFlowScanner,
    PinMagnetScanner,
    SkewScanner,
)
from .price_action import (
    BiggerMoveScanner,
    BreakoutQualityScanner,
    FailedMoveScanner,
    LiquiditySweepScanner,
    LongTrapScanner,
    MomentumIgnitionScanner,
    ShortTrapScanner,
    SqueezeCompressionScanner,
    TrendExhaustionScanner,
)
from .regime import SeasonalityScanner, VolatilityRegimeScanner
from .reversal_pullback import PullbackReasonClassifierScanner, ReversalMasterScanner
from .spx_gamma_command import SpxGammaCommandScanner
from .volume_profile_poc import VolumeProfilePocScanner
from .volume_scanners import (
    AccumulationDistributionScanner,
    LowVolumePullbackScanner,
    RvolExpansionScanner,
    VolumeDivergenceScanner,
    VolumeDryUpReversalScanner,
)

_SCANNER_CLASSES: list[type[Scanner]] = [
    # structure / price action
    MtfStructureScanner,
    KeyLevelScanner,
    AnchoredVwapScanner,
    OpeningRangeScanner,
    GapScanner,
    LiquiditySweepScanner,
    ShortTrapScanner,
    LongTrapScanner,
    BreakoutQualityScanner,
    TrendExhaustionScanner,
    MomentumIgnitionScanner,
    FailedMoveScanner,
    BiggerMoveScanner,
    ReversalMasterScanner,
    PullbackReasonClassifierScanner,
    # volume / auction
    VolumeProfilePocScanner,
    SqueezeCompressionScanner,
    AccumulationDistributionScanner,
    VolumeDivergenceScanner,
    LowVolumePullbackScanner,
    VolumeDryUpReversalScanner,
    RvolExpansionScanner,
    # options / gamma
    SpxGammaCommandScanner,
    GammaExposureScanner,
    GammaWallScanner,
    GammaSqueezeScanner,
    ExpectedMoveScanner,
    PinMagnetScanner,
    MaxPainScanner,
    SkewScanner,
    CharmVannaScanner,
    OptionsFlowScanner,
    DealerHedgeFlowScanner,
    BrokenWingButterflyScanner,
    # volatility / cross-asset
    VolatilityRegimeScanner,
    VixTailRiskScanner,
    IndexDivergenceScanner,
    CrossAssetRiskScanner,
    SeasonalityScanner,
    # catalyst / flow
    InsiderCongressScanner,
    # ML / self-learning
    AnomalyDetectionScanner,
    RegimeClassificationScanner,
]

_SCANNERS: dict[str, type[Scanner]] = {cls.scanner_id: cls for cls in _SCANNER_CLASSES}


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
