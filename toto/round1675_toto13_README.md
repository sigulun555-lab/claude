# 第1675回 通常toto（13試合・1X2方式、Claude側予測、2026-11-27 締切前日自動配信）

`round1675_toto13_claude_predictions.json` は、第1675回の通常toto13試合（ホーム勝ち/引き分け/
アウェイ勝ちの1X2方式）のClaude側予測です。round1674・round1668・round1665と同じ構造・同じ生成方法で、
totoGOALアプリ（本番モデル）の実コード（`predictScore()` / `calculateOutcomeProbabilitiesCore()`の
V2＝Dixon-Coles低スコア補正＋drawBoost込み / `poissonProbability()` / `teamDatabase`の該当各クラブの
エントリ）を、アプリのソースから忠実に転記・再現して計算した実際の値です（アプリ自体のロジックは
変更していません。外部で同一ロジックを複製して実行したのみ）。

- 対象：第1675回 通常toto、13試合（開催 2026-11-28(土)・2026-11-29(日)、締切 2026-11-28T04:50:00Z＝JST 13:50・ネット決済）
  1. 京都サンガ(home) vs セレッソ大阪(away)
  2. 柏レイソル(home) vs サンフレッチェ広島(away)
  3. 横浜F・マリノス(home) vs FC東京(away)
  4. 水戸ホーリーホック(home) vs V・ファーレン長崎(away)
  5. 名古屋グランパス(home) vs アビスパ福岡(away)
  6. 清水エスパルス(home) vs 浦和レッズ(away)
  7. 鹿島アントラーズ(home) vs ファジアーノ岡山(away)
  8. ヴィッセル神戸(home) vs ジェフユナイテッド千葉(away)
  9. FC町田ゼルビア(home) vs 東京ヴェルディ(away)
  10. 川崎フロンターレ(home) vs ガンバ大阪(away)
  11. ヴァンラーレ八戸(home) vs 藤枝MYFC(away)
  12. テゲバジャーロ宮崎(home) vs サガン鳥栖(away)
  13. ベガルタ仙台(home) vs モンテディオ山形(away)

  mini toto A組＝試合1〜5、B組＝試合6〜10（試合11〜13は対象外）。
  totoGOAL3の指定3試合（`round1675_totoGOAL3_claude_predictions.json`）は、このうち
  1試合目・3試合目・5試合目（京都×Ｃ大阪／横浜FM×FC東京／名古屋×福岡）と同一の組み合わせです。
  いずれも toto公式サイト（store.toto-dream.com、holdCntId=1675）・楽天toto
  （toto.rakuten.co.jp/toto/schedule/1675/）で確認済み。

- probabilitiesのキー規約：`{"1": ホーム勝ち, "0": 引き分け, "2": アウェイ勝ち}`
  （`toto-lab`リポジトリの既存1X2スキーマ・採点スクリプトと同じ規約）。

- アプリ内部のroundsData（第1675回）には、本タスク実行時点で `injuryPresets` の登録が
  無かったため（別タスク「totoGOAL3 新開催回チェック＆自動更新」が対戦カードのみ反映し、
  負傷情報は未登録の状態）、怪我人補正は適用されていません（補正対象0名のため、
  `predictScore()` の生の出力と同じ値になります）。負傷・出場停止情報の
  追加調査はこのタスクの担当外です。

- 同じ内容を、Claude/ChatGPT比較基盤リポジトリ `sigulun555-lab/toto-lab` にも、既存の
  1X2用スキーマ形式で保存済み（`predictions/round_1675_Claude.jsonl`、13件）。
  比較・採点はtoto-lab側で行う。このリポジトリ（`claude`）への保存は、ChatGPT側リポジトリ
  との直接比較に使っていた既存の`toto/`フォルダの運用パターンに揃えるためのもの。

- 本ファイルは、締切前日22時頃に実行される自動配信タスクによって生成されました
  （売上・投票率などの確定後の情報は一切使用せず、締切前の時点での予測を確定・保存したものです）。
