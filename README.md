# tenhou-analytics

天鳳の対局ログ（mjlogファイル）を解析し、BigQuery上で自分の麻雀を分析するための環境。

## 概要

天鳳からダウンロードしたmjlogファイルをパース・構造化し、BigQueryにロードした上でdbtによるデータモデリングを行う。
最終的にはSQLでの分析やStreamlitでの可視化を目指す。

## アーキテクチャ

```
mjlogファイル → [Python Parser] → BigQuery raw tables → [dbt] → 分析用テーブル → [Streamlit]（将来）
```

### データパイプライン

1. **mjlog Parser**（Python）: gzip圧縮XMLをパースし構造化データに変換
2. **BigQuery Loader**（Python）: パース結果をBigQueryのrawテーブルにロード
3. **dbt**: rawテーブルからstaging → intermediate → martsへモデリング
4. **可視化**（将来）: Streamlit等でダッシュボード構築

### mjlogフォーマット

mjlogファイルはgzip圧縮されたXML。主要な要素:

| 要素 | 内容 |
|------|------|
| `<GO>` | ゲーム種別（四麻/三麻、東風/東南等） |
| `<UN>` | プレイヤー情報（名前、段位、レート） |
| `<INIT>` | 局の初期状態（配牌、点数、親、ドラ） |
| `<T>/<U>/<V>/<W>` | 各プレイヤー(0-3)のツモ |
| `<D>/<E>/<F>/<G>` | 各プレイヤー(0-3)の打牌 |
| `<N>` | 鳴き（ポン/チー/カン） |
| `<AGARI>` | 和了（役、点数、支払い） |
| `<RYUUKYOKU>` | 流局 |

牌IDは0-135の整数。`ID // 4` で牌種（0-33）に変換可能。

## ディレクトリ構成

```
tenhou-analytics/
├── pyproject.toml
├── data/                        # mjlogファイル（.gitignore済み）
├── src/
│   └── tenhou_analytics/
│       ├── parser/              # mjlog → 構造化データへのパース
│       └── loader/              # BigQueryへのロード
├── dbt/                         # dbtプロジェクト
│   └── models/
│       ├── staging/             # rawテーブルの型変換・リネーム
│       ├── intermediate/        # 局単位・巡目単位の中間テーブル
│       └── marts/               # 分析用の最終テーブル
├── streamlit/                   # 可視化（将来）
└── tests/
```

## セットアップ

```bash
# 依存関係のインストール
uv sync

# mjlogファイルをdata/に配置
# ファイル名例: 2026080814gm-0089-0000-fee5c4f5&tw=0.mjlog
```

## 使い方

### mjlogパーサー

```python
from tenhou_analytics.parser import parse_mjlog

game = parse_mjlog("data/2026080814gm-0089-0000-fee5c4f5&tw=0.mjlog")

# 対局情報
print(game.game_id)
print(game.players[game.my_seat].name)  # 自分のプレイヤー名
print(game.final_points)                # 最終ポイント

# 各局の結果
for r in game.rounds:
    print(f"局={r.round_number} 本場={r.honba} 結果={type(r.result).__name__}")
```

### BigQueryへのロード

```bash
# 全ファイルをロード（重複は自動スキップ）
uv run tenhou-load data/

# パースのみ（BigQueryにはロードしない）
uv run tenhou-load data/ --dry-run

# 個別ファイル指定も可
uv run tenhou-load data/2026080814gm-0089-0000-fee5c4f5\&tw=0.mjlog
```

### テスト

```bash
uv run pytest -v
```

## コスト

- **BigQuery**: 無料枠（10GBストレージ、1TBクエリ/月）で十分
- **dbt-core**: OSS版を使用（無料）
- **GCS**: 必要に応じて利用（無料枠5GB）

## 開発状況

- [x] mjlogパーサー実装
- [x] BigQueryローダー実装
- [ ] dbtプロジェクトセットアップ
- [ ] staging/intermediate/martsモデル作成
- [ ] Streamlit可視化
