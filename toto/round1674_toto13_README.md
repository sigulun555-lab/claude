# 第1674回 通常toto（13試合・1X2方式、Claude側予測、2026-11-24 締切前日自動配信）

`round1674_toto13_claude_predictions.json` は、第1674回の通常toto13試合（ホーム勝ち/引き分け/
アウェイ勝ちの1X2方式）のClaude側予測です。round1668・round1665と同じ構造・同じ生成方法で、
totoGOALアプリ（本番モデル）の実コード（`predictScore()` / `calculateOutcomeProbabilitiesCore()`の
V2＝Dixon-Coles低スコア補正＋drawBoost込み / `poissonProbability()` / `teamDatabase`の該当各クラブの
エントリ）を、アプリのソースから忠実に転記・再現して計算した実際の値です（アプリ自体のロジックは
変更していません。外部で同一ロジックを複製して実行したのみ）。

- 対象：第1674回 通常toto、13試合（開催 2026-11-25(水)、締切 2026-11-25T09:50:00Z＝JST 18:50・ネット決済）
  1. ジェフユナイテッド千葉(home) vs 名古屋グランパス(away)
  2. ファジアーノ岡山(home) vs 清水エスパルス(away)
  3. V・ファーレン長崎(home) vs 川崎フロンターレ(away)
  4. 水戸ホーリーホック(home) vs 東京ヴェルディ(away)
  5. アビスパ福岡(home) vs 横浜F・マリノス(away)
  6. FC東京(home) vs サンフレッチェ広島(away)
  7. 浦和レッズ(home) vs セレッソ大阪(away)
  8. 北海道コンサドーレ札幌(home) vs 藤枝MYFC(away)
  9. モンテディオ山形(home) vs ジュビロ磐田(away)
  10. サガン鳥栖(home) vs 大分トリニータ(away)
  11. いわきFC(home) vs カターレ富山(away)
  12. 横浜FC(home) vs ベガルタ仙台(away)
  13. RB大宮アルディージャ(home) vs 徳島ヴォルティス(away)

  mini toto A組＝試合1〜5、B組＝試合6〜10（試合11〜13は対象外）。
  totoGOAL3の指定3試合（`round1674_totoGOAL3_claude_predictions.json`）は、このうち
  1試合目・2試合目・3試合目（千葉×名古屋／岡山×清水／長崎×川崎Ｆ）と同一の組み合わせです。
  いずれも toto公式サイト（store.toto-dream.com、holdCntId=1674）で確認済み。

- probabilitiesのキー規約：`{"1": ホーム勝ち, "0": 引き分け, "2": アウェイ勝ち}`
  （`toto-lab`リポジトリの既存1X2スキーマ・採点スクリプトと同じ規約）。

- アプリ内部のroundsData（第1674回）には、本タスク実行時点で `injuryPresets` の登録が
  無かったため（別タスク「totoGOAL3 新開催回チェック＆自動更新」が対戦カードのみ反映し、
  負傷情報は未登録の状態）、`calculateLiveOutcome` による怪我人補正は適用されていません
  （補正対象0名のため、`predictScore()` の生の出力と同じ値になります）。負傷・出場停止情報の
  追加調査はこのタスクの担当外です。

- 同じ内容を、Claude/ChatGPT比較基盤リポジトリ `sigulun555-lab/toto-lab` にも、既存の
  1X2用スキーマ形式で保存済み（`predictions/round_1674_Claude.jsonl`、13件）。
  比較・採点はtoto-lab側で行う。このリポジトリ（`claude`）への保存は、ChatGPT側リポジトリ
  との直接比較に使っていた既存の`toto/`フォルダの運用パターンに揃えるためのもの。

- 本ファイルは、締切前日22時頃に実行される自動配信タスクによって生成されました
  （売上・投票率などの確定後の情報は一切使用せず、締切前の時点での予測を確定・保存したものです）。
