#!/usr/bin/env python3
"""過去（と当日）のレースの出馬表・最終オッズ・払戻を集めて keiba/data/history.jsonl に貯める。

  python3 keiba/history.py 2026-08-01 2026-10-13   # 期間を指定して追加（取得済みの日はとばす）
  python3 keiba/history.py today                    # 日本時間の今日（夜に全レースが終わってから）
  python3 keiba/history.py yesterday
  python3 keiba/history.py venue 3 2026-08-01 2026-10-17 [--refresh]   # 指定した競馬場（3=帯広）だけを、すでに集めた日にも追加

keiba.go.jp の DebaTable（出馬表：その時点の成績・最終オッズ・人気・馬体重）と
RefundMoneyList（払戻）を使う。ばんえい（帯広・コード3）も対象に含める（2026-10-17 追加）。
1レース1行のJSON。1頭ごとに全成績・場・距離の成績と、近5走（着順・日付・頭数）を持つ。
"""
import concurrent.futures as cf
import json
import os
import re
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "history.jsonl")
BASE = "https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/"
VENUES = {3: "帯広", 10: "盛岡", 11: "水沢", 18: "浦和", 19: "船橋", 20: "大井", 21: "川崎", 22: "金沢",
          23: "笠松", 24: "名古屋", 27: "園田", 28: "姫路", 31: "高知", 32: "佐賀", 36: "門別"}


def http(url, retries=4):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            return urllib.request.urlopen(req, timeout=40).read().decode("utf-8", errors="ignore")
        except Exception:
            time.sleep(2 * (i + 1))
    return ""


def text_of(html):
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", html, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t).replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", t)


def to_int(s):
    return int(s.replace(",", ""))


def parse_refund(html):
    t = text_of(html)
    marks, last = [], 0
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
            d["単勝"] = [int(m.group(1)), to_int(m.group(2))]
        f = re.search(r"複勝(.*?)枠連複", seg)
        if f:
            d["複勝"] = {a: to_int(b) for a, b in re.findall(r"(\d+) ([\d,]+)円", f.group(1))}
        m = re.search(r"馬連複 (\d+)-(\d+) ([\d,]+)円", seg)
        if m:
            d["馬連"] = [[int(m.group(1)), int(m.group(2))], to_int(m.group(3))]
        m = re.search(r"馬連単 (\d+)-(\d+) ([\d,]+)円", seg)
        if m:
            d["馬単"] = [[int(m.group(1)), int(m.group(2))], to_int(m.group(3))]
        if "馬連" in d:
            out[r] = d
    return out


def nums_of(chunk, label):
    m = re.search(rf"<td>{label}(?:&nbsp;)*</td>(.*?)</tr>", chunk, flags=re.S)
    if not m:
        return None
    n = re.findall(r"(\d+)-?\s*</td>", m.group(1))
    return [int(x) for x in n[:4]] if len(n) >= 4 else None


def parse_deba(html):
    """{'dist','surf','name','hs':[...]}"""
    head = text_of(html[:60000])
    m = re.search(r"(ダート|芝)\s*(\d{3,4})\s*ｍ", head)
    nm = re.search(r"<h3[^>]*>(.*?)</h3>", html, flags=re.S)
    bm = re.search(r"馬場：([\d.]+)", head)
    out = {"dist": int(m.group(2)) if m else None, "surf": m.group(1) if m else None,
           "baba": float(bm.group(1)) if bm else None,
           "name": re.sub(r"\s+", "", re.sub(r"<[^>]+>", "", nm.group(1))) if nm else "", "hs": []}
    for chunk in html.split('class="horseNum"')[1:]:
        m = re.match(r">\s*(\d+)\s*<", chunk)
        if not m:
            continue
        allrec = nums_of(chunk, "全")
        if not allrec:
            continue
        txt = text_of(chunk)
        o = re.search(r'class="odds_\w+[^"]*"[^>]*>\s*([\d.]+)', chunk)
        pop = re.search(r"\((\d+)人気\)", chunk)
        wt = re.search(r'odds_weight">\s*(\d{3,4})\s*<br>\s*\(([+-]?\d+|-)\)', chunk)
        jk = re.search(r'jockeyName"[^>]*>([^<]+)<', chunk)
        nmh = re.search(r'horseName"[^>]*>([^<]+)<', chunk)
        sx = re.search(r"(牡|牝|セン)(\d+) \S+ \d\d\.\d\d生 ([☆◇△▲★]?) ?([\d.]+)", txt)
        runs = []
        runs_b = []
        for rm in re.finditer(r"(\d{1,2}|除外|取消|中止|失格|計不) (\d\d\.\d\d\.\d\d) (?:良|稍重|重|不良) (\d+)頭", txt):
            runs.append([int(rm.group(1)) if rm.group(1).isdigit() else None, rm.group(2), int(rm.group(3))])
        if not runs and out["dist"] == 200:
            runs, runs_b = parse_banei_runs(chunk, txt)
        out["hs"].append({
            "no": int(m.group(1)), "name": nmh.group(1).strip() if nmh else "",
            "jk": jk.group(1).strip() if jk else "",
            "odds": float(o.group(1)) if o else None, "pop": int(pop.group(1)) if pop else None,
            "wt": int(wt.group(1)) if wt else None,
            "dwt": (0 if wt.group(2) == "-" else int(wt.group(2))) if wt else None,
            "sex": sx.group(1) if sx else None, "age": int(sx.group(2)) if sx else None,
            "kin": float(sx.group(4)) if sx else None, "red": sx.group(3) if sx else "",
            "all": allrec, "venue": nums_of(chunk, "場"), "dist_rec": nums_of(chunk, "距"),
            "runs": runs[:5], "runs_b": runs_b[:5],
        })
    return out


