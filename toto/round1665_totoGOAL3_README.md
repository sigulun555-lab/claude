# 第1665回 totoGOAL3（Claude側予測、2026-10-22追加）

`toto claude sample round1664.json`（既存）は通常toto（13試合・1X2方式）のサンプルでした。
今回追加した `round1665_totoGOAL3_claude_predictions.json` は、それとは**当たり方が異なる別商品**
totoGOAL3（指定3試合のみ・ホーム/アウェイそれぞれのチームの自チーム得点数0点/1点/2点/3点以上を
当てる方式）の予測です。probabilitiesのキーが`{"0","1","2","3"}`（4バケット）である点が、
1X2方式（`{"1","0","2"}`、3クラス）と異なります。

- 対象：第1665回 totoGOAL3、指定3試合（締切 2026-10-24T04:50:00Z）
  - ヴィッセル神戸(home) vs FC町田ゼルビア(away)
  - サンフレッチェ広島(home) vs 清水エスパルス(away)
  - 鹿島アントラーズ(home) vs 柏レイソル(away)
- 確率値：totoGOAL3アプリ（本番モデル）のpredictScore()内部で使われている
  calculateScoreProbabilities()・poissonProbability()・teamDatabaseの該当エントリを、
  アプリのソースから忠実に転記・再現して計算した実際の値（アプリ自体は変更していない）。
- 同じ内容を、Claude/ChatGPT比較基盤リポジトリ `sigulun555-lab/toto-lab` にも
  totoGOAL3専用スキーマ（`schemas/prediction_goal3.schema.json`）形式で保存済み
  （`predictions/round_1665_Claude_goal3.jsonl`）。比較・採点はtoto-lab側で行う。
  このリポジトリ（`claude`）への保存は、ChatGPT側リポジトリ（`sigulun555-lab/gpt`）との
  直接比較に使っていた既存の`toto/`フォルダの運用パターン（1X2用サンプルと同じ場所）に
  揃えるためのもの。
- matchNumber（1〜3）は、toto公式サイト（store.toto-dream.com、holdCntId=1665）の
  第1665回totoGOAL3対象試合ページで確認した表示順：
  1試合目=広島vs清水、2試合目=鹿島vs柏、3試合目=神戸vs町田（全試合10/24(土)開催）。
