#!/usr/bin/env python3
"""「オッズの変化」を足すと、勝ち馬の予想が良くなるかを確かめる（ab_test.py から呼ばれる）。

要素 = log(締切時の市場の勝率) − log(発走の60分以上前の市場の勝率)
 ＝ 発走前に人気が上がった馬はプラス、下がった馬はマイナス。
基準は「締切時の市場のオッズだけ」。保存した朝・昼・夕のオッズ（odds_snapshots.jsonl）がある
レースだけで、時間順に分けて「前の期間で学習→次の期間で採点」する。
データが少ないうちは「データ不足」と表示するだけ。
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ab_test as AB  # noqa: E402

SNAP = os.path.join(HERE, "data", "odds_snapshots.jsonl")
MIN_RACES = 300
MIN_DAYS = 6


def minutes(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def load_snapshots():
    """{(日付, 競馬場コード, R): 発走60分以上前で一番早いスナップショットの {馬番: オッズ}}"""
    best = {}
    if not os.path.exists(SNAP):
        return best
    for line in open(SNAP, encoding="utf-8"):
        s = json.loads(line)
        if not s["start"] or any(v is None for v in s["odds"].values()):
            continue
        if minutes(s["start"]) - minutes(s["t"][11:16]) < 60:
            continue
        key = (s["d"], s["code"], s["r"])
        if key not in best or s["t"] < best[key][0]:
            best[key] = (s["t"], {int(k): v for k, v in s["odds"].items()})
    return best


def section(races):
    snaps = load_snapshots()
    sub = []
    for r in races:
        key = (r["d"], r["code"], r["r"])
        if key in snaps and set(snaps[key][1]) == {h["no"] for h in r["hs"]}:
            r = dict(r)
            r["snap"] = snaps[key][1]
            sub.append(r)
    days = sorted({r["d"] for r in sub})
    out = ["\n## オッズの変化（発走60分以上前 → 締切時）",
           f"- 保存したオッズが使えるレース：{len(sub)}レース／{len(days)}日分（試すには {MIN_RACES}レース・{MIN_DAYS}日分以上が必要）"]
    if len(sub) < MIN_RACES or len(days) < MIN_DAYS:
        out.append("- **データ不足**：朝・昼・夕のオッズ保存がたまるまで、判定しません。")
        return out
    X = np.zeros((len(sub), AB.NMAX, 2))
    mask = np.zeros((len(sub), AB.NMAX), bool)
    y = np.zeros(len(sub), int)
    for i, r in enumerate(sub):
        pf = np.array([1.0 / h["odds"] for h in r["hs"]])
        pf /= pf.sum()
        ps = np.array([1.0 / r["snap"][h["no"]] for h in r["hs"]])
        ps /= ps.sum()
        n = len(r["hs"])
        X[i, :n, 0] = np.log(pf)
        X[i, :n, 1] = np.log(pf) - np.log(ps)
        mask[i, :n] = True
        y[i] = [h["no"] for h in r["hs"]].index(r["win"])
    day_of = np.array([r["d"] for r in sub])
    edges = [days[int(len(days) * k / 5)] for k in range(5)] + ["99999999"]
    d_all, fold_all = [], []
    for k in range(1, 5):
        tr = (day_of < edges[k])
        te = (day_of >= edges[k]) & (day_of < edges[k + 1])
        if tr.sum() < 50 or te.sum() == 0:
            continue
        losses = []
        for cols in ([0], [0, 1]):
            Xtr, Xte = X[tr][:, :, cols], X[te][:, :, cols]
            mu, sd = AB.stats(Xtr, mask[tr])
            beta = AB.fit(Xtr, mask[tr], y[tr], mu, sd)
            p = AB.predict(Xte, mask[te], beta, mu, sd)
            losses.append(AB.per_race_loss(p, y[te]))
        d_all.append(losses[0] - losses[1])
        fold_all.append(np.full(te.sum(), k))
    d = np.concatenate(d_all)
    f = np.concatenate(fold_all)
    se = d.std(ddof=1) / math.sqrt(len(d))
    t = d.mean() / se if se > 0 else 0.0
    good = sum(1 for k in sorted(set(f)) if d[f == k].mean() > 0)
    ok = t >= 2.5 and good >= max(3, len(set(f)) - 1)
    out.append(f"- 良くなった幅 {d.mean():+.4f}（±{se:.4f}、{t:+.1f}倍）／良くなった分割 {good}/{len(set(f))} → "
               f"{'**追加する**' if ok else '追加しない'}")
    return out
