ペーパートレード用の固定モデル。
学習データ: 2025-10-01 〜 2026-10-05 (56,412レース)
2着・3着の補正: GAMMA=0.672, DELTA=0.476 (boatrace/model.py)

model_morning.txt: 朝の予想表用。展示タイム・風・波を使わない (同じ期間で学習)
model_check.txt: 直前チェック用。風向きだけ使わない (同じ期間で学習)

[2026-10-14 更新] model_check.txt / model_morning.txt を作り直し (2026-10-13 までで学習)
- 特徴量を追加: 直近のスタートタイミング(ST)、フライング率、進入コースの傾向、その場での勝率
- model_check.txt は直前チェックで公式オッズと合成して使う (boatrace/market.py)
- model.txt は記録テストの固定モデルなので変更しない
