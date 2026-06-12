"""Machine-learning / self-learning: datasets, models, anomaly, regime."""

from .absorption import AbsorptionResult, compute_absorption
from .anomaly import AnomalyResult, detect_last_bar
from .calibration import ScoreCalibrator, fit_calibrator, wilson_interval
from .calibration_builder import build_scanner_calibrator
from .cross_validation import purged_walk_forward_splits
from .dataset import Dataset, build_dataset, compute_feature_frame
from .discovery import DiscoveryReport, SuggestedRule, TurnEvent, discover
from .genetic import MinedRule, MinerConfig, mine_rules
from .info_theory import InfoReport, binary_entropy, mutual_information_ranking
from .models import ModelReport, train_setup_model
from .regime import RegimeResult, classify_regime
from .rl_lab import RLConfig, RLReport, train_policy

__all__ = [
    "build_dataset",
    "compute_feature_frame",
    "Dataset",
    "train_setup_model",
    "ModelReport",
    "detect_last_bar",
    "AnomalyResult",
    "classify_regime",
    "RegimeResult",
    "mine_rules",
    "MinedRule",
    "MinerConfig",
    "discover",
    "DiscoveryReport",
    "SuggestedRule",
    "TurnEvent",
    "ScoreCalibrator",
    "fit_calibrator",
    "wilson_interval",
    "build_scanner_calibrator",
    "compute_absorption",
    "AbsorptionResult",
    "mutual_information_ranking",
    "InfoReport",
    "binary_entropy",
    "purged_walk_forward_splits",
    "train_policy",
    "RLConfig",
    "RLReport",
]
