#!/usr/bin/env python3
"""過去のレースで、screen.py と同じ計算式の的中率・回収率を確かめる（1点100円）。

  python3 keiba/backtest.py 2026-10-01 2026-10-13

keiba.go.jp の過去の出馬表（DebaTable：その時点の成績・最終オッズ）と払戻（RefundMoneyList）を取得する。
ばんえい（帯広）は対象外。取得したHTMLは keiba/backtest_cache に保存する（.gitignore 済み）。
"""
import concurrent.futures as cf
import csv
import os
import re
import subprocess
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import screen as S  # noqa: E402

BASE = "https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/"
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backtest_cache")
VENUES = {10: "盛岡", 11: "水沢", 18: "浦和", 19: "船橋", 20: "大井", 21: "川崎", 22: "金沢",
          23: "笠松", 24: "名古屋", 27: "園田", 28: "姫路", 31: "高知", 32: "佐賀", 36: "門別"}


def fetch(url, name):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, name)
    for _ in range(3):
        if os.path.exists(path) and os.path.getsize(path) >= 2000:
            break
        subprocess.run(["curl", "-sS", "-m", "40", "-o", path, url], check=False, stderr=subprocess.DEVNULL)
    if not os.path.exists(path):
        return ""
    return open(path, encoding="utf-8", errors="ignore").read()


def text_of(html):
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", html, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t).replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", t)


def to_int(s):
    return int(s.replace(",", ""))


def parse_refund(html):
    """{R: {...払戻...}}"""
    t = text_of(html)
    marks = []
    last = 0
    for m in re.finditer(r"(?:^|\s)(\d{1,2})R\s", t):
        if int(m.group(1)) == last + 1:
            marks.append((last + 1, m.start()))
            last += 1
    out = {}
    for i, (r, st) in enumerate(marks):
        seg = t[st:marks[i + 1][1] if i + 1 < len(marks) else len(t)]
        d = {}
        m = re.search(r"単勝 (\d+) ([\d,]+)円", seg)
        if m:
            d["単勝"] = (int(m.group(1)), to_int(m.group(2)))
        seg_f = re.search(r"複勝(.*?)枠連複", seg)
        if seg_f:
            d["複勝"] = {int(a): to_int(b) for a, b in re.findall(r"(\d+) ([\d,]+)円", seg_f.group(1))}
        m = re.search(r"馬連複 (\d+)-(\d+) ([\d,]+)円", seg)
        if m:
            d["馬連"] = ((int(m.group(1)), int(m.group(2))), to_int(m.group(3)))
        m = re.search(r"馬連単 (\d+)-(\d+) ([\d,]+)円", seg)
        if m:
            d["馬単"] = ((int(m.group(1)), int(m.group(2))), to_int(m.group(3)))
        if "馬連" in d:
            out[r] = d
    return out


def parse_deba(html):
    horses = []
    for chunk in html.split('class="horseNum"')[1:]:
        m = re.match(r">\s*(\d+)\s*<", chunk)
        if not m:
            continue
        no = int(m.group(1))
        rec = re.search(r"全(?:&nbsp;)*</td>(.*?)</tr>", chunk, flags=re.S)
        nums = re.findall(r"(\d+)-?\s*</td>", rec.group(1)) if rec else []
        rec = nums[:4] if len(nums) >= 4 else None
        odds = re.search(r'class="odds_\w+ odds[^"]*"[^>]*>\s*([\d.]+)', chunk)
        pop = re.search(r"\((\d+)人気\)", chunk)
        if not rec:
            continue
        horses.append({"馬番": str(no), "全成績": "-".join(rec),
                       "odds": float(odds.group(1)) if odds else None,
                       "pop": int(pop.group(1)) if pop else None})
    return horses


def job(args):
    d, code, r = args
    ds = d.strftime("%Y/%m/%d").replace("/", "%2F")
    html = fetch(f"{BASE}DebaTable?k_raceDate={ds}&k_raceNo={r}&k_babaCode={code}", f"deba_{d:%Y%m%d}_{code}_{r}.html")
    return (d, code, r), parse_deba(html)


