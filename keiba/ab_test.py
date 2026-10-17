#!/usr/bin/env python3
"""「追加する／追加しない」の比べっこ。

基準は「市場の単勝オッズだけ」。そこに1つずつ要素（全成績・近走・馬体重・斤量・枠・騎手など）を足して、
**時間順に分けた別の期間（まだ見ていないレース）**で勝ち馬の予想が良くなるかを確かめる。
良くなった要素だけを keiba/model.json に採用する。

  python3 keiba/ab_test.py            # 結果を keiba/ab_report.md に書き、model.json を更新
  python3 keiba/ab_test.py --no-write # 画面に出すだけ

方法：条件付きロジット（レースの中で誰が勝つかの確率モデル）。
  基準  : 効用 = b0 × log(市場の勝率)
  追加  : 効用 = b0 × log(市場の勝率) + Σ b_k × 要素_k
評価は時間順の5分割で、前の期間で学習→次の期間で採点（対数損失・小さいほど良い）。
採用条件：全体の差が「誤差の2.5倍以上」良くなり、かつ後ろ4分割のうち3つ以上で良くなること。
（要素を何個も試すので、偶然通るのを避けるため2倍ではなく2.5倍にしている）
"""
import json
import math
import os
import sys
from datetime import date

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DATA = os.path.join(HERE, "data", "history.jsonl")
REPORT = os.path.join(HERE, "ab_report.md")
MODEL = os.path.join(HERE, "model.json")
NMAX = 16
LAMBDA = 1.0

FEATURES = {
    "m2": "市場の勝率の曲がり（人気薄・本命の見すぎ補正）",
    "form_win": "全成績の1着率",
    "form_place": "全成績の連対率",
    "recent3": "近3走の平均着順（頭数比）",
    "last1": "前走の着順（頭数比）",
    "venue_win": "この競馬場の1着率",
    "dist_win": "この距離の1着率",
    "wt_change": "馬体重の増減（%）",
    "wt_change_abs": "馬体重の増減の大きさ（%）",
    "kin_rel": "斤量（そのレースの平均との差）",
    "age": "年齢",
    "sex_f": "牝馬",
    "gate": "馬番（内→外）",
    "rest": "前走からの間隔（日の対数）",
    "jk_rate": "騎手の1着率（学習期間のみで計算）",
    "course_gate": "競馬場×距離ごとの枠（内・中・外）の有利不利（学習期間のみで計算）",
}
BANEI_ONLY = {
    "kin_ratio": "負担重量÷馬体重（そのレースの平均との差）＝ソリの重さの割合",
    "kin_baba": "負担重量の差 × 馬場水分（水分が高い日にソリが軽い馬が有利か）",
}
ALL_FEATURES = {**FEATURES, **BANEI_ONLY}


def features_for(group):
    """ばんえいは、ばんえい専用の要素も試す。"""
    f = dict(FEATURES)
    if group == "ばんえい":
        f.update(BANEI_ONLY)
        for k in ("age", "sex_f", "venue_win", "dist_win", "course_gate", "recent3", "last1", "rest"):
            f.pop(k, None)  # ばんえいでは意味が薄い・データが取れない要素
    return f


def group_of(race):
    return "ばんえい" if race["code"] == 3 else "平地"


def load_races(group=None):
    races = []
    if not os.path.exists(DATA):
        sys.exit(f"{DATA} がありません。先に keiba/history.py で集めてください。")
    for line in open(DATA, encoding="utf-8"):
        r = json.loads(line)
        hs = r["hs"]
        pay = r["pay"]
        if "単勝" not in pay or "馬連" not in pay or any(h["odds"] is None for h in hs):
            continue
        win = pay["単勝"][0]
        nos = [h["no"] for h in hs]
        if win not in nos or len(hs) > NMAX or len(hs) < 4:
            continue
        a, b = pay["馬連"][0]
        if win not in (a, b):
            continue
        r["win"], r["second"] = win, (b if win == a else a)
        if group and group_of(r) != group:
            continue
        races.append(r)
    races.sort(key=lambda r: (r["d"], r["code"], r["r"]))
    return races


