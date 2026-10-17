"""チャリロト.com のレース結果ページ(マークダウン化したもの)から、
チャリロト5対象(最終5レース)の情報を取り出して JSON にする。

使い方: python parse_results.py <web_fetch結果のJSON> ... > 出力
入力は {"results": [{"url":..., "full_content":...}]} 形式。
"""
import json
import re
import sys
import unicodedata

GRADE_ORDER = ["SS", "S1", "S2", "A1", "A2", "A3", "L1"]


def norm(s):
    return unicodedata.normalize("NFKC", s).replace(" ", "").strip()


def parse_lines(row):
    """周回予想の行 '|7 |2 | |1 |9 |8 | |3 |...' を [[7,2],[1,9,8],...] にする。"""
    cells = [c.strip() for c in row.strip().strip("|").split("|")]
    lines, cur = [], []
    for c in cells:
        if c.isdigit():
            cur.append(int(c))
        elif cur:
            lines.append(cur)
            cur = []
    if cur:
        lines.append(cur)
    return lines


def parse_payout(block, label):
    m = re.search(r"\|" + label + r" \|\n\| --- \| --- \|\n\|複 \|[^\n]*\n\|単 \|([^\n]*)", block)
    if not m:
        return None
    pm = re.search(r"([\d\-]+) ([\d,]+)円", m.group(1))
    return int(pm.group(2).replace(",", "")) if pm else None


def parse_race(block):
    head = re.match(r"第(\d+)レース ([^\n]*)", block)
    race = {"race": int(head.group(1)), "name": norm(head.group(2))}
    riders = []
    table = block.split("周回予想")[0]  # 周回予想の行を選手行と取り違えないように
    for m in re.finditer(r"^\|([^|\n]*)\|(\d) \|([^|\n]*)\|(\d+) \|([^|\n]*)\|(\d+) \|([^|\n]*)\|([^|\n]*)\|([^|\n]*)\|([^|\n]*)\|([^|\n]*)\|", table, re.M):
        finish = m.group(1).strip()
        riders.append({
            "car": int(m.group(2)),
            "name": m.group(3).strip(),
            "age": int(m.group(4)),
            "pref": m.group(5).strip(),
            "term": int(m.group(6)),
            "grade": norm(m.group(7)),
            "finish": int(finish) if finish.isdigit() else None,  # 失格・落車などは None
            "kimarite": m.group(10).strip() or None,
            "sb": m.group(11).strip() or None,
        })
    if not riders:
        return None
    riders.sort(key=lambda r: r["car"])
    race["riders"] = riders
    race["field_size"] = len(riders)
    lm = re.search(r"周回予想\n\n(\|[^\n]*)\n", block)
    race["lines"] = parse_lines(lm.group(1)) if lm else []
    winners = [r["car"] for r in riders if r["finish"] == 1]
    race["winners"] = winners  # 同着なら複数
    race["exacta"] = parse_payout(block, "2車連")
    race["trifecta"] = parse_payout(block, "3連勝")
    return race


def parse_c5(content):
    i = content.find("回チャリロト５")
    if i < 0:
        return None
    sec = content[i:].split("チャリロト３")[0]  # 後ろに続くチャリロト3の欄を読まないように
    def num(label):
        m = re.search(r"\|" + label + r" \|([\d,]*)[円口]? \|", sec)
        return int(m.group(1).replace(",", "")) if m and m.group(1) else None
    hit = re.search(r"\|的中番号 \|([\d ]+)\|", sec)
    pay = re.search(r"払戻金[^\d]*([\d,]+)円", sec)
    return {
        "carryover_in": num("前回からのキャリーオーバー額"),
        "sold_units": num("販売口数（1口100円）"),
        "sales": num("総販売金額"),
        "hit_units": num("総的中口数"),
        "carryover_out": num("次回へのキャリーオーバー額"),
        "winning_numbers": [int(x) for x in hit.group(1).split()] if hit else None,
        "payout": int(pay.group(1).replace(",", "")) if pay else None,
    }


def join_broken_cells(text):
    """セル内改行 (例: S/B 欄の 'S\nB') で分断された表の行をつなぎ直す。"""
    out = []
    for line in text.split("\n"):
        if out and out[-1].startswith("|") and not out[-1].rstrip().endswith("|") and line and not line.startswith("|"):
            out[-1] += line
        else:
            out.append(line)
    return "\n".join(out)


def parse_page(url, content):
    m = re.search(r"/results/(\d+)/(\d{4}-\d{2}-\d{2})", url)
    title = re.search(r"# 【[^】]*】\n(\S+)競輪 \n[^\n]*\n(\S+)\n(\S+)", content)
    race_part = join_broken_cells(content.split("各レースの一着")[0])
    blocks = re.split(r"\n(?=第\d+レース )", race_part)
    races = [r for r in (parse_race(b) for b in blocks[1:]) if r]
    if not races:
        return None
    races.sort(key=lambda r: r["race"])
    return {
        "velodrome_code": int(m.group(1)),
        "velodrome": title.group(1) if title else None,
        "date": m.group(2),
        "day_label": title.group(2) if title else None,
        "grade": norm(title.group(3)) if title else None,
        "num_races": len(races),
        "c5_races": races[-5:],  # 最終競走から数えて連続する5競走
        "chariloto5": parse_c5(content),
        "source": url,
    }


def main():
    days = {}
    for path in sys.argv[1:]:
        d = json.load(open(path))
        for r in d.get("results", []):
            day = parse_page(r["url"], r.get("full_content") or "")
            if not day:
                continue
            key = (day["velodrome_code"], day["date"])
            # 同じ日を複数回取得したときは、最終5レースの結果がそろっている方を使う
            if key not in days or complete(day) >= complete(days[key]):
                days[key] = day
    out = sorted((d for d in days.values() if complete(d) == 5), key=lambda d: (d["date"], d["velodrome_code"]))
    json.dump(out, sys.stdout, ensure_ascii=False, indent=1)


def complete(day):
    return sum(1 for r in day["c5_races"] if r["winners"])


if __name__ == "__main__":
    main()
