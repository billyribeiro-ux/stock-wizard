"""RL trade-policy lab (tabular Q-learning research lab)."""

from __future__ import annotations

from engine.ml import RLConfig, train_policy
from tests.conftest import make_ohlcv


def test_rl_policy_trains_and_reports():
    report = train_policy(make_ohlcv(n=500, drift=0.05, amp=2.0), RLConfig(episodes=10, seed=7))
    assert report is not None
    assert report.n_states_visited > 0
    assert isinstance(report.beats_buy_hold, bool)
    mix_sum = sum(report.action_mix.values())
    assert abs(mix_sum - 1.0) < 0.01
    assert "research lab" in report.note.lower() or "research" in report.note.lower()


def test_rl_deterministic_with_seed():
    a = train_policy(make_ohlcv(n=400, amp=2.0), RLConfig(episodes=8, seed=11))
    b = train_policy(make_ohlcv(n=400, amp=2.0), RLConfig(episodes=8, seed=11))
    assert a is not None and b is not None
    assert a.valid_return == b.valid_return


def test_rl_insufficient_history():
    assert train_policy(make_ohlcv(n=60)) is None