def smooth(rec, n, k=3):
    if not rec:
        return 1.0 / n
    w, s, t, x = rec
    return (w + k / n) / (w + s + t + x + k)


def smooth_place(rec, n, k=3):
    if not rec:
        return 2.0 / n
    w, s, t, x = rec
    return (w + s + 2 * k / n) / (w + s + t + x + k)


def jockey_stats(races):
    st = {}
    for r in races:
        for h in r["hs"]:
            s = st.setdefault(h["jk"], [0, 0])
            s[1] += 1
            s[0] += h["no"] == r["win"]
    return st


def gate_bucket(no, n):
    return 0 if no <= 3 else (2 if no > n - 3 else 1)


def gate_key(race, no):
    return f"{race['code']}|{race['dist']}|{gate_bucket(no, race['n'])}"


def gate_stats(races):
    """競馬場×距離×枠の位置ごとに [実際の勝ち数, 全馬が同じ確率なら期待される勝ち数]。"""
    st = {}
    for r in races:
        for h in r["hs"]:
            s = st.setdefault(gate_key(r, h["no"]), [0.0, 0.0])
            s[0] += h["no"] == r["win"]
            s[1] += 1.0 / r["n"]
    return st


def build(race, jk=None, loo=False, gs=None):
    """1レースの要素行列 (n, F) と、基準の log(市場の勝率) を返す。"""
    hs = race["hs"]
    n = len(hs)
    inv = np.array([1.0 / h["odds"] for h in hs])
    m = np.log(inv / inv.sum())
    kins = [h["kin"] for h in hs if h["kin"]]
    kmean = sum(kins) / len(kins) if kins else 0.0
    rd = date(2000 + int(race["d"][2:4]), int(race["d"][4:6]), int(race["d"][6:8]))
    cols = {k: np.zeros(n) for k in ALL_FEATURES}
    cols["m2"] = m ** 2
    ratios = np.array([(h["kin"] / h["wt"]) if h["kin"] and h["wt"] else 0.0 for h in hs])
    rmean = ratios[ratios > 0].mean() if (ratios > 0).any() else 0.0
    kd = np.array([(h["kin"] - kmean) if h["kin"] else 0.0 for h in hs])
    baba = race.get("baba") or 1.0
    cols["kin_ratio"] = np.where(ratios > 0, ratios - rmean, 0.0)
    cols["kin_baba"] = kd * baba
    for i, h in enumerate(hs):
        cols["form_win"][i] = math.log(smooth(h["all"], n))
        cols["form_place"][i] = math.log(smooth_place(h["all"], n))
        pos = [p / q for p, _, q in h["runs"][:3] if p]
        cols["recent3"][i] = sum(pos) / len(pos) if pos else 0.5
        cols["last1"][i] = (h["runs"][0][0] / h["runs"][0][2]) if h["runs"] and h["runs"][0][0] else 0.5
        cols["venue_win"][i] = math.log(smooth(h["venue"], n))
        cols["dist_win"][i] = math.log(smooth(h["dist_rec"], n))
        pct = (h["dwt"] / h["wt"] * 100) if h["wt"] and h["dwt"] is not None else 0.0
        cols["wt_change"][i] = pct
        cols["wt_change_abs"][i] = abs(pct)
        cols["kin_rel"][i] = (h["kin"] - kmean) if h["kin"] else 0.0
        cols["age"][i] = h["age"] or 4
        cols["sex_f"][i] = 1.0 if h["sex"] == "牝" else 0.0
        cols["gate"][i] = h["no"] / n
        days = 30
        if h["runs"]:
            y, mo, dd = h["runs"][0][1].split(".")
            try:
                days = max((rd - date(2000 + int(y), int(mo), int(dd))).days, 1)
            except ValueError:
                days = 30
        cols["rest"][i] = math.log(days)
        if gs is not None:
            w, e = gs.get(gate_key(race, h["no"]), [0.0, 0.0])
            if loo and e > 0:
                w -= h["no"] == race["win"]
                e -= 1.0 / race["n"]
            cols["course_gate"][i] = math.log((w + 5.0) / (e + 5.0))
        if jk is not None:
            w, t = jk.get(h["jk"], [0, 0])
            if loo and t > 0:
                w -= h["no"] == race["win"]
                t -= 1
            cols["jk_rate"][i] = (w + 1.0) / (t + 10.0)
    return m, cols


