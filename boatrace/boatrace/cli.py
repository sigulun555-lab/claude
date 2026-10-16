import argparse
from datetime import date, timedelta
from pathlib import Path

from . import VENUES
from .baseline import course_win_rates, strategies
from .db import connect, save_odds, save_program, save_result
from .download import daterange, extract_text, fetch
from .parse_program import parse_program
from .parse_result import parse_result


def _date(s):
    return date.fromisoformat(s)


def _cached(kind, d, raw):
    path = raw / f"{kind.lower()}{d:%y%m%d}.lzh"
    return path if path.exists() else None


def cmd_load(args):
    con = connect(args.db)
    raw = Path(args.raw_dir)
    for d in daterange(args.start, args.end):
        ymd = d.strftime("%Y%m%d")
        get = (lambda k: _cached(k, d, raw)) if args.offline else (lambda k: fetch(k, d, raw, args.sleep))
        b = get("B")
        if b:
            races, entries = parse_program(extract_text(b), ymd)
            save_program(con, races, entries)
        k = get("K")
        if k:
            races_k, results, payouts = parse_result(extract_text(k), ymd)
            save_result(con, races_k, results, payouts)
        print(f"{d}: 番組 {'有' if b else '無'} / 成績 {'有' if k else '無'}")


LOOKBACK_DAYS = 7  # 直近分を取るときは、取り損ねや未完成のファイルを直すためここまで遡る


def _live_start(start, end):
    """終了日が直近 (今日から2日以内) なら、開始日を LOOKBACK_DAYS 前まで広げる。

    取得済みのファイルは再ダウンロードされないので、遡っても通信は増えない。
    """
    from .download import RECENT_DAYS, today_jst

    if (today_jst() - end).days <= RECENT_DAYS:
        return min(start, end - timedelta(days=LOOKBACK_DAYS))
    return start


def cmd_fetch(args):
    """ダウンロードだけ行う (DBには入れない)。"""
    raw = Path(args.raw_dir)
    for d in daterange(_live_start(args.start, args.end), args.end):
        got = [k for k in "BK" if fetch(k, d, raw, args.sleep)]
        print(f"{d}: {''.join(got) or '開催なし'}", flush=True)


# 取得するページと、HTML から {券種: {組番: オッズ}} を返す読み取り関数
ODDS_PAGES = {
    # 単勝ページには複勝も載っている。複勝は幅の下限と上限を別の券種名で保存する
    "単勝": ("oddstf", lambda m, h: {
        "単勝": m.parse_tansho(h),
        "複勝": {b: lo for b, (lo, hi) in m.parse_fukusho(h).items()},
        "複勝上限": {b: hi for b, (lo, hi) in m.parse_fukusho(h).items()},
    }),
    "2連単": ("odds2tf", lambda m, h: m.parse_exacta(h)),  # 2連複も同じページで取れる
    "3連単": ("odds3t", lambda m, h: {"3連単": m.parse_trifecta(h)}),
}


def choose_venues(date: str, venues, n: int) -> set:
    """その日に取る場を選ぶ。日付だけで決まる抽選なので、同じ日は何度実行しても同じ場になり、
    特定の場(場コードの小さい場など)に偏らない。"""
    import random

    pool = sorted(venues)
    return set(random.Random(date).sample(pool, min(n, len(pool))))