def parse_banei_runs(chunk, txt):
    """ばんえいの近5走。runs=[着順,日付,頭数]、runs_b=[着順,日付,馬場水分,頭数,人気,馬体重,騎手,ソリ重量,タイム秒,勝ち馬との差(秒)]"""
    base = []
    for rm in re.finditer(r'pastRank[^>]*>\s*(\d{1,2}|除外|取消|中止|失格|計不)\s*</span>\s*(\d\d\.\d\d\.\d\d)\s+([\d.]+)\s+(\d+)頭', chunk):
        base.append([int(rm.group(1)) if rm.group(1).isdigit() else None, rm.group(2), float(rm.group(3)), int(rm.group(4))])
    if not base:
        return [], []
    tail = txt[txt.find("生") + 1:] if "生" in txt else txt
    info = re.findall(r"(\d+)人 (\d{3,4}) (\S+) (\d{3,4})", tail)
    times = re.findall(r"\b(\d):(\d\d\.\d)\b", tail)
    after = tail[tail.rfind("）") + 1:] if "）" in tail else tail
    diffs = re.findall(r"(\d+\.\d) ([^\s\d.]+)", after)
    runs, runs_b = [], []
    for i, (pos, dt, baba, n) in enumerate(base):
        runs.append([pos, dt, n])
        pop, wt, jk, kin = (info[i] if i < len(info) else (None, None, None, None))
        tsec = (int(times[i][0]) * 60 + float(times[i][1])) if i < len(times) else None
        diff = float(diffs[i][0]) if i < len(diffs) else None
        runs_b.append([pos, dt, baba, n, int(pop) if pop else None, int(wt) if wt else None, jk,
                       int(kin) if kin else None, tsec, diff])
    return runs, runs_b


def collect_day(d, only=None):
    ds = d.strftime("%Y/%m/%d").replace("/", "%2F")
    out = []
    for code, vname in VENUES.items():
        if only and code not in only:
            continue
        rf = parse_refund(http(f"{BASE}RefundMoneyList?k_babaCode={code}&k_raceDate={ds}"))
        if not rf:
            continue
        for r, pay in rf.items():
            page = parse_deba(http(f"{BASE}DebaTable?k_raceDate={ds}&k_raceNo={r}&k_babaCode={code}"))
            if len(page["hs"]) < 4:
                continue
            out.append({"d": d.strftime("%Y%m%d"), "code": code, "v": vname, "r": r, "n": len(page["hs"]),
                        "dist": page["dist"], "surf": page["surf"], "baba": page.get("baba"), "name": page["name"],
                        "hs": page["hs"], "pay": pay})
    return out


def existing_days():
    if not os.path.exists(DATA):
        return set()
    return {json.loads(l)["d"] for l in open(DATA, encoding="utf-8") if l.strip()}


def jst(offset=0):
    return (datetime.now(timezone(timedelta(hours=9))) + timedelta(days=offset)).date()


def backfill(code, start, end, refresh=False):
    """すでに集めた日に、指定した競馬場（例：ばんえい=3）だけを追加する。"""
    have = set()
    if os.path.exists(DATA):
        have = {(json.loads(l)["d"], json.loads(l)["code"]) for l in open(DATA, encoding="utf-8") if l.strip()}
    days = [start + timedelta(n) for n in range((end - start).days + 1)]
    if refresh:
        lo, hi = start.strftime("%Y%m%d"), end.strftime("%Y%m%d")
        keep = [l for l in open(DATA, encoding="utf-8") if l.strip()]
        with open(DATA, "w", encoding="utf-8") as f:
            f.writelines(l for l in keep if not (json.loads(l)["code"] == code and lo <= json.loads(l)["d"] <= hi))
        have = {k for k in have if not (k[1] == code and lo <= k[0] <= hi)}
    days = [d for d in days if (d.strftime("%Y%m%d"), code) not in have]
    total = 0
    with cf.ThreadPoolExecutor(max_workers=3) as ex:
        for d, races in zip(days, ex.map(lambda d: collect_day(d, only={code}), days)):
            with open(DATA, "a", encoding="utf-8") as f:
                for r in races:
                    f.write(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n")
            total += len(races)
            if races:
                print(f"{d} {len(races)}レース", flush=True)
    print(f"追加 {total}レース（競馬場コード{code}）→ {DATA}")


def main(args):
    if args and args[0] == "venue":
        return backfill(int(args[1]), date.fromisoformat(args[2]), date.fromisoformat(args[3]), refresh="--refresh" in args)
    if args and args[0] == "today":
        start = end = jst()
    elif args and args[0] == "yesterday":
        start = end = jst(-1)
    else:
        start, end = date.fromisoformat(args[0]), date.fromisoformat(args[1])
    have = existing_days()
    days = [start + timedelta(n) for n in range((end - start).days + 1)]
    days = [d for d in days if d.strftime("%Y%m%d") not in have or d == jst()]
    os.makedirs(os.path.dirname(DATA), exist_ok=True)
    if jst() in days:  # 当日は取り直す（途中で終わったレースを上書き）
        keep = [l for l in open(DATA, encoding="utf-8")] if os.path.exists(DATA) else []
        today = jst().strftime("%Y%m%d")
        with open(DATA, "w", encoding="utf-8") as f:
            f.writelines(l for l in keep if json.loads(l)["d"] != today)
    total = 0
    with cf.ThreadPoolExecutor(max_workers=3) as ex:
        for d, races in zip(days, ex.map(collect_day, days)):
            with open(DATA, "a", encoding="utf-8") as f:
                for r in races:
                    f.write(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n")
            total += len(races)
            print(f"{d} {len(races)}レース", flush=True)
    print(f"追加 {total}レース → {DATA}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
