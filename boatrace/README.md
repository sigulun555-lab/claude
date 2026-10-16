# 競艇予想アプリ

設計した10フェーズのうち、**Phase 1 (データ基盤)** と **Phase 2 (ベースライン評価)** を実装しています。

## セットアップ

```bash
cd boatrace
pip install -r requirements.txt
```

## 使い方

```bash
# 公式サイトから過去の番組表・競走成績をダウンロードしてDBに保存
#   (1日あたり2ファイル、リクエストの間隔は1秒)
python -m boatrace.cli load 2025-10-01 2025-10-31

# 手元に展開済みの TXT (BYYMMDD.TXT / KYYMMDD.TXT) がある場合
python -m boatrace.cli load-text path/to/B251001.TXT path/to/K251001.TXT

# コース別の1着率と、単純予想の的中率・回収率を確認
python -m boatrace.cli baseline            # 全場
python -m boatrace.cli baseline --venue 24 # 大村だけ
```

DBは `data/boatrace.sqlite` に作られます (git管理外)。

## データの出どころ

BOAT RACE 公式のダウンロードページ (`www1.mbrace.or.jp/od2/`) にある
LZH 形式のファイルを使います。

- `B` = 番組表: 枠番、登番、級別、全国/当地勝率、モーター・ボートの2連率など
- `K` = 競走成績: 着順、進入コース、ST、展示タイム、天候・風・波、決まり手、全券種の払戻

公式サイトの利用規約を守り、アクセスの間隔を空けて使ってください。

## テーブル

| テーブル | 中身 |
|---|---|
| `races` | レース単位 (場、R番号、距離、締切、天候、風、波、決まり手) |
| `entries` | 出走表 (選手・モーター・ボートの成績) |
| `results` | 成績 (着順、進入、ST、展示タイム) |
| `payouts` | 払戻 (単勝〜3連複、人気) |

`race_id` は `YYYYMMDD_場コード_R番号` (例: `20261007_24_01`) です。

## テスト

```bash
python -m pytest -q
```

`tests/fixtures/` のサンプルは公式ファイルの書式をまねて作った架空データです。
本物のファイルで書式のずれが見つかったら、パーサの正規表現を調整します。

## 次のフェーズ

3. 特徴量作成 → 4. LightGBM で着順確率 → 5. 券種ごとの確率へ変換 →
6. 期待値計算 → 7. バックテスト → 8. 直前情報のリアルタイム取得 → 9. UI → 10. 運用
