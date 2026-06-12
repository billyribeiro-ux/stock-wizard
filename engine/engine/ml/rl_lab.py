"""Reinforcement-learning trade policy lab (research, NOT production).

A compact tabular Q-learning lab: the state is a coarse discretization of the feature
vector (trend bucket x RSI bucket x volatility bucket), actions are {long, flat,
short}, and the reward is the next-bar return of the held position minus a switching
cost. The policy is trained on the earlier slice of history and evaluated on the later
slice (walk-forward), reported against buy-and-hold. Per the blueprint this is a
research lab: a policy is *never* promoted from here — it must still pass the standard
forward-testing gate.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

import numpy as np

from ..features.base import ohlcv_to_frame
from ..schemas import OHLCV
from .dataset import compute_feature_frame

ACTIONS = (-1, 0, 1)  # short, flat, long


@dataclass
class RLConfig:
    episodes: int = 30
    alpha: float = 0.2  # learning rate
    gamma: float = 0.9  # discount
    epsilon: float = 0.15  # exploration
    switch_cost: float = 0.0002  # cost of changing position (2 bps)
    train_frac: float = 0.6
    seed: int = 42


@dataclass
class RLReport:
    n_states_visited: int
    train_return: float
    valid_return: float
    buy_hold_valid_return: float
    beats_buy_hold: bool
    action_mix: dict[str, float] = field(default_factory=dict)
    note: str = (
        "Research lab output — never trade an RL policy without the standard "
        "walk-forward + forward-test promotion gate."
    )


def _bucket(x: float, edges: tuple[float, ...]) -> int:
    for i, e in enumerate(edges):
        if x < e:
            return i
    return len(edges)


def _states(feats) -> np.ndarray:
    """Discretize each bar into a small integer state id."""
    trend = feats["dist_sma20_atr"].to_numpy(dtype=float)
    rsi = feats["rsi14"].to_numpy(dtype=float)
    vol = feats["atr_norm"].to_numpy(dtype=float)
    med_vol = np.nanmedian(vol)
    out = np.zeros(len(feats), dtype=int)
    for i in range(len(feats)):
        t = _bucket(trend[i], (-1.0, 0.0, 1.0))  # 4 trend buckets
        r = _bucket(rsi[i], (30.0, 50.0, 70.0))  # 4 rsi buckets
        v = _bucket(vol[i], (med_vol,))  # 2 vol buckets
        out[i] = (t * 4 + r) * 2 + v
    return out


def _run_policy(q: dict, states: np.ndarray, rets: np.ndarray, cfg: RLConfig) -> tuple[float, dict]:
    """Greedy evaluation: follow argmax-Q, accumulate compounded return."""
    pos = 0
    equity = 1.0
    counts = dict.fromkeys(ACTIONS, 0)
    for i in range(len(states) - 1):
        qs = q.get(states[i])
        action = ACTIONS[int(np.argmax(qs))] if qs is not None else 0
        cost = cfg.switch_cost if action != pos else 0.0
        equity *= 1.0 + action * rets[i + 1] - cost
        pos = action
        counts[action] += 1
    total = max(sum(counts.values()), 1)
    mix = {"short": counts[-1] / total, "flat": counts[0] / total, "long": counts[1] / total}
    return equity - 1.0, mix


def train_policy(ohlcv: OHLCV, config: RLConfig | None = None) -> RLReport | None:
    cfg = config or RLConfig()
    df = ohlcv_to_frame(ohlcv)
    if len(df) < 150:
        return None
    feats = compute_feature_frame(df)
    rets = df["close"].pct_change().fillna(0.0).to_numpy(dtype=float)
    mask = feats.notna().all(axis=1).to_numpy()
    first = int(np.argmax(mask)) if mask.any() else len(df)
    if len(df) - first < 120:
        return None
    states = _states(feats.iloc[first:])
    rets = rets[first:]

    split = int(len(states) * cfg.train_frac)
    s_tr, r_tr = states[:split], rets[:split]
    s_va, r_va = states[split:], rets[split:]

    rng = random.Random(cfg.seed)
    q: dict[int, np.ndarray] = {}

    def ensure(s: int) -> np.ndarray:
        if s not in q:
            q[s] = np.zeros(len(ACTIONS))
        return q[s]

    for _ in range(cfg.episodes):
        pos = 0
        for i in range(len(s_tr) - 1):
            qs = ensure(s_tr[i])
            if rng.random() < cfg.epsilon:
                a_idx = rng.randrange(len(ACTIONS))
            else:
                a_idx = int(np.argmax(qs))
            action = ACTIONS[a_idx]
            cost = cfg.switch_cost if action != pos else 0.0
            reward = action * r_tr[i + 1] - cost
            next_qs = ensure(s_tr[i + 1])
            qs[a_idx] += cfg.alpha * (reward + cfg.gamma * float(np.max(next_qs)) - qs[a_idx])
            pos = action

    train_ret, _ = _run_policy(q, s_tr, r_tr, cfg)
    valid_ret, mix = _run_policy(q, s_va, r_va, cfg)
    bh = float(np.prod(1.0 + r_va[1:]) - 1.0)

    return RLReport(
        n_states_visited=len(q),
        train_return=round(float(train_ret), 5),
        valid_return=round(float(valid_ret), 5),
        buy_hold_valid_return=round(float(bh), 5),
        beats_buy_hold=bool(valid_ret > bh),
        action_mix={k: round(float(v), 3) for k, v in mix.items()},
    )
