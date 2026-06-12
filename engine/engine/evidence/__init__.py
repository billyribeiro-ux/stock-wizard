"""Evidence aggregation, Bayesian scoring, and conflict resolution."""

from .bayesian import confidence_band, posterior_probability
from .ensemble import Consensus, combine

__all__ = ["Consensus", "combine", "posterior_probability", "confidence_band"]
