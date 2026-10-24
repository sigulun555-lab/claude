# win5-lab

JRAのWIN5（指定5レースの1着をすべて当てる馬券）の買い目づくりと、結果の記録（ペーパー検証）をする場所です。
`sigulun555-lab/claude` の `keiba-prediction` ブランチにある競馬予想プロンプトの、WIN5の部分を移植しました。

| ファイル | 役割 |
|---|---|
| `prompt.md` | WIN5用のプロンプト（移植元のSTEP18などを、WIN5専用に書き直したもの） |
| `win5.py` | 予算内で的中確率が最大になる買い方を出す／結果を記録する |
| `examples/sample.json` | 入力の見本（架空のデータ） |
| `logs/` | 保存した買い目（`<日付>_plan.json`）と累計（`summary.csv`） |
| `tests/` | `win5.py` のテスト |

## 使い方

Python 3 だけで動きます（追加のインストールは不要です）。

```sh
# 1) 買い方を出す（予算3,000円の例）
python3 win5.py plan examples/sample.json --budget 3000

# 2) 記録として残す
python3 win5.py plan my_win5.json --budget 3000 --save

# 3) 結果が出たら確かめる（5レースの勝ち馬を順に。的中したら払戻も）
python3 win5.py settle logs/2026-10-25_plan.json 3,5,1,12,7 --payout 1234500
```

## 入力ファイルの書き方

```json
{
  "date": "2026-10-25",
  "sales": 1500000000,
  "carryover": 200000000,
  "legs": [
    {"race": "東京10R", "horses": [
      {"no": 1, "name": "馬名", "odds": 2.1},
      {"no": 2, "name": "馬名", "odds": 4.5, "p": 0.25},
      {"no": 3, "name": "馬名", "odds": 9.9, "scratched": true}
    ]}
  ]
}
```

- `legs` はWIN5の対象5レースを順番どおりに書きます
- `odds` は単勝オッズ。勝率は「1÷オッズ」をレース内で合計1に直して計算します
- 自分の見立てを入れたいときは、そのレースの**全馬**に `p`（勝率）を書きます（合計は自動で1に直します）
- 出走取消は `"scratched": true`
- `sales`（売上の見込み）と `carryover` は任意です。書くとキャリーオーバー込みの理論上の還元率が出ます

## 移植元からの変更点
- 移植元の「馬連が当たればWIN5も当選する」という記述は誤り（移植元 `keiba/improvements.md` 改良案10）なので、
  WIN5では各レースの**勝率だけ**を使うように直しました
- WIN5はJRAだけの馬券なので、地方競馬・ばんえい専用の部分（STEP0a〜0dなど）は移していません。
  1レースずつの分析は、移植元の `keiba/prompt.md` STEP1〜17・19 をそのまま使います

## テスト
```sh
python3 -m unittest discover -s tests -v
```

※ お金は賭けない記録上の検証です。実際に購入するかどうかはご自身で判断してください。
