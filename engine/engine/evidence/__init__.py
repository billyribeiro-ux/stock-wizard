"""Evidence aggregation, Bayesian scoring, and conflict resolution."""

from .bayesian import confidence_band, posterior_probability
from .ensemble import (
    Consensus,
    combine,
    edge_weight_from_calibrator,
    edge_weight_from_walkforward,
)

__all__ = [
    "Consensus",
    "combine",
    "edge_weight_from_calibrator",
    "edge_weight_from_walkforward",
    "posterior_probability",
    "confidence_band",
]
