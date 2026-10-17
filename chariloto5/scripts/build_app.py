"""data/ の JSON を app/template.html に埋め込み、1ファイルで動く app/index.html を作る。"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")


def load(name):
    return json.load(open(os.path.join(ROOT, "data", name)))


def main():
    days = load("races.json")
    data = {"model": load("model.json"), "backtest": load("backtest.json"), "days": days}
    html = open(os.path.join(ROOT, "app", "template.html")).read()
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = (html.replace("__DATA__", blob)
                .replace("__RANGE__", f"{days[0]['date']}〜{days[-1]['date']}")
                .replace("__NDAYS__", str(len(days)))
                .replace("__NRACES__", str(sum(len(d['c5_races']) for d in days))))
    open(os.path.join(ROOT, "app", "index.html"), "w").write(html)
    print("app/index.html", len(html), "bytes")


if __name__ == "__main__":
    main()
