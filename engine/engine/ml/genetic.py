"""Genetic rule miner — evolve simple, human-readable trading rules.

A rule is a conjunction of feature conditions (e.g. ``rsi14 < 32 AND rvol > 1.4``)
with a direction. Fitness is measured on the TRAIN period only (mean forward return
in the rule's direction, scaled by hit count) with a simplicity penalty; survivors are
then re-scored on a later VALIDATION period — the walk-forward discipline the blueprint
mandates. Rules that don't hold up out-of-sample are flagged, not promoted.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import numpy as np

from ..schemas import OHLCV
from .dataset import FEATURE_NAMES, build_dataset


@dataclass(frozen=True)
class Condition:
    feature: str
    op: str  # "gt" | "lt"
    threshold: float

    def describe(self) -> str:
        return f"{self.feature} {'>' if self.op == 'gt' else '<'} {self.threshold:.3f}"


@dataclass
class Rule:
    conditions: list[Condition]
    direction: int  # +1 long, -1 short

    def describe(self) -> str:
        side = "LONG" if self.direction > 0 else "SHORT"
        return f"{side} when " + " AND ".join(c.describe() for c in self.conditions)


@dataclass
class MinedRule:
    rule: Rule
    description: str
    train_hits: int
    train_mean_return: float
    train_fitness: float
    valid_hits: int
    valid_mean_return: float
    holds_up: bool


@dataclass
class MinerConfig:
    population: int = 60
    generations: int = 25
    max_conditions: int = 3
    min_hits: int = 15
    mutation_rate: float = 0.35
    simplicity_penalty: float = 0.0002
    seed: int = 42
    top_n: int = 10


def _mask(rule: Rule, X: np.ndarray, idx: dict[str, int]) -> np.ndarray:
    m = np.ones(len(X), dtype=bool)
    for c in rule.conditions:
        col = X[:, idx[c.feature]]
        m &= (col > c.threshold) if c.op == "gt" else (col < c.threshold)
    return m


def _fitness(
    rule: Rule, X: np.ndarray, fwd: np.ndarray, idx: dict[str, int], cfg: MinerConfig
) -> tuple[float, int, float]:
    m = _mask(rule, X, idx)
    hits = int(m.sum())
    if hits < cfg.min_hits:
        return -1.0, hits, 0.0
    mean_ret = float(np.mean(fwd[m])) * rule.direction
    # Reward edge and sample size; penalize complexity.
    fit = mean_ret * np.sqrt(hits) - cfg.simplicity_penalty * len(rule.conditions)
    return float(fit), hits, mean_ret


def _random_rule(rng: random.Random, X: np.ndarray, idx: dict[str, int], cfg: MinerConfig) -> Rule:
    n_cond = rng.randint(1, cfg.max_conditions)
    feats = rng.sample(FEATURE_NAMES, n_cond)
    conds = []
    for f in feats:
        col = X[:, idx[f]]
        thr = float(np.quantile(col, rng.uniform(0.1, 0.9)))
        conds.append(Condition(feature=f, op=rng.choice(["gt", "lt"]), threshold=thr))
    return Rule(conditions=conds, direction=rng.choice([1, -1]))


def _mutate(
    rng: random.Random, rule: Rule, X: np.ndarray, idx: dict[str, int], cfg: MinerConfig
) -> Rule:
    conds = list(rule.conditions)
    roll = rng.random()
    if roll < 0.4 and conds:  # perturb a threshold
        i = rng.randrange(len(conds))
        col = X[:, idx[conds[i].feature]]
        jitter = float(np.std(col)) * rng.uniform(-0.3, 0.3)
        conds[i] = Condition(conds[i].feature, conds[i].op, conds[i].threshold + jitter)
    elif roll < 0.6 and len(conds) < cfg.max_conditions:  # add a condition
        extra = _random_rule(rng, X, idx, cfg).conditions[0]
        conds.append(extra)
    elif roll < 0.8 and len(conds) > 1:  # drop a condition (simplify)
        conds.pop(rng.randrange(len(conds)))
    else:  # flip direction
        return Rule(conditions=conds, direction=-rule.direction)
    return Rule(conditions=conds, direction=rule.direction)


def _crossover(rng: random.Random, a: Rule, b: Rule, cfg: MinerConfig) -> Rule:
    pool = list({*a.conditions, *b.conditions})
    rng.shuffle(pool)
    take = pool[: max(1, min(cfg.max_conditions, len(pool)))]
    return Rule(conditions=take, direction=rng.choice([a.direction, b.direction]))


def mine_rules(
    ohlcv: OHLCV,
    horizon: int = 10,
    train_frac: float = 0.6,
    config: MinerConfig | None = None,
) -> list[MinedRule]:
    """Evolve rules on the train slice, validate on the later slice."""
    cfg = config or MinerConfig()
    ds = build_dataset(ohlcv, horizon=horizon)
    if ds is None or len(ds.y) < 120:
        return []
    rng = random.Random(cfg.seed)
    idx = {f: i for i, f in enumerate(FEATURE_NAMES)}

    split = int(len(ds.X) * train_frac)
    X_tr, fwd_tr = ds.X[:split], ds.forward_returns[:split]
    X_va, fwd_va = ds.X[split:], ds.forward_returns[split:]

    population = [_random_rule(rng, X_tr, idx, cfg) for _ in range(cfg.population)]
    for _ in range(cfg.generations):
        scored = sorted(
            ((rule, *_fitness(rule, X_tr, fwd_tr, idx, cfg)) for rule in population),
            key=lambda t: t[1],
            reverse=True,
        )
        elite = [t[0] for t in scored[: max(4, cfg.population // 5)]]
        children: list[Rule] = list(elite)
        while len(children) < cfg.population:
            if rng.random() < cfg.mutation_rate:
                children.append(_mutate(rng, rng.choice(elite), X_tr, idx, cfg))
            else:
                children.append(_crossover(rng, rng.choice(elite), rng.choice(elite), cfg))
        population = children

    # Final scoring: train fitness ranks; validation decides if a rule "holds up".
    out: list[MinedRule] = []
    seen: set[str] = set()
    final = sorted(
        ((rule, *_fitness(rule, X_tr, fwd_tr, idx, cfg)) for rule in population),
        key=lambda t: t[1],
        reverse=True,
    )
    for rule, fit, hits, mean_ret in final:
        desc = rule.describe()
        if fit <= 0 or desc in seen:
            continue
        seen.add(desc)
        v_mask = _mask(rule, X_va, idx)
        v_hits = int(v_mask.sum())
        v_mean = float(np.mean(fwd_va[v_mask])) * rule.direction if v_hits > 0 else 0.0
        out.append(
            MinedRule(
                rule=rule,
                description=desc,
                train_hits=hits,
                train_mean_return=round(mean_ret, 5),
                train_fitness=round(fit, 5),
                valid_hits=v_hits,
                valid_mean_return=round(v_mean, 5),
                holds_up=v_hits >= max(5, cfg.min_hits // 3) and v_mean > 0,
            )
        )
        if len(out) >= cfg.top_n:
            break
    return out
