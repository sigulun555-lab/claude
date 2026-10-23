# 第1665回 通常toto（13試合・1X2方式、Claude側予測、2026-10-22追加）

`round1665_toto13_claude_predictions.json` は、第1665回の通常toto13試合（ホーム勝ち/引き分け/
アウェイ勝ちの1X2方式）のClaude側予測です。`toto claude sample round1664.json`（既存）と同じ
構造（schemaVersion/generatedBy/modelName/generatedAt/round/matchCount/warnings/predictions[]）
ですが、**modelNameとdataSourceは意図的に書き分けています**：round1664サンプルは「Claude調査に
よる手動リサーチ」ベースの別モデルでしたが、今回のround1665は、totoGOAL3アプリ（本番モデル）の
実コード（`predictScore()` / `calculateOutcomeProbabilitiesCore()`のV2＝Dixon-Coles低スコア補正＋
drawBoost込み / `poissonProbability()` / `teamDatabase`の該当20クラブのエントリ）を、アプリの
ソースから忠実に転記・再現して計算した実際の値です（アプリ自体は変更していません。外部で同一
ロジックを複製して実行したのみ）。手動リサーチの値ではないため、混同しないようにしてください。

- 対象：第1665回 通常toto、13試合（締切 2026-10-24T04:50:00Z）
  1. サンフレッチェ広島(home) vs 清水エスパルス(away)
  2. 鹿島アントラーズ(home) vs 柏レイソル(away)
  3. ヴィッセル神戸(home) vs FC町田ゼルビア(away)
  4. セレッソ大阪(home) vs ジェフユナイテッド千葉(away)
  5. FC東京(home) vs 水戸ホーリーホック(away)
  6. 東京ヴェルディ(home) vs アビスパ福岡(away)
  7. ガンバ大阪(home) vs 京都サンガF.C.(away)
  8. 名古屋グランパス(home) vs 横浜F・マリノス(away)
  9. 川崎フロンターレ(home) vs ファジアーノ岡山(away)
  10. 浦和レッズ(home) vs V・ファーレン長崎(away)
  11. ブラウブリッツ秋田(home) vs FC今治(away)
  12. サガン鳥栖(home) vs ヴァンラーレ八戸(away)
  13. カターレ富山(home) vs 北海道コンサドーレ札幌(away)

  1〜3試合目は、totoGOAL3の指定3試合（`round1665_totoGOAL3_claude_predictions.json`）と
  同一の組み合わせ・同一のホーム/アウェイです。toto公式サイト（store.toto-dream.com、
  holdCntId=1665）で確認済み。

- probabilitiesのキー規約：`{"1": ホーム勝ち, "0": 引き分け, "2": アウェイ勝ち}`
  （`toto-lab`リポジトリの既存1X2スキーマ・採点スクリプトと同じ規約。toto公式の投票表記
  「1＝ホーム勝/0＝引き分け/2＝アウェイ勝」に合わせている）。

- marketOdds（購入割合によるブレンド）：第1665回の該当13試合ペア分のエントリはアプリ側に
  存在しないため未使用（モデルの生の期待得点をそのまま使用。アプリの該当オブジェクトを
  grepして確認済み）。

- isCupRiskMatch：13試合すべて `home.league === away.league`、かつ`MANUAL_CUP_MATCHES`にも
  登録なしのため、全試合 `isCupMatch=false`（アプリのHTMLソースで直接確認済み）。

- 同じ内容を、Claude/ChatGPT比較基盤リポジトリ `sigulun555-lab/toto-lab` にも、既存の
  1X2用スキーマ（`schemas/prediction.schema.json`、変更なし）形式で保存済み
  （`predictions/round_1665_Claude.jsonl`、13件）。比較・採点はtoto-lab側で行う。
  このリポジトリ（`claude`）への保存は、ChatGPT側リポジトリとの直接比較に使っていた
  既存の`toto/`フォルダの運用パターン（round1664サンプルと同じ場所）に揃えるためのもの。