def pack(races, names, jk=None, loo=False, gs=None):
    R = len(races)
    X = np.zeros((R, NMAX, 1 + len(names)))
    mask = np.zeros((R, NMAX), bool)
    y = np.zeros(R, int)
    for ri, r in enumerate(races):
        m, cols = build(r, jk, loo, gs)
        n = len(r["hs"])
        X[ri, :n, 0] = m
        for j, nm in enumerate(names):
            X[ri, :n, 1 + j] = cols[nm]
        mask[ri, :n] = True
        y[ri] = [h["no"] for h in r["hs"]].index(r["win"])
    return X, mask, y


def softmax(u, mask):
    u = np.where(mask, u, -1e9)
    u = u - u.max(axis=1, keepdims=True)
    e = np.exp(u) * mask
    return e / e.sum(axis=1, keepdims=True)


def fit(X, mask, y, mu, sd, iters=30):
    """条件付きロジット。基準の列(0番)は標準化しない。"""
    F = X.shape[2]
    Z = (X - mu) / sd
    Z[:, :, 0] = X[:, :, 0]
    Z = Z * mask[:, :, None]
    beta = np.zeros(F)
    beta[0] = 1.0
    R = len(y)
    for _ in range(iters):
        p = softmax(Z @ beta, mask)
        xbar = np.einsum("rn,rnf->rf", p, Z)
        grad = -(Z[np.arange(R), y] - xbar).sum(axis=0)
        d = Z - xbar[:, None, :]
        H = np.einsum("rn,rnf,rng->fg", p, d, d)
        reg = np.eye(F) * LAMBDA
        reg[0, 0] = 0.0
        grad += reg @ (beta - np.where(np.arange(F) == 0, beta, 0))
        step = np.linalg.solve(H + reg + 1e-9 * np.eye(F), grad)
        beta = beta - step
        if np.abs(step).max() < 1e-7:
            break
    return beta


def predict(X, mask, beta, mu, sd):
    Z = (X - mu) / sd
    Z[:, :, 0] = X[:, :, 0]
    return softmax(Z @ beta, mask)


def stats(X, mask):
    flat = X[mask]
    mu = flat.mean(axis=0)
    sd = flat.std(axis=0)
    sd[sd < 1e-9] = 1.0
    return mu, sd


def per_race_loss(p, y):
    return -np.log(np.maximum(p[np.arange(len(y)), y], 1e-9))


def walk_forward(races, names, folds=5):
    """前の期間で学習→次の期間で採点。(レースごとの損失, 分割番号)を返す。"""
    days = sorted({r["d"] for r in races})
    edges = [days[int(len(days) * k / folds)] for k in range(folds)] + ["99999999"]
    losses, fold_ids, probs, idx = [], [], [], []
    for k in range(1, folds):
        train = [r for r in races if r["d"] < edges[k]]
        test = [r for r in races if edges[k] <= r["d"] < edges[k + 1]]
        if len(train) < 50 or not test:
            continue
        jk = jockey_stats(train) if "jk_rate" in names else None
        gs = gate_stats(train) if "course_gate" in names else None
        Xtr, mtr, ytr = pack(train, names, jk, loo=True, gs=gs)
        Xte, mte, yte = pack(test, names, jk, loo=False, gs=gs)
        mu, sd = stats(Xtr, mtr)
        beta = fit(Xtr, mtr, ytr, mu, sd)
        p = predict(Xte, mte, beta, mu, sd)
        losses.append(per_race_loss(p, yte))
        fold_ids.append(np.full(len(yte), k))
        probs.append(p)
        idx.append([races.index(r) for r in test] if False else None)
    return np.concatenate(losses), np.concatenate(fold_ids)


MODEL_FILES = {"平地": MODEL, "ばんえい": os.path.join(HERE, "model_banei.json")}


