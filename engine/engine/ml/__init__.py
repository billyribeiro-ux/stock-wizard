"""Machine-learning / self-learning: datasets, models, anomaly, regime."""

from .anomaly import AnomalyResult, detect_last_bar
from .dataset import Dataset, build_dataset, compute_feature_frame
from .models import ModelReport, train_setup_model
from .regime import RegimeResult, classify_regime

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
]
