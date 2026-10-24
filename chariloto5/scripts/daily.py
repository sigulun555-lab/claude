"""結果ページ(web_fetch の JSON)を取り込み、data/races.json に追記する。

使い方: python daily.py <取得したJSONのパス> ...
- 既に入っている(場コード, 日付)は上書きしない(手で入れた分を守るため)
- 最終5レースの1着がそろった日だけ追加する
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parse_results as P  # noqa: E402

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
RACES = os.path.join(DATA, "races.json")


def main(paths):
    days = json.load(open(RACES))
    have = {(d["velodrome_code"], d["date"]) for d in days}
    added = []
    for path in paths:
        for r in json.load(open(path)).get("results", []):
            day = P.parse_page(r["url"], r.get("full_content") or "")
            if not day or (day["velodrome_code"], day["date"]) in have:
                continue
            if P.complete(day) != 5 or not day["chariloto5"]:
                continue
            days.append(day)
            have.add((day["velodrome_code"], day["date"]))
            added.append(f"{day['date']} {day['velodrome']}")
    days.sort(key=lambda d: (d["date"], d["velodrome_code"]))
    json.dump(days, open(RACES, "w"), ensure_ascii=False, indent=1)
    print("追加:", added or "なし", "| 合計", len(days), "開催")


if __name__ == "__main__":
    main(sys.argv[1:])