def run_group(group, feats, out):
    """1グループ（平地／ばんえい）の比べっこ。表を out に追記し、採用した要素のモデルを返す。"""
    races = load_races(group)
    days = sorted({r["d"] for r in races})
    out.append(f"\n## 【{group}】{len(races)}レース（{days[0]}〜{days[-1]}）" if races else f"\n## 【{group}】データなし")
    if len(races) < 150:
        out.append(f"- データ不足（{len(races)}レース。150レース以上で判定）")
        return None, races
    out += ["| 要素 | 内容 | 良くなった幅 | 誤差 | 倍率(t) | 良くなった分割 | 判定 |", "|---|---|---|---|---|---|---|"]
    base, _ = walk_forward(races, [])
    adopted = []
    for nm, desc in feats.items():
        loss, f2 = walk_forward(races, [nm])
        d = base - loss
        se = d.std(ddof=1) / math.sqrt(len(d))
        t = d.mean() / se if se > 0 else 0
        good = sum(1 for k in sorted(set(f2)) if d[f2 == k].mean() > 0)
        nf = len(set(f2))
        ok = t >= 2.5 and good >= max(3, nf - 1)
        if ok:
            adopted.append(nm)
        out.append(f"| {nm} | {desc} | {d.mean():+.4f} | ±{se:.4f} | {t:+.1f} | {good}/{nf} | "
                   f"{'**追加する**' if ok else '追加しない'} |")
    if adopted:
        loss, f2 = walk_forward(races, adopted)
        d = base - loss
        se = d.std(ddof=1) / math.sqrt(len(d))
        out.append(f"\n採用した要素をまとめて追加：良くなった幅 {d.mean():+.4f}（±{se:.4f}、{d.mean() / se:+.1f}倍）")
    loss_all, _ = walk_forward(races, list(feats))
    d = base - loss_all
    se = d.std(ddof=1) / math.sqrt(len(d))
    out.append(f"\n参考：全要素を入れた場合 {d.mean():+.4f}（±{se:.4f}、{d.mean() / se:+.1f}倍）／基準の損失 {base.mean():.4f}")
    names = adopted
    jk = jockey_stats(races) if "jk_rate" in names else None
    gs = gate_stats(races) if "course_gate" in names else None
    X, mask, y = pack(races, names, jk, loo=True, gs=gs)
    mu, sd = stats(X, mask)
    beta = fit(X, mask, y, mu, sd)
    model = {"updated": date.today().isoformat(), "group": group, "races": len(races), "features": names,
             "beta": beta.tolist(), "mu": mu.tolist(), "sd": sd.tolist(),
             "jockey": jk if jk else {}, "gate_stats": gs if gs else {}}
    out.append(f"\n基準の係数（市場の勝率の指数）：{beta[0]:.3f}"
               + ("　採用した要素の係数：" + "、".join(f"{n}={b:+.3f}" for n, b in zip(names, beta[1:])) if names else "　採用した要素：なし"))
    return model, races


def main(write=True):
    out = ["# 「追加する／追加しない」の比べっこ\n",
           "- 基準は「市場の単勝オッズだけ」。平地（ばんえい以外）とばんえいを別々に試す",
           "- 評価：時間順の5分割で、前の期間で学習→次の期間で採点（後ろ4分割）",
           "- 数字は勝ち馬の対数損失の差（基準−追加。**プラスなら追加したほうが良い**）。誤差の目安つき"]
    models = {}
    for group in ("平地", "ばんえい"):
        models[group], _ = run_group(group, features_for(group), out)
    try:
        import odds_move_test as OM
        out.extend(OM.section(load_races()))
    except Exception as e:  # 朝のオッズの保存がまだないときなど
        out.append(f"\n## オッズの変化\n- 試せませんでした：{e}")
    text = "\n".join(out) + "\n"
    print(text)
    if write:
        open(REPORT, "w", encoding="utf-8").write(text)
        for group, model in models.items():
            if model is not None:
                json.dump(model, open(MODEL_FILES[group], "w", encoding="utf-8"), ensure_ascii=False)
        print(f"保存：{REPORT} / {'・'.join(os.path.basename(MODEL_FILES[g]) for g, m in models.items() if m)}")


if __name__ == "__main__":
    main(write="--no-write" not in sys.argv)
