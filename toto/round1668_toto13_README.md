# 第1668回 通常toto（13試合・1X2方式、Claude側予測、2026-10-30追加）

`round1668_toto13_claude_predictions.json` は、第1668回の通常toto13試合（ホーム勝ち/引き分け/
アウェイ勝ちの1X2方式）のClaude側予測です。round1665と同じ構造・同じ生成方法で、totoGOAL3
アプリ（本番モデル）の実コード（`predictScore()` / `calculateOutcomeProbabilitiesCore()`の
V2＝Dixon-Coles低スコア補正＋drawBoost込み / `poissonProbability()` / `teamDatabase`の該当
26クラブのエントリ）を、アプリのソースから忠実に転記・再現して計算した実際の値です
（アプリ自体のロジックは変更していません。外部で同一ロジックを複製して実行したのみ）。

**本来は締切前日22時の自動配信タスクが担当する内容ですが、同日0時台に実行されるはずの
「totoGOAL3 新開催回チェック＆自動更新」タスクがABANDONED（未完了）となり、アプリ側に
第1668回の対戦カードが反映されていなかったため、22時の配信タスクでは通常toto13・
mini toto A/Bの予想が生成できませんでした。そのため、ユーザー依頼によりこちらで手動で
アプリに第1668回の対戦カード・mini toto A/Bを反映した上で、同じ`predictScore()`を呼び出して
計算・保存したものです。**

- 対象：第1668回 通常toto、13試合（締切 2026-10-31T04:50:00Z＝JST 13:50）
  1. ファジアーノ岡山(home) vs FC東京(away)
  2. 水戸ホーリーホック(home) vs サンフレッチェ広島(away)
  3. ヴィッセル神戸(home) vs 名古屋グランパス(away)
  4. 鹿島アントラーズ(home) vs セレッソ大阪(away)
  5. 柏レイソル(home) vs 浦和レッズ(away)
  6. 京都サンガF.C.(home) vs 清水エスパルス(away)
  7. ジェフユナイテッド千葉(home) vs アビスパ福岡(away)
  8. V・ファーレン長崎(home) vs 東京ヴェルディ(away)
  9. FC町田ゼルビア(home) vs ガンバ大阪(away)
  10. 横浜F・マリノス(home) vs 川崎フロンターレ(away)
  11. ベガルタ仙台(home) vs RB大宮アルディージャ(away)
  12. アルビレックス新潟(home) vs カターレ富山(away)
  13. テゲバジャーロ宮崎(home) vs 大分トリニータ(away)

  mini toto A組＝試合1〜5、B組＝試合6〜10（試合11〜13は対象外）。
  totoGOAL3の指定3試合（`round1668_totoGOAL3_claude_predictions.json`）は、このうち
  1試合目・3試合目・5試合目（岡山×FC東京／神戸×名古屋／柏×浦和）と同一の組み合わせです。
  いずれも toto公式投票ページ（store.toto-dream.com、holdCntId=1668）で確認済み。

- probabilitiesのキー規約：`{"1": ホーム勝ち, "0": 引き分け, "2": アウェイ勝ち}`
  （`toto-lab`リポジトリの既存1X2スキーマ・採点スクリプトと同じ規約）。

- marketOdds（購入割合によるブレンド）：第1668回の該当13試合ペア分のエントリはアプリ側に
  存在しないため未使用（モデルの生の期待得点をそのまま使用）。

- 同じ内容を、Claude/ChatGPT比較基盤リポジトリ `sigulun555-lab/toto-lab` にも、既存の
  1X2用スキーマ形式で保存済み（`predictions/round_1668_Claude.jsonl`、13件）。
  比較・採点はtoto-lab側で行う。このリポジトリ（`claude`）への保存は、ChatGPT側リポジトリ
  との直接比較に使っていた既存の`toto/`フォルダの運用パターンに揃えるためのもの。
