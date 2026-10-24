import csv
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from itertools import combinations, product

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import win5  # noqa: E402

SAMPLE = os.path.join(ROOT, "examples", "sample.json")


def leg(odds):
    return {"horses": [{"no": i, "odds": o} for i, o in enumerate(odds, 1)]}


class WinP(unittest.TestCase):
    def test_market_normalized(self):
        p = win5.win_p(leg([2.0, 4.0, 4.0])["horses"])
        self.assertAlmostEqual(sum(p.values()), 1.0)
        self.assertAlmostEqual(p[1], 0.5)

    def test_own_p_used(self):
        p = win5.win_p([{"no": 1, "odds": 2.0, "p": 1}, {"no": 2, "odds": 9.0, "p": 3}])
        self.assertAlmostEqual(p[2], 0.75)


class Plan(unittest.TestCase):
    def setUp(self):
        self.legs = [leg([1.5, 5, 10, 20]), leg([3, 3.2, 3.5, 8]), leg([2, 4, 6]),
                     leg([4, 4.5, 5, 6, 9]), leg([1.8, 3, 12])]

    def test_within_budget_and_matches_brute_force(self):
        best = win5.plan(self.legs, 1200)[0]
        self.assertLessEqual(best["cost"], 1200)
        # 馬の選び方を全通り（各レースの空でない部分集合）調べた最大と一致する
        subsets = []
        for l in self.legs:
            p = list(win5.win_p(l["horses"]).values())
            subsets.append([(len(c), sum(c)) for n in range(1, len(p) + 1) for c in combinations(p, n)])
        top = 0.0
        for choice in product(*subsets):
            pts, h = 1, 1.0
            for k, s in choice:
                pts *= k
                h *= s
            if pts * 100 <= 1200:
                top = max(top, h)
        self.assertAlmostEqual(best["hit"], top)

    def test_points_and_picks(self):
        best = win5.plan(self.legs, 100)[0]
        self.assertEqual(best["points"], 1)
        self.assertEqual(best["picks"], [[1], [1], [1], [1], [1]])

    def test_budget_too_small(self):
        with self.assertRaises(SystemExit):
            win5.plan(self.legs, 50)


class Theory(unittest.TestCase):
    def test_break_even_at_30_percent(self):
        self.assertAlmostEqual(win5.theory_return(1000, 300), 1.0)
        self.assertAlmostEqual(win5.theory_return(1000, 0), 0.7)
        self.assertIsNone(win5.theory_return(None, 0))


class Load(unittest.TestCase):
    def test_sample_scratched_removed(self):
        d = win5.load(SAMPLE)
        self.assertEqual(len(d["legs"][1]["horses"]), 11)

    def test_needs_five_legs(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "four.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"legs": [leg([2, 3])] * 4}, f)
            with self.assertRaises(SystemExit):
                win5.load(path)


class Cli(unittest.TestCase):
    def test_plan_save_and_settle(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = win5.LOG
            win5.LOG = tmp
            try:
                with redirect_stdout(io.StringIO()) as out:
                    win5.main(["plan", SAMPLE, "--budget", "3000", "--save"])
                self.assertIn("おすすめ", out.getvalue())
                path = os.path.join(tmp, "2026-01-01_plan.json")
                with open(path, encoding="utf-8") as f:
                    rec = json.load(f)
                winners = ",".join(str(p[0]) for p in rec["plan"]["picks"])
                with redirect_stdout(io.StringIO()) as out:
                    win5.main(["settle", path, winners, "--payout", "50000"])
                self.assertIn("的中", out.getvalue())
                rows = list(csv.reader(open(os.path.join(tmp, "summary.csv"), encoding="utf-8")))
                self.assertEqual(rows[1][5], "○")
                self.assertEqual(rows[1][6], "50000")
                # 同じ日をやり直すと上書きされ、行が増えない
                with redirect_stdout(io.StringIO()):
                    win5.main(["settle", path, "99,99,99,99,99"])
                rows = list(csv.reader(open(os.path.join(tmp, "summary.csv"), encoding="utf-8")))
                self.assertEqual(len(rows), 2)
                self.assertEqual(rows[1][5], "×")
            finally:
                win5.LOG = old


if __name__ == "__main__":
    unittest.main()
