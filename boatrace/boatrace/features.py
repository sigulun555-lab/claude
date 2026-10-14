"""Phase 3: 特徴量作成。1行 = 1レースの1艇。

レース前に分かる情報だけを使う(実際の進入コースやSTは結果なので使わない)。
展示タイムと天候・風・波は締切前の直前情報で分かるので使う。
"""
import numpy as np
import pandas as pd

GRADE = {"A1": 4, "A2": 3, "B1": 2, "B2": 1}
WIND_DIRS = ["北", "北北東", "北東", "東北東", "東", "東南東", "南東", "南南東",
             "南", "南南西", "南西", "西南西", "西", "西北西", "北西", "北北西"]
RECENT_N = 30  # 直近何走の成績を見るか

FEATURES = [
    "boat", "venue", "race_no", "grade_num", "age", "weight",
    "nat_win", "nat_2r", "loc_win", "loc_2r", "motor_2r", "boat_2r",
    "exhibition", "wind_speed", "wave", "wind_sin", "wind_cos",
    "nat_win_rank", "nat_win_diff", "motor_2r_rank", "exhibition_rank", "exhibition_diff",
    "recent_win", "recent_top2", "recent_avg_rank", "recent_n",
    "recent_win_same_boat", "recent_n_same_boat",
    "recent_st", "recent_st_rank", "recent_st_diff", "recent_f", "recent_course",
    "recent_win_venue", "recent_n_venue",
]
# 追加前の特徴量 (比較用)
BASE_FEATURES = [f for f in FEATURES if f not in (
    "recent_st", "recent_st_rank", "recent_st_diff", "recent_f", "recent_course",
    "recent_win_venue", "recent_n_venue")]
CATEGORICAL = ["venue"]

# 朝の時点では分からない直前情報 (展示タイム・風・波) を除いた特徴量
PRERACE_ONLY = {"exhibition", "exhibition_rank", "exhibition_diff", "wind_speed", "wave", "wind_sin", "wind_cos"}
MORNING_FEATURES = [f for f in FEATURES if f not in PRERACE_ONLY]

# 直前チェック用。公式サイトの風向き表示はレース場ごとのコースの向き基準で
# 方角に直せないため、風向きだけ除く (展示タイム・風速・波は使う)。
CHECK_FEATURES = [f for f in FEATURES if f not in ("wind_sin", "wind_cos")]


def load_frame(con) -> pd.DataFrame:
    df = pd.read_sql_query("""
        SELECT e.*, r.date, r.venue, r.race_no, r.wind_dir, r.wind_speed, r.wave,
               res.rank, res.rank_raw, res.exhibition, res.st, res.st_flag, res.course
        FROM entries e
        JOIN races r USING (race_id)
        LEFT JOIN results res ON res.race_id = e.race_id AND res.boat = e.boat
        ORDER BY r.date, r.venue, r.race_no, e.boat
    """, con)
    return df


def _recent_form(df: pd.DataFrame) -> pd.DataFrame:
    """選手ごとの直近成績。そのレースより前の走だけで計算する(未来の情報を混ぜない)。"""
    df = df.sort_values(["date", "race_no", "venue", "boat"]).copy()
    finished = df["rank"].notna()
    df["_win"] = np.where(finished, (df["rank"] == 1).astype(float), np.nan)
    df["_top2"] = np.where(finished, (df["rank"] <= 2).astype(float), np.nan)
    df["_rank"] = df["rank"].astype(float)
    # スタートタイミング (フライング・出遅れは除く)、フライング率、実際に入った進入コース
    df["_st"] = df["st"].where(df["st_flag"].isna() & df["st"].between(0, 0.4))
    df["_f"] = (df["st_flag"] == "F").astype(float).where(df["rank_raw"].notna())
    df["_course"] = df["course"].astype(float)

    def roll(s):
        return s.shift().rolling(RECENT_N, min_periods=1).mean()

    g = df.groupby("reg_no")
    df["recent_win"] = g["_win"].transform(roll)
    df["recent_top2"] = g["_top2"].transform(roll)
    df["recent_avg_rank"] = g["_rank"].transform(roll)
    df["recent_n"] = g.cumcount()

    df["recent_st"] = g["_st"].transform(roll)
    df["recent_f"] = g["_f"].transform(roll)
    df["recent_course"] = g["_course"].transform(roll)
    gv = df.groupby(["reg_no", "venue"])
    df["recent_win_venue"] = gv["_win"].transform(roll)
    df["recent_n_venue"] = gv.cumcount()

    # 同じ枠番での直近成績 (イン屋・アウト屋の傾向)
    g2 = df.groupby(["reg_no", "boat"])
    df["recent_win_same_boat"] = g2["_win"].transform(roll)
    df["recent_n_same_boat"] = g2.cumcount()
    return df.drop(columns=["_win", "_top2", "_rank", "_st", "_f", "_course"])


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["grade_num"] = df["grade"].map(GRADE)
    angle = df["wind_dir"].map({d: i * 2 * np.pi / 16 for i, d in enumerate(WIND_DIRS)})
    df["wind_sin"] = np.sin(angle)
    df["wind_cos"] = np.cos(angle)
    # 展示タイムは0や欠損があるので無効値をNaNに
    df.loc[~df["exhibition"].between(6.0, 8.0), "exhibition"] = np.nan

    # レース内での相対値 (同じレースの他艇と比べてどうか)
    race = df.groupby("race_id")
    df["nat_win_rank"] = race["nat_win"].rank(ascending=False)
    df["nat_win_diff"] = df["nat_win"] - race["nat_win"].transform("mean")
    df["motor_2r_rank"] = race["motor_2r"].rank(ascending=False)
    df["exhibition_rank"] = race["exhibition"].rank()
    df["exhibition_diff"] = df["exhibition"] - race["exhibition"].transform("mean")

    df = _recent_form(df)
    # スタートの速さのレース内での相対値 (_recent_form のあとで計算する)
    race = df.groupby("race_id")
    df["recent_st_rank"] = race["recent_st"].rank()
    df["recent_st_diff"] = df["recent_st"] - race["recent_st"].transform("mean")
    df["venue"] = df["venue"].astype("category")
    return df.sort_values(["race_id", "boat"]).reset_index(drop=True)
