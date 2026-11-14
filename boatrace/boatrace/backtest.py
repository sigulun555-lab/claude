"""Phase 7: 時系列で学習期間とテスト期間に分けて、モデルの実力を測る。

注意: 過去オッズはまだ取り込んでいないため、「期待値が1を超える買い目だけ買う」
本来の戦略はまだ検証できない。ここでは、確率の精度と、確率上位を機械的に
買ったときの的中率・回収率を出す。
"""
import numpy as np
import pandas as pd

from .model import harville, predict_win_prob, train


def split_by_date(df, test_ratio=0.25):
    dates = np.sort(df["date"].unique())
    cut = dates[int(len(dates) * (1 - test_ratio))]
    return df[df["date"] < cut], df[df["date"] >= cut], cut


def _logloss(p, y):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


def run(con, df, test_ratio=0.25):
    train_df, test_df, cut = split_by_date(df, test_ratio)
    model = train(train_df)
    test_df = test_df[test_df["rank"].notna()].copy()
    # 6艇全員が完走していなくても、着順がついた艇のレースは評価対象にする
    test_df["p_win"] = predict_win_prob(model, test_df)
    y = (test_df["rank"] == 1).astype(int)

    # 比較用: 学習期間の枠番別1着率だけを使った確率
    prior = train_df[train_df["rank"].notna()].groupby("boat")["rank"].apply(lambda r: (r == 1).mean())
    p_prior = test_df["boat"].map(prior)
    p_prior = p_prior / p_prior.groupby(test_df["race_id"]).transform("sum")

    pay = pd.read_sql_query("SELECT race_id, bet_type, combo, amount FROM payouts", con)
    pay = pay[pay["race_id"].isin(test_df["race_id"])]
    paymap = {(r, t, c): a for r, t, c, a in pay.itertuples(index=False)}
    settled = set(pay["race_id"])

    bets = {k: [0, 0, 0] for k in ["単勝 1点", "2連単 1点", "3連単 1点", "3連単 上位5点", "3連複 1点"]}
    calib = []
    for race_id, g in test_df.groupby("race_id"):
        if race_id not in settled or len(g) < 6:
            continue
        probs = harville(dict(zip(g["boat"], g["p_win"])))
        for name, (bet_type, n) in {
            "単勝 1点": ("単勝", 1), "2連単 1点": ("2連単", 1), "3連単 1点": ("3連単", 1),
            "3連単 上位5点": ("3連単", 5), "3連複 1点": ("3連複", 1),
        }.items():
            picks = sorted(probs[bet_type], key=probs[bet_type].get, reverse=True)[:n]
            ret = sum(paymap.get((race_id, bet_type, c), 0) for c in picks)
            bets[name][0] += 100 * n
            bets[name][1] += ret
            bets[name][2] += ret > 0
        top = max(probs["単勝"], key=probs["単勝"].get)
        calib.append((probs["単勝"][top], int(g.loc[g["boat"] == int(top), "rank"].iloc[0] == 1)))

    ev = ev_backtest(con, test_df, paymap)
    n_races = len(calib)
    cal = pd.DataFrame(calib, columns=["p", "hit"])
    cal["bin"] = pd.cut(cal["p"], [0, .3, .4, .5, .6, .7, .8, 1])
    return {
        "train_until": cut,
        "n_train_races": train_df["race_id"].nunique(),
        "n_test_races": n_races,
        "logloss_model": _logloss(test_df["p_win"].values, y.values),
        "logloss_prior": _logloss(p_prior.values, y.values),
        "bets": {k: (h / n_races if n_races else 0, r / s if s else 0) for k, (s, r, h) in bets.items()},
        "calibration": cal.groupby("bin", observed=True).agg(n=("hit", "size"), pred=("p", "mean"), actual=("hit", "mean")),
        "importance": pd.Series(model.feature_importance("gain"), index=model.feature_name()).sort_values(ascending=False),
        "ev": ev,
        "model": model,
    }


EV_THRESHOLDS = [1.0, 1.1, 1.2, 1.3, 1.5, 2.0]


def ev_backtest(con, test_df, paymap, bet_types=("単勝", "3連単")):
    """締切時オッズがあるレースで「期待値 = 確率 × オッズ」が閾値以上の買い目だけ買う。

    戻り値: {券種: [(閾値, レース数, 点数, 的中率, 回収率), ...]}
    """
    odds = pd.read_sql_query("SELECT race_id, bet_type, combo, odds FROM odds", con)
    odds = odds[odds["race_id"].isin(set(test_df["race_id"])) & odds["odds"].notna()]
    if odds.empty:
        return {}
    by_race = {k: dict(zip(g["combo"], g["odds"])) for k, g in odds.groupby(["race_id", "bet_type"])}
    races = {rid for rid, _ in by_race}
    out = {}
    for bet_type in bet_types:
        stats = {th: [0, 0, 0, set()] for th in EV_THRESHOLDS}  # 点数, 払戻, 的中数, レース
        for race_id, g in test_df[test_df["race_id"].isin(races)].groupby("race_id"):
            o = by_race.get((race_id, bet_type))
            if not o or len(g) < 6:
                continue
            probs = harville(dict(zip(g["boat"], g["p_win"])))[bet_type]
            for combo, p in probs.items():
                if combo not in o:
                    continue
                ev = p * o[combo]
                ret = paymap.get((race_id, bet_type, combo), 0)
                for th in EV_THRESHOLDS:
                    if ev >= th:
                        st = stats[th]
                        st[0] += 1
                        st[1] += ret
                        st[2] += ret > 0
                        st[3].add(race_id)
        out[bet_type] = [
            (th, len(r), n, h / n if n else 0, pay / (100 * n) if n else 0)
            for th, (n, pay, h, r) in stats.items()
        ]
    return {k: v for k, v in out.items() if any(row[2] for row in v)}
