#!/bin/bash
# dbt-codegenを使ってモデルのschema.ymlひな型を生成するスクリプト
# 使い方:
#   ./scripts/generate_schema.sh stg_games
#   ./scripts/generate_schema.sh fct_round_player_stats
#   ./scripts/generate_schema.sh --all  (全モデル)

set -euo pipefail

cd "$(dirname "$0")/.."

if [ "${1:-}" = "--all" ]; then
    # 全モデルを一括生成
    models=$(find models -name "*.sql" -exec basename {} .sql \; | sort)
    for model in $models; do
        echo "=== $model ==="
        uv run --group dbt dbt run-operation generate_model_yaml \
            --args "{\"model_names\": [\"$model\"]}" \
            --profiles-dir . 2>&1 | grep -v "^\[0m"
        echo ""
    done
elif [ -n "${1:-}" ]; then
    # 単一モデル
    echo "=== $1 ==="
    uv run --group dbt dbt run-operation generate_model_yaml \
        --args "{\"model_names\": [\"$1\"]}" \
        --profiles-dir . 2>&1 | grep -v "^\[0m"
else
    echo "使い方: $0 <model_name> | --all"
    echo "例: $0 stg_games"
    echo "例: $0 --all"
    exit 1
fi
