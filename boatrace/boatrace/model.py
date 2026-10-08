"""Phase 4-6: 1着確率のモデル、券種ごとの確率、期待値。"""
from itertools import combinations, permutations

import lightgbm as lgb
import numpy as np
import pandas as pd

from .features import CATEGORICAL, FEATURES

PARAMS = {
    "objective": "binary",
    "learning_rate": 0.03,
    "num_leaves": 31,
    "min_data_in_leaf": 100,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "lambda_l2": 1.0,
    "verbose": -1,
}


def train(df: pd.DataFrame, num_rounds: int = 600) -> lgb.Booster:
    df = df[df["rank"].notna()]
    data = lgb.Dataset(df[FEATURES], label=(df["rank"] == 1).astype(int),
                       categorical_feature=CATEGORICAL)
    return lgb.train(PARAMS, data, num_boost_round=num_rounds)


def predict_win_prob(model: lgb.Booster, df: pd.DataFrame) -> pd.Series:
    """各艇の1着確率。レース内で合計が1になるように揃える。"""
    raw = pd.Series(model.predict(df[FEATURES]), index=df.index)
    return raw / raw.groupby(df["race_id"]).transform("sum")


# 2着・3着の補正 (Benter 方式)。学習期間の後半で最尤推定した値。
# そのままの Harville (1.0, 1.0) だと本命寄りの組を来ると思いすぎ、大穴を低く見すぎる。
GAMMA, DELTA = 0.672, 0.476


def harville(p: dict, gamma: float = GAMMA, delta: float = DELTA) -> dict:
    """1着確率 {艇: 確率} から全券種の的中確率を出す (Harville の公式 + Benter の補正)。

    P(i-j-k) = p_i * p_j^γ/Σ_{m≠i} p_m^γ * p_k^δ/Σ_{m≠i,j} p_m^δ
    γ = δ = 1 のとき元の Harville の公式になる。
    """
    boats = sorted(p)
    pg = {b: p[b] ** gamma for b in boats}
    pd_ = {b: p[b] ** delta for b in boats}
    sg, sd = sum(pg.values()), sum(pd_.values())
    tri = {}
    for i, j, k in permutations(boats, 3):
        tri[(i, j, k)] = p[i] * pg[j] / (sg - pg[i]) * pd_[k] / (sd - pd_[i] - pd_[j])
    exacta = {(i, j): p[i] * pg[j] / (sg - pg[i]) for i, j in permutations(boats, 2)}

    out = {"単勝": {str(i): p[i] for i in boats}}
    out["2連単"] = {f"{i}-{j}": v for (i, j), v in exacta.items()}
    out["2連複"] = {f"{i}-{j}": exacta[(i, j)] + exacta[(j, i)] for i, j in combinations(boats, 2)}
    out["3連単"] = {f"{i}-{j}-{k}": v for (i, j, k), v in tri.items()}
    out["3連複"] = {
        f"{i}-{j}-{k}": sum(tri[t] for t in permutations((i, j, k)))
        for i, j, k in combinations(boats, 3)
    }
    top2 = {b: sum(v for (i, j), v in exacta.items() if b in (i, j)) for b in boats}
    top3 = {b: sum(v for t, v in tri.items() if b in t) for b in boats}
    out["複勝"] = {str(b): top2[b] for b in boats}  # 6艇立ては2着まで
    out["拡連複"] = {
        f"{i}-{j}": sum(v for t, v in tri.items() if i in t and j in t)
        for i, j in combinations(boats, 2)
    }
    out["_top3"] = top3
    return out


def expected_value(prob: float, odds: float) -> float:
    """期待値 = 的中確率 × オッズ。1.0 を超えると理論上プラス。"""
    return prob * odds


def kelly_fraction(prob: float, odds: float, scale: float = 0.25) -> float:
    """資金のうち何割を賭けるか (ケリー基準の scale 倍、マイナスなら0)。"""
    b = odds - 1
    if b <= 0:
        return 0.0
    return max(0.0, (prob * b - (1 - prob)) / b) * scale
