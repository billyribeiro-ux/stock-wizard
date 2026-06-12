"""Evidence aggregation, Bayesian scoring, and conflict resolution."""

from .bayesian import confidence_band, posterior_probability
from .ensemble import Consensus, combine, edge_weight_from_calibrator

__all__ = [
    "Consensus",
    "combine",
    "edge_weight_from_calibrator",
    "posterior_probability",
    "confidence_band",
]