def cmd_fetch_odds(args):
    """DBにあるレースの締切時オッズを公式サイトから取り、CSVに追記する(途中再開可)。"""
    import csv
    from . import odds as odds_mod

    con = connect(args.db)
    page, parser = ODDS_PAGES[args.bet_type]
    out = Path(args.csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out.exists():
        with out.open() as f:
            done = {row[0] for row in csv.reader(f)}
    races = con.execute(
        "SELECT race_id, date, venue, race_no FROM races WHERE date BETWEEN ? AND ? ORDER BY race_id",
        [args.start.strftime("%Y%m%d"), args.end.strftime("%Y%m%d")]).fetchall()
    if args.max_venues:
        keep = set()
        for date in sorted({r[1] for r in races}):
            venues = choose_venues(date, {r[2] for r in races if r[1] == date}, args.max_venues)
            keep |= {(date, v) for v in venues}
        races = [r for r in races if (r[1], r[2]) in keep]
    todo = [r for r in races if r[0] not in done]
    print(f"{args.bet_type}: 対象 {len(races)} レース / 取得済み {len(races) - len(todo)}", flush=True)
    with out.open("a", newline="") as f:
        w = csv.writer(f)
        for n, (race_id, date, venue, race_no) in enumerate(todo, 1):
            try:
                html = odds_mod.fetch_page(page, date, venue, race_no, args.sleep)
            except Exception as e:  # 1レースの失敗で全体を止めない
                print(f"失敗 {race_id}: {e}", flush=True)
                continue
            for bet_type, combos in parser(odds_mod, html).items():
                for combo, v in combos.items():
                    w.writerow([race_id, bet_type, combo, v])
            f.flush()
            if n % 200 == 0:
                print(f"{n}/{len(todo)}", flush=True)


def cmd_load_odds(args):
    import csv
    con = connect(args.db)
    for p in args.files:
        with open(p) as f:
            rows = [(r, t, c, float(o) if o else None) for r, t, c, o in csv.reader(f)]
        save_odds(con, rows)
        print(f"取り込み: {p} ({len(rows)}件)")


def cmd_load_text(args):
    """手元の展開済み TXT を取り込む (BYYMMDD.TXT / KYYMMDD.TXT)。"""
    con = connect(args.db)
    for p in map(Path, args.files):
        text = p.read_bytes().decode("cp932", errors="replace")
        ymd = "20" + p.stem[1:7]
        if p.stem[0].upper() == "B":
            save_program(con, *parse_program(text, ymd))
        elif p.stem[0].upper() == "K":
            save_result(con, *parse_result(text, ymd))
        print(f"取り込み: {p}")


def cmd_baseline(args):
    con = connect(args.db)
    title = VENUES.get(args.venue, "全場") if args.venue else "全場"
    print(f"■ コース別1着率 ({title})")
    for c, n, rate in course_win_rates(con, args.venue):
        print(f"  {c}コース: {rate:6.1%}  ({n}走)")
    print("■ ベースライン戦略 (1点100円)")
    for name, (n, hit, roi) in strategies(con).items():
        print(f"  {name:<14} レース数 {n:>6}  的中率 {hit:6.1%}  回収率 {roi:6.1%}")


def cmd_backtest(args):
    from .backtest import run
    from .features import build_features, load_frame

    con = connect(args.db)
    df = build_features(load_frame(con))
    r = run(con, df, args.test_ratio)
    print(f"学習: {r['n_train_races']}レース / テスト: {r['n_test_races']}レース ({r['train_until']}以降)")
    print(f"■ 1着確率の精度 (logloss, 小さいほど良い)")
    print(f"  モデル {r['logloss_model']:.4f}  /  枠番だけ {r['logloss_prior']:.4f}")
    print("■ 確率上位を機械的に買った場合 (1点100円)")
    for name, (hit, roi) in r["bets"].items():
        print(f"  {name:<10} 的中率 {hit:6.1%}  回収率 {roi:6.1%}")
    print("■ 本命の予想確率と実際の1着率")
    for b, row in r["calibration"].iterrows():
        print(f"  予想 {b}: 平均 {row['pred']:.1%} → 実際 {row['actual']:.1%} ({int(row['n'])}レース)")
    for bet_type, rows in r["ev"].items():
        print(f"■ 期待値で絞って買った場合: {bet_type} (締切時オッズ, 1点100円)")
        for th, n_races, n_bets, hit, roi in rows:
            print(f"  期待値 {th:.1f}以上  {n_races:>5}レース {n_bets:>6}点  的中率 {hit:6.1%}  回収率 {roi:6.1%}")
    print("■ 効いている特徴量 上位10")
    for k, v in r["importance"].head(10).items():
        print(f"  {k:<22} {v:,.0f}")
    if args.save:
        r["model"].save_model(args.save)
        print(f"モデルを保存: {args.save}")


def cmd_papertrade(args):
    import lightgbm as lgb

    from .features import build_features, load_frame
    from .papertrade import make_picks, report, save_picks

    con = connect(args.db)
    model = lgb.Booster(model_file=args.model)
    # 同じフォルダに直前チェック用モデルがあれば、オッズと合成するルールも記録する
    chk = Path(args.model).with_name("model_check.txt")
    model_check = lgb.Booster(model_file=str(chk)) if chk.exists() else None
    feats = build_features(load_frame(con))
    # 直近の日は、結果が後から入ったものを採点し直す (オッズがない日は何もしない)
    for d in daterange(_live_start(args.start, args.end), args.end):
        ymd = d.strftime("%Y%m%d")
        rows = make_picks(con, model, feats, ymd, model_check)
        if rows:
            save_picks(Path(args.csv), ymd, rows)
        print(f"{d}: {len(rows)}点")
    print(report(Path(args.csv)))


def cmd_sheet(args):
    import lightgbm as lgb

    from .features import build_features, load_frame
    import json

    from .sheet import sheet_data, to_markdown

    con = connect(args.db)
    data = sheet_data(con, lgb.Booster(model_file=args.model), build_features(load_frame(con)),
                      args.date.strftime("%Y%m%d"))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(to_markdown(data))
    if args.json:
        Path(args.json).write_text(json.dumps(data, ensure_ascii=False))
    print(to_markdown(data)[:2000])


def cmd_train(args):
    from .features import CHECK_FEATURES, FEATURES, MORNING_FEATURES, build_features, load_frame
    from .model import train

    con = connect(args.db)
    df = build_features(load_frame(con))
    features = MORNING_FEATURES if args.morning else CHECK_FEATURES if args.check else FEATURES
    model = train(df, features=features)
    model.save_model(args.out)
    print(f"学習: {df['date'].min()}〜{df['date'].max()} → {args.out}")


def cmd_check(args):
    import lightgbm as lgb

    from .check import check_races, parse_request

    con = connect(args.db)
    lines = [l for l in Path(args.request).read_text().splitlines() if l.strip() and not l.startswith("#")]
    text = check_races(con, lgb.Booster(model_file=args.model), [parse_request(l) for l in lines])
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(text)
    print(text)


def cmd_live(args):
    """朝の予想表の、これから締切のレースの今の単勝オッズを取る (毎時のオッズ取得)。"""
    import json
    from datetime import datetime

    from .live import fetch_live
    from .download import JST

    sheet = json.loads(Path(args.sheet).read_text())
    now = datetime.fromisoformat(args.now) if args.now else datetime.now(JST)
    if sheet["date"] != now.strftime("%Y-%m-%d"):
        print(f"予想表は {sheet['date']} の分で、今日 ({now:%Y-%m-%d}) の分ではないので何もしません")
        return
    out = Path(args.out)
    previous = json.loads(out.read_text()) if out.exists() else None
    result = fetch_live(sheet, now, previous, window=args.window, sleep=args.sleep, lead=args.lead,
                        cand_only=not args.all_races)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False))
    print(f"{result['asof']} 時点: {result['fetched']}レースを対象に、{len(result['races'])}レース分のオッズを保存"
          + (f" (失敗 {len(result['errors'])}件)" if result["errors"] else ""))