def main(start, end):
    days = [start + timedelta(n) for n in range((end - start).days + 1)]
    refunds = {}
    for d in days:
        ds = d.strftime("%Y/%m/%d").replace("/", "%2F")
        for code in VENUES:
            html = fetch(f"{BASE}RefundMoneyList?k_babaCode={code}&k_raceDate={ds}", f"refund_{d:%Y%m%d}_{code}.html")
            rf = parse_refund(html)
            if rf:
                refunds[(d, code)] = rf
    print(f"開催 {len(refunds)}場日 / レース {sum(len(v) for v in refunds.values())}")
    jobs = [(d, code, r) for (d, code), v in refunds.items() for r in v]
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        decks = dict(ex.map(job, jobs))

    st = {k: [0, 0, 0] for k in ("モデル馬連1位", "選出馬連(10%以上)", "モデル馬単1位", "馬単10点/日",
                                  "モデル単勝1位", "1番人気 単勝", "1番人気 複勝", "モデル複勝1位")}
    daily = {}
    rows = []

    def add(key, hit, pay):
        st[key][0] += 1
        st[key][1] += bool(hit)
        st[key][2] += pay if hit else 0

    for (d, code, r), horses in decks.items():
        pay = refunds[(d, code)][r]
        horses = [h for h in horses if h["全成績"]]
        if len(horses) < 4:
            continue
        pairs = S.race_pairs(horses)
        ex_ = S.race_exacta(horses)
        top = max(pairs, key=pairs.get)
        add("モデル馬連1位", top == pay["馬連"][0], pay["馬連"][1])
        if pairs[top] >= S.THRESHOLD:
            add("選出馬連(10%以上)", top == pay["馬連"][0], pay["馬連"][1])
        if "馬単" in pay:
            t1 = max(ex_, key=ex_.get)
            add("モデル馬単1位", t1 == pay["馬単"][0], pay["馬単"][1])
            for k, v in ex_.items():
                daily.setdefault(d, []).append((v, k, pay["馬単"]))
        # 単勝・複勝（モデル）
        n = len(horses)
        p1 = {}
        for h in horses:
            w, s, tot = S.record(h["全成績"])
            p1[int(h["馬番"])] = (w + S.K / n) / (tot + S.K)
        best = max(p1, key=p1.get)
        if "単勝" in pay:
            add("モデル単勝1位", best == pay["単勝"][0], pay["単勝"][1])
        if "複勝" in pay:
            add("モデル複勝1位", best in pay["複勝"], pay["複勝"].get(best, 0))
        # 1番人気
        fav = [h for h in horses if h["pop"] == 1]
        if fav:
            f = int(fav[0]["馬番"])
            if "単勝" in pay:
                add("1番人気 単勝", f == pay["単勝"][0], pay["単勝"][1])
            if "複勝" in pay:
                add("1番人気 複勝", f in pay["複勝"], pay["複勝"].get(f, 0))
        rows.append((d, code, r, len(horses), round(pairs[top] * 100, 1)))

    # 馬単10点/日（その日の全レース横断・確度順）
    for d, lst in daily.items():
        lst.sort(key=lambda x: -x[0])
        for v, k, actual in lst[:S.EXACTA_N]:
            add("馬単10点/日", k == actual[0], actual[1])

    print(f"\n期間 {start}〜{end}  （1点100円）")
    print(f"{'戦略':<20}{'点数':>6}{'的中':>6}{'的中率':>9}{'回収率':>9}")
    for k, (n, h, p) in st.items():
        if n:
            print(f"{k:<20}{n:>6}{h:>6}{h / n * 100:>8.1f}%{p / (100 * n) * 100:>8.0f}%")
    return st


if __name__ == "__main__":
    a = date.fromisoformat(sys.argv[1])
    b = date.fromisoformat(sys.argv[2])
    start, end = a, b
    main(a, b)
