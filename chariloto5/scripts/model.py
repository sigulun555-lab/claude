"""チャリロト5 予想モデル(条件付きロジット)の学習と検証。

各選手の特徴量 x から得点 s = w・x を作り、同じレース内で
softmax をとった値を「その選手が1着になる確率」とみなす。
重み w は過去レースの尤度最大化(L2正則化つき)で求める。

使い方: python model.py            -> data/model.json と data/backtest.json を出力
"""
import itertools
import json
import math
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")

GRADES = {"SS": 0, "S1": 1, "S2": 2, "A1": 3, "A2": 4, "A3": 5, "L1": 6}
POSITIONS = ["先頭", "番手", "3番手以降", "単騎"]

# 特徴量の名前(アプリ側の JS と同じ順番で使う)
FEATURES = (
    [f"車番{c}" for c in range(2, 10)]          # 1番車を基準にした車番の差
    + ["番手", "3番手以降", "単騎"]             # 先頭(先行)を基準にした位置の差
    + ["級班が最上位より1つ下", "級班が最上位より2つ以上下"]
    + ["3人以上のライン"]
)
L2 = 0.003  # 正則化の強さ(tune_l2 の1日抜き交差検証で選んだ値)


def position_of(car, lines):
    for li in lines:
        if car in li:
            if len(li) == 1:
                return "単騎", 1
            i = li.index(car)
            return ["先頭", "番手"][i] if i < 2 else "3番手以降", len(li)
    return "単騎", 1  # 周回予想にない選手は単騎扱い


def featurize(riders, lines):
    """riders: [{car, grade}] -> 行列 (人数 x 特徴量数)"""
    best = min(GRADES.get(r["grade"], 9) for r in riders)
    rows = []
    for r in riders:
        x = [0.0] * len(FEATURES)
        if r["car"] >= 2:
            x[FEATURES.index(f"車番{r['car']}")] = 1
        pos, size = position_of(r["car"], lines)
        if pos != "先頭":
            x[FEATURES.index(pos)] = 1
        gap = GRADES.get(r["grade"], 9) - best
        if gap == 1:
            x[FEATURES.index("級班が最上位より1つ下")] = 1
        elif gap >= 2:
            x[FEATURES.index("級班が最上位より2つ以上下")] = 1
        if size >= 3:
            x[FEATURES.index("3人以上のライン")] = 1
        rows.append(x)
    return np.array(rows)


def race_examples(days):
    out = []
    for day in days:
        for r in day["c5_races"]:
            X = featurize(r["riders"], r["lines"])
            y = np.array([1.0 if x["car"] in r["winners"] else 0.0 for x in r["riders"]])
            out.append((X, y / y.sum()))  # 同着は1着を等分
    return out


def softmax(s):
    e = np.exp(s - s.max())
    return e / e.sum()


def stack(examples):
    """レースごとの行列を (レース数 x 9人 x 特徴量) にまとめる。空き枠は mask=0。"""
    n, k = len(examples), max(len(X) for X, _ in examples)
    Xs = np.zeros((n, k, len(FEATURES)))
    Ys = np.zeros((n, k))
    M = np.zeros((n, k))
    for i, (X, y) in enumerate(examples):
        Xs[i, :len(X)], Ys[i, :len(X)], M[i, :len(X)] = X, y, 1
    return Xs, Ys, M


def fit(examples, l2=L2, iters=60):
    """平均対数尤度 - l2/2*|w|^2 をニュートン法で最大化する。"""
    Xs, Ys, M = stack(examples)
    n, d = len(examples), len(FEATURES)
    w = np.zeros(d)
    for _ in range(iters):
        s = np.where(M > 0, Xs @ w, -np.inf)
        P = np.exp(s - s.max(1, keepdims=True))
        P /= P.sum(1, keepdims=True)
        mean = np.einsum("nk,nkd->nd", P, Xs)
        g = np.einsum("nk,nkd->d", Ys, Xs) / n - mean.sum(0) / n - l2 * w
        Xc = Xs - mean[:, None, :]
        H = -np.einsum("nk,nkd,nke->de", P, Xc, Xc) / n - l2 * np.eye(d)
        step = np.linalg.solve(H, g)
        w -= step
        if np.abs(step).max() < 1e-8:
            break
    return w


def predict(w, X):
    return softmax(X @ w)


def best_ticket_plan(probs, budget):
    """各レースで上位 k_i 車を選ぶ。点数 = Π k_i <= budget の中で
    的中確率 Π(上位 k_i 車の確率の和) が最大になる k を全探索する。"""
    order = [np.argsort(-p) for p in probs]
    cum = [np.concatenate([[0], np.cumsum(p[o])]) for p, o in zip(probs, order)]
    best = None
    for ks in itertools.product(*[range(1, len(p) + 1) for p in probs]):
        cost = math.prod(ks)
        if cost > budget:
            continue
        hit = math.prod(c[k] for c, k in zip(cum, ks))
        if best is None or hit > best[0] + 1e-12 or (abs(hit - best[0]) < 1e-12 and cost < best[1]):
            best = (hit, cost, ks)
    hit, cost, ks = best
    picks = [[int(o[i]) for i in range(k)] for o, k in zip(order, ks)]
    return {"hit_prob": hit, "tickets": cost, "picks": picks}


