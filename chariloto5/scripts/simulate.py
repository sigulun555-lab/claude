"""毎日の予想シミュレーション(歩き進み検証)。

その日より前の開催だけで学習し、その日の5レースの1着確率と買い目を作って
実際の結果と突き合わせる。結果は data/sim_log.jsonl に1日1行で追記する。

使い方:
  python simulate.py variants   # 特徴量の案を比べる(採用判断用)
  python simulate.py run        # 現在の採用モデルで全開催を検証し sim_log.jsonl を作る
"""
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model as M  # noqa: E402

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
MIN_TRAIN_DAYS = 8  # 学習に使う開催がこれ以上たまってから予想を始める
GRADES = M.GRADES


def feats(riders, lines, variant):
    """variant: 'base' 現行 / 'grade_lin' 級班を数値で(差が1段ごとに効く) / 'no_line_size' ライン人数を外す"""
    X = M.featurize(riders, lines)
    if variant == "no_line_size":
        X = X[:, :-1]
    if variant == "grade_lin":
        best = min(GRADES.get(r["grade"], 9) for r in riders)
        g = np.array([[GRADES.get(r["grade"], 9) - best] for r in riders], float)
        X = np.hstack([X, g])
    return X


def examples(days, variant):
    out = []
    for day in days:
        for r in day["c5_races"]:
            X = feats(r["riders"], r["lines"], variant)
            y = np.array([1.0 if x["car"] in r["winners"] else 0.0 for x in r["riders"]])
            out.append((X, y / y.sum()))
    return out


def fit_variant(exs, variant, l2):
    # M.fit は特徴数を前提にしているので、特徴数に合わせて一時的に差し替える
    d = exs[0][0].shape[1]
    saved = M.FEATURES
    M.FEATURES = [f"f{i}" for i in range(d)]
    try:
        return M.fit(exs, l2=l2)
    finally:
        M.FEATURES = saved


def walk_forward(days, variant, l2):
    rows = []
    for i in range(MIN_TRAIN_DAYS, len(days)):
        w = fit_variant(examples(days[:i], variant), variant, l2)
        day = days[i]
        probs, wins = [], []
        for r in day["c5_races"]:
            p = M.predict(w, feats(r["riders"], r["lines"], variant))
            probs.append(p)
            wins.append([j for j, x in enumerate(r["riders"]) if x["car"] in r["winners"]])
        rows.append({"date": day["date"], "velodrome": day["velodrome"], "probs": probs, "wins": wins,
                     "day": day})
    return rows


def score(rows):
    ll, top1, n = 0.0, 0, 0
    for row in rows:
        for p, win in zip(row["probs"], row["wins"]):
            ll += math.log(sum(p[j] for j in win))
            top1 += int(int(np.argmax(p)) in win)
            n += 1
    return {"races": n, "mean_loglik": round(ll / n, 4), "geo_mean_winner_prob": round(math.exp(ll / n), 4),
            "top1_acc": round(top1 / n, 4)}


def settle(row, budget):
    """予算(点数の上限)で買い目を決め、的中・費用・払戻の見込みを返す。"""
    plan = M.best_ticket_plan(row["probs"], budget)
    hit = all(any(j in pk for j in win) for pk, win in zip(plan["picks"], row["wins"]))
    cost = plan["tickets"] * 100
    c5 = row["day"].get("chariloto5") or {}
    pay = 0
    if hit and c5.get("sales") is not None:
        pool = (c5.get("carryover_in") or 0) + (c5["sales"] + cost) * 0.75
        pay = min(pool / ((c5.get("hit_units") or 0) + 1), 6e8)
    return {"budget": budget, "tickets": plan["tickets"], "pred_hit_prob": round(plan["hit_prob"], 5),
            "hit": hit, "cost": cost, "payout_est": int(pay)}


def variants(days):
    grid = [0.001, 0.003, 0.01]
    res = []
    for v in ["base", "grade_lin", "no_line_size"]:
        for l2 in grid:
            rows = walk_forward(days, v, l2)
            s = score(rows)
            res.append({"variant": v, "l2": l2, **s})
            print(v, l2, s, flush=True)
    return res


def run(days):
    variant, l2 = "base", M.L2
    rows = walk_forward(days, variant, l2)
    log = []
    for row in rows:
        log.append({"date": row["date"], "velodrome": row["velodrome"], "variant": variant, "l2": l2,
                    "result_winners": [[int(row["day"]["c5_races"][k]["riders"][j]["car"]) for j in win]
                                       for k, win in enumerate(row["wins"])],
                    "by_budget": [settle(row, b) for b in (1, 16, 243, 1000)]})
    path = os.path.join(DATA, "sim_log.jsonl")
    with open(path, "w") as f:
        for item in log:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    summary = {"variant": variant, "l2": l2, "days": len(log), **score(rows)}
    for b_i, b in enumerate((1, 16, 243, 1000)):
        hits = sum(item["by_budget"][b_i]["hit"] for item in log)
        cost = sum(item["by_budget"][b_i]["cost"] for item in log)
        pay = sum(item["by_budget"][b_i]["payout_est"] for item in log)
        summary[f"budget_{b}"] = {"hit_days": hits, "cost": cost, "payout_est": pay,
                                  "recovery": round(pay / cost, 3) if cost else None}
    json.dump(summary, open(os.path.join(DATA, "sim_summary.json"), "w"), ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    days = json.load(open(os.path.join(DATA, "races.json")))
    {"variants": variants, "run": run}[sys.argv[1]](days)
