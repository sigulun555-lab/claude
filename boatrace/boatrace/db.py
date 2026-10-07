import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS races (
    race_id TEXT PRIMARY KEY,
    date TEXT NOT NULL,
    venue INTEGER NOT NULL,
    race_no INTEGER NOT NULL,
    race_name TEXT,
    distance INTEGER,
    deadline TEXT,
    weather TEXT,
    wind_dir TEXT,
    wind_speed INTEGER,
    wave INTEGER,
    technique TEXT
);
CREATE TABLE IF NOT EXISTS entries (
    race_id TEXT NOT NULL,
    boat INTEGER NOT NULL,
    reg_no INTEGER,
    name TEXT,
    age INTEGER,
    branch TEXT,
    weight INTEGER,
    grade TEXT,
    nat_win REAL, nat_2r REAL,
    loc_win REAL, loc_2r REAL,
    motor_no INTEGER, motor_2r REAL,
    boat_no INTEGER, boat_2r REAL,
    PRIMARY KEY (race_id, boat)
);
CREATE TABLE IF NOT EXISTS results (
    race_id TEXT NOT NULL,
    boat INTEGER NOT NULL,
    reg_no INTEGER,
    rank INTEGER,
    rank_raw TEXT,
    exhibition REAL,
    course INTEGER,
    st REAL,
    st_flag TEXT,
    race_time TEXT,
    PRIMARY KEY (race_id, boat)
);
CREATE TABLE IF NOT EXISTS payouts (
    race_id TEXT NOT NULL,
    bet_type TEXT NOT NULL,
    combo TEXT NOT NULL,
    amount INTEGER,
    popularity INTEGER,
    PRIMARY KEY (race_id, bet_type, combo)
);
CREATE INDEX IF NOT EXISTS idx_races_date ON races(date);
CREATE INDEX IF NOT EXISTS idx_entries_reg ON entries(reg_no);
"""

RACE_PROGRAM_COLS = ["race_id", "date", "venue", "race_no", "race_name", "distance", "deadline"]
RACE_RESULT_COLS = ["weather", "wind_dir", "wind_speed", "wave", "technique"]


def connect(path):
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    return con


def _upsert(con, table, rows):
    if not rows:
        return
    cols = list(rows[0].keys())
    sql = (f"INSERT OR REPLACE INTO {table} ({','.join(cols)}) "
           f"VALUES ({','.join('?' * len(cols))})")
    con.executemany(sql, [[r[c] for c in cols] for r in rows])


def save_program(con, races, entries):
    for r in races:
        con.execute(
            "INSERT INTO races (race_id, date, venue, race_no, race_name, distance, deadline) "
            "VALUES (?,?,?,?,?,?,?) ON CONFLICT(race_id) DO UPDATE SET "
            "race_name=excluded.race_name, distance=excluded.distance, deadline=excluded.deadline",
            [r[c] for c in RACE_PROGRAM_COLS],
        )
    _upsert(con, "entries", entries)
    con.commit()


def save_result(con, races, results, payouts):
    for r in races:
        con.execute(
            "INSERT INTO races (race_id, date, venue, race_no, weather, wind_dir, wind_speed, wave, technique) "
            "VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(race_id) DO UPDATE SET "
            "weather=excluded.weather, wind_dir=excluded.wind_dir, wind_speed=excluded.wind_speed, "
            "wave=excluded.wave, technique=excluded.technique",
            [r["race_id"], r["date"], r["venue"], r["race_no"]] + [r[c] for c in RACE_RESULT_COLS],
        )
    _upsert(con, "results", results)
    _upsert(con, "payouts", payouts)
    con.commit()