def tune_l2(days, grid=(0.001, 0.003, 0.01, 0.02, 0.05, 0.1, 0.3)):
    """1日抜き交差検証の対数尤度で正則化の強さを選ぶ。"""
    res = {}
    for l2 in grid:
        ll = 0.0
        for i, day in enumerate(days):
            w = fit(race_examples(days[:i] + days[i + 1:]), l2=l2)
            for X, y in race_examples([day]):
                ll += math.log(float(predict(w, X) @ y))
        res[l2] = ll
    return res


def main():
    days = json.load(open(os.path.join(DATA, "races.json")))
    # --- 1日抜き交差検証(その日を学習に使わずに予想する) ---
    budgets = [1, 4, 16, 32, 64, 128, 243, 500, 1000, 3000]
    per_day = []
    race_hits_top1 = races = 0
    ll_model = ll_uniform = 0.0
    for i, day in enumerate(days):
        train = race_examples(days[:i] + days[i + 1:])
        w = fit(train)
        probs, winners_idx = [], []
        for r in day["c5_races"]:
            X = featurize(r["riders"], r["lines"])
            p = predict(w, X)
            probs.append(p)
            win = [j for j, x in enumerate(r["riders"]) if x["car"] in r["winners"]]
            winners_idx.append(win)
            races += 1
            race_hits_top1 += int(int(np.argmax(p)) in win)
            ll_model += math.log(sum(p[j] for j in win))
            ll_uniform += math.log(len(win) / len(p))
        c5 = day["chariloto5"] or {}
        rows = []
        for b in budgets:
            plan = best_ticket_plan(probs, b)
            hit = all(any(j in pk for j in win) for pk, win in zip(plan["picks"], winners_idx))
            cost = plan["tickets"] * 100
            # 当たっていた場合の払戻の見込み: (キャリーオーバー + 売上*75%) / (他の的中口数 + 自分の1口)
            pay = 0
            if hit and c5.get("sales") is not None:
                pool = (c5.get("carryover_in") or 0) + (c5["sales"] + cost) * 0.75
                pay = min(pool / ((c5.get("hit_units") or 0) + 1), 6e8)
            rows.append({"budget": b, "tickets": plan["tickets"], "pred_hit_prob": round(plan["hit_prob"], 4),
                         "hit": hit, "cost": cost, "payout_est": int(pay)})
        per_day.append({"date": day["date"], "velodrome": day["velodrome"], "plans": rows})

    summary = []
    for bi, b in enumerate(budgets):
        rs = [d["plans"][bi] for d in per_day]
        summary.append({
            "budget": b,
            "avg_tickets": round(sum(r["tickets"] for r in rs) / len(rs), 1),
            "pred_hit_rate": round(sum(r["pred_hit_prob"] for r in rs) / len(rs), 4),
            "actual_hits": sum(r["hit"] for r in rs),
            "days": len(rs),
            "total_cost": sum(r["cost"] for r in rs),
            "total_payout_est": sum(r["payout_est"] for r in rs),
        })
    # 何も考えずに選んだ場合(全車同じ確率)の5レース全的中確率
    uniform_1 = sum(math.prod(1 / r["field_size"] for r in d["c5_races"]) for d in days) / len(days)
    backtest = {
        "method": "1日抜き交差検証(予想する日のデータは学習に使っていない)",
        "days": len(days), "races": races,
        "race_top1_accuracy": round(race_hits_top1 / races, 4),
        "avg_race_winner_prob_model": round(math.exp(ll_model / races), 4),
        "avg_race_winner_prob_uniform": round(math.exp(ll_uniform / races), 4),
        "uniform_1ticket_hit_prob": uniform_1,
        "by_budget": summary,
        "per_day": per_day,
    }
    json.dump(backtest, open(os.path.join(DATA, "backtest.json"), "w"), ensure_ascii=False, indent=1)

    # --- 全データで最終モデルを学習 ---
    w = fit(race_examples(days))
    model = {
        "type": "conditional_logit",
        "features": FEATURES,
        "weights": [round(float(v), 4) for v in w],
        "l2": L2,
        "trained_on": {"days": len(days), "races": races,
                       "from": days[0]["date"], "to": days[-1]["date"]},
    }
    json.dump(model, open(os.path.join(DATA, "model.json"), "w"), ensure_ascii=False, indent=1)

    print(json.dumps({k: v for k, v in backtest.items() if k != "per_day"}, ensure_ascii=False, indent=1))
    for f, v in zip(FEATURES, w):
        print(f"{f:>16} {v:+.3f}  (x{math.exp(v):.2f})")


if __name__ == "__main__":
    main()
