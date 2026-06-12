"""Machine-learning / self-learning: datasets, models, anomaly, regime."""

from .anomaly import AnomalyResult, detect_last_bar
from .dataset import Dataset, build_dataset, compute_feature_frame
from .discovery import DiscoveryReport, SuggestedRule, TurnEvent, discover
from .genetic import MinedRule, MinerConfig, mine_rules
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
    "train_policy",
    "RLConfig",
    "RLReport",
]
