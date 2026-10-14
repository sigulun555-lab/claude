from boatrace.sheet import to_markdown


def test_markdown_marks_top_pick():
    data = {"date": "2026-10-14", "venues": [{"code": 24, "name": "大村", "races": [
        {"no": 1, "deadline": "15:20", "picks": [
            {"boat": 1, "name": "大村太郎", "grade": "A1", "p": 0.5, "need": 2.4, "top": True},
            {"boat": 3, "name": "長崎三郎", "grade": "B1", "p": 0.2, "need": 6.0, "top": False}]}]}]}
    text = to_markdown(data)
    assert "大村太郎 〔予想1位〕" in text
    assert "長崎三郎 〔予想1位〕" not in text


def test_candidate_mark_on_venue_and_race():
    def race(no, need):
        return {"no": no, "deadline": "15:00", "picks": [
            {"boat": 1, "name": f"選手{no}", "grade": "A1", "p": 0.4, "need": need, "top": True}]}
    data = {"date": "2026-10-14", "venues": [
        {"code": 1, "name": "桐生", "races": [race(1, 1.6), race(2, 3.1)]},
        {"code": 2, "name": "戸田", "races": [race(1, 1.5), race(2, 2.4)]}]}
    text = to_markdown(data)
    assert "## 桐生 🔴1" in text and "## 戸田\n" in text
    assert "| 2 🔴 |" in text and "| 1 🔴 |" not in text