def main(argv=None):
    p = argparse.ArgumentParser(prog="boatrace", description="競艇予想アプリ")
    p.add_argument("--db", default="data/boatrace.sqlite")
    sub = p.add_subparsers(required=True)

    s = sub.add_parser("load", help="公式サイトから期間分をダウンロードしてDBへ")
    s.add_argument("start", type=_date, help="開始日 YYYY-MM-DD")
    s.add_argument("end", type=_date, help="終了日 YYYY-MM-DD")
    s.add_argument("--raw-dir", default="data/raw")
    s.add_argument("--sleep", type=float, default=1.0, help="リクエスト間隔(秒)")
    s.add_argument("--offline", action="store_true", help="ダウンロードせず取得済みファイルだけ使う")
    s.set_defaults(func=cmd_load)

    s = sub.add_parser("fetch", help="公式サイトから期間分をダウンロードするだけ")
    s.add_argument("start", type=_date)
    s.add_argument("end", type=_date)
    s.add_argument("--raw-dir", default="data/raw")
    s.add_argument("--sleep", type=float, default=1.0)
    s.set_defaults(func=cmd_fetch)

    s = sub.add_parser("fetch-odds", help="DBにあるレースの締切時オッズを取得してCSVへ")
    s.add_argument("start", type=_date)
    s.add_argument("end", type=_date)
    s.add_argument("--bet-type", choices=list(ODDS_PAGES), default="単勝")
    s.add_argument("--csv", required=True)
    s.add_argument("--sleep", type=float, default=2.0)
    s.add_argument("--max-venues", type=int, help="1日あたりこの数の場だけ取る (日付から決まる抽選)")
    s.set_defaults(func=cmd_fetch_odds)

    s = sub.add_parser("load-odds", help="オッズCSVをDBへ")
    s.add_argument("files", nargs="+")
    s.set_defaults(func=cmd_load_odds)

    s = sub.add_parser("papertrade", help="固定ルールで買い目を記録し、累計成績を表示")
    s.add_argument("start", type=_date)
    s.add_argument("end", type=_date)
    s.add_argument("--model", required=True)
    s.add_argument("--csv", default="data/papertrade/picks.csv")
    s.set_defaults(func=cmd_papertrade)

    s = sub.add_parser("sheet", help="朝の予想表 (Markdown) を作る")
    s.add_argument("date", type=_date)
    s.add_argument("--model", required=True)
    s.add_argument("--out", required=True)
    s.add_argument("--json", help="同じ内容をJSONでも保存する (予想表ページ用)")
    s.set_defaults(func=cmd_sheet)

    s = sub.add_parser("train", help="全データでモデルを学習して保存")
    s.add_argument("--out", required=True)
    s.add_argument("--morning", action="store_true", help="直前情報を使わない朝用モデル")
    s.add_argument("--check", action="store_true", help="風向きを使わない直前チェック用モデル")
    s.set_defaults(func=cmd_train)

    s = sub.add_parser("live", help="これから締切のレースの今の単勝オッズを取る (毎時のオッズ取得)")
    s.add_argument("--sheet", required=True, help="朝の予想表のJSON (yosou/latest.json)")
    s.add_argument("--out", required=True)
    s.add_argument("--window", type=int, default=20, help="今から何分以内に締切のレースを取るか")
    s.add_argument("--lead", type=int, default=2, help="締切まであと何分より近いレースは取らないか")
    s.add_argument("--all-races", action="store_true", help="🔴だけでなく全レースを取る")
    s.add_argument("--sleep", type=float, default=1.5)
    s.add_argument("--now", help="テスト用: 現在時刻 (ISO形式)")
    s.set_defaults(func=cmd_live)

    s = sub.add_parser("check", help="直前チェック (直前情報と今のオッズで買い/見送り)")
    s.add_argument("--request", required=True, help="'YYYY-MM-DD 場名 R' を1行ずつ書いたファイル")
    s.add_argument("--model", required=True)
    s.add_argument("--out", required=True)
    s.set_defaults(func=cmd_check)

    s = sub.add_parser("load-text", help="展開済みTXTファイルをDBへ")
    s.add_argument("files", nargs="+")
    s.set_defaults(func=cmd_load_text)

    s = sub.add_parser("baseline", help="ベースライン予想の的中率・回収率")
    s.add_argument("--venue", type=int, help="場コード 1-24")
    s.set_defaults(func=cmd_baseline)

    s = sub.add_parser("backtest", help="モデルを学習して過去データで検証")
    s.add_argument("--test-ratio", type=float, default=0.25, help="テストに使う期間の割合")
    s.add_argument("--save", help="学習したモデルの保存先")
    s.set_defaults(func=cmd_backtest)

    args = p.parse_args(argv)
    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    args.func(args)


if __name__ == "__main__":
    main()
