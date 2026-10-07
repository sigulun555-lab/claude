import argparse
from datetime import date
from pathlib import Path

from . import VENUES
from .baseline import course_win_rates, strategies
from .db import connect, save_program, save_result
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


def cmd_fetch(args):
    """ダウンロードだけ行う (DBには入れない)。"""
    raw = Path(args.raw_dir)
    for d in daterange(args.start, args.end):
        got = [k for k in "BK" if fetch(k, d, raw, args.sleep)]
        print(f"{d}: {''.join(got) or '開催なし'}", flush=True)


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
    print("■ 効いている特徴量 上位10")
    for k, v in r["importance"].head(10).items():
        print(f"  {k:<22} {v:,.0f}")
    if args.save:
        r["model"].save_model(args.save)
        print(f"モデルを保存: {args.save}")


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
