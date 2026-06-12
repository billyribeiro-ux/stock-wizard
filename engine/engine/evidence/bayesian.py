"""Bayesian evidence scoring — combine weighted evidence into a posterior probability.

Works in log-odds space (a naive-Bayes / logistic aggregation): start from a prior,
then each piece of supporting evidence adds to the log-odds and each opposing piece
subtracts, scaled by its weight. The result is a disciplined, monotonic way to turn an
EvidencePacket's for/against stack into a single calibrated probability the system can
change intraday as new evidence arrives.
"""

from __future__ import annotations

import math

from ..schemas import EvidencePacket


def _logit(p: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def posterior_probability(packet: EvidencePacket, prior: float = 0.5, scale: float = 1.5) -> float:
    """Posterior P(thesis | evidence). ``scale`` maps a unit weight to log-odds shift."""
    log_odds = _logit(prior)
    for item in packet.evidence_for:
        log_odds += scale * item.weight
    for item in packet.evidence_against:
        log_odds -= scale * item.weight
    return _sigmoid(log_odds)


def confidence_band(
    packet: EvidencePacket, prior: float = 0.5, scale: float = 1.5, spread: float = 0.1
) -> tuple[float, float]:
    """A simple credible band around the posterior, widened by evidence conflict.

    More opposing evidence => wider band (less certainty).
    """
    p = posterior_probability(packet, prior, scale)
    against = sum(i.weight for i in packet.evidence_against)
    width = spread * (1.0 + against)
    return (max(0.0, p - width), min(1.0, p + width))
