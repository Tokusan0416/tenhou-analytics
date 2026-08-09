"""BigQueryへのデータロード。

パース済みのGameオブジェクトをBigQueryのrawテーブルに投入する。
"""

from __future__ import annotations

import os
import time

from google.cloud import bigquery

from tenhou_analytics.parser.mjlog import (
    AgariResult,
    Game,
    RyuukyokuResult,
)

DEFAULT_PROJECT = os.environ.get("GCP_PROJECT_ID", "invertible-vine-477701-j8")
DEFAULT_DATASET = "tenhou_raw"


def _get_table_id(project: str, dataset: str, table: str) -> str:
    return f"{project}.{dataset}.{table}"


def _game_to_raw_games_row(game: Game) -> dict:
    """Gameオブジェクトをraw_gamesテーブルの行に変換。"""
    return {
        "game_id": game.game_id,
        "game_date": game.game_date.isoformat() if game.game_date else None,
        "my_seat": game.my_seat,
        "is_sanma": game.game_type.get("is_sanma", False),
        "is_tonnansen": game.game_type.get("is_tonnansen", False),
        "is_soku": game.game_type.get("is_soku", False),
        "is_no_red": game.game_type.get("is_no_red", False),
        "lobby": game.game_type.get("lobby", ""),
        "player0_name": game.players[0].name if len(game.players) > 0 else "",
        "player1_name": game.players[1].name if len(game.players) > 1 else "",
        "player2_name": game.players[2].name if len(game.players) > 2 else "",
        "player3_name": game.players[3].name if len(game.players) > 3 else "",
        "player0_dan": game.players[0].dan if len(game.players) > 0 else 0,
        "player1_dan": game.players[1].dan if len(game.players) > 1 else 0,
        "player2_dan": game.players[2].dan if len(game.players) > 2 else 0,
        "player3_dan": game.players[3].dan if len(game.players) > 3 else 0,
        "player0_rate": game.players[0].rate if len(game.players) > 0 else 0.0,
        "player1_rate": game.players[1].rate if len(game.players) > 1 else 0.0,
        "player2_rate": game.players[2].rate if len(game.players) > 2 else 0.0,
        "player3_rate": game.players[3].rate if len(game.players) > 3 else 0.0,
        "final_score0": game.final_scores[0] if len(game.final_scores) > 0 else 0,
        "final_score1": game.final_scores[1] if len(game.final_scores) > 1 else 0,
        "final_score2": game.final_scores[2] if len(game.final_scores) > 2 else 0,
        "final_score3": game.final_scores[3] if len(game.final_scores) > 3 else 0,
        "final_point0": game.final_points[0] if len(game.final_points) > 0 else 0.0,
        "final_point1": game.final_points[1] if len(game.final_points) > 1 else 0.0,
        "final_point2": game.final_points[2] if len(game.final_points) > 2 else 0.0,
        "final_point3": game.final_points[3] if len(game.final_points) > 3 else 0.0,
        "num_rounds": len(game.rounds),
    }


def _game_to_raw_rounds_rows(game: Game) -> list[dict]:
    """Gameオブジェクトをraw_roundsテーブルの行リストに変換。"""
    rows = []
    for i, r in enumerate(game.rounds):
        row = {
            "game_id": game.game_id,
            "round_index": i,
            "round_number": r.round_number,
            "honba": r.honba,
            "riichi_sticks": r.riichi_sticks,
            "dora_indicator": r.dora_indicator,
            "dealer": r.dealer,
            "starting_score0": r.starting_scores[0] if len(r.starting_scores) > 0 else 0,
            "starting_score1": r.starting_scores[1] if len(r.starting_scores) > 1 else 0,
            "starting_score2": r.starting_scores[2] if len(r.starting_scores) > 2 else 0,
            "starting_score3": r.starting_scores[3] if len(r.starting_scores) > 3 else 0,
            "hand0": ",".join(r.hands.get(0, [])),
            "hand1": ",".join(r.hands.get(1, [])),
            "hand2": ",".join(r.hands.get(2, [])),
            "hand3": ",".join(r.hands.get(3, [])),
            "reach_players": ",".join(str(p) for p in r.reach_players),
            "result_type": _get_result_type(r.result),
        }

        if isinstance(r.result, AgariResult):
            row.update({
                "agari_winner": r.result.winner,
                "agari_from_who": r.result.from_who,
                "agari_is_tsumo": r.result.is_tsumo,
                "agari_ten": r.result.ten,
                "agari_fu": r.result.fu,
                "agari_han": r.result.han,
                "agari_yaku": ",".join(f"{y.name}:{y.han}" for y in r.result.yaku),
                "agari_winning_tile": r.result.winning_tile,
                "agari_dora": ",".join(r.result.dora),
                "agari_ura_dora": ",".join(r.result.ura_dora),
                "agari_dora_count": sum(y.han for y in r.result.yaku if y.id == 52),
                "agari_ura_dora_count": sum(y.han for y in r.result.yaku if y.id == 53),
                "agari_aka_dora_count": sum(y.han for y in r.result.yaku if y.id == 54),
                "score_change0": r.result.score_changes[0] if len(r.result.score_changes) > 0 else 0,
                "score_change1": r.result.score_changes[1] if len(r.result.score_changes) > 1 else 0,
                "score_change2": r.result.score_changes[2] if len(r.result.score_changes) > 2 else 0,
                "score_change3": r.result.score_changes[3] if len(r.result.score_changes) > 3 else 0,
                "ryuukyoku_reason": None,
                "tenpai_players": None,
            })
        elif isinstance(r.result, RyuukyokuResult):
            row.update({
                "agari_winner": None,
                "agari_from_who": None,
                "agari_is_tsumo": None,
                "agari_ten": None,
                "agari_fu": None,
                "agari_han": None,
                "agari_yaku": None,
                "agari_winning_tile": None,
                "agari_dora": None,
                "agari_ura_dora": None,
                "agari_dora_count": None,
                "agari_ura_dora_count": None,
                "agari_aka_dora_count": None,
                "score_change0": r.result.score_changes[0] if len(r.result.score_changes) > 0 else 0,
                "score_change1": r.result.score_changes[1] if len(r.result.score_changes) > 1 else 0,
                "score_change2": r.result.score_changes[2] if len(r.result.score_changes) > 2 else 0,
                "score_change3": r.result.score_changes[3] if len(r.result.score_changes) > 3 else 0,
                "ryuukyoku_reason": r.result.reason,
                "tenpai_players": ",".join(str(p) for p in r.result.tenpai_players),
            })

        rows.append(row)
    return rows


def _game_to_raw_actions_rows(game: Game) -> list[dict]:
    """Gameオブジェクトをraw_actionsテーブルの行リストに変換。"""
    rows = []
    for round_idx, r in enumerate(game.rounds):
        for action_idx, a in enumerate(r.actions):
            rows.append({
                "game_id": game.game_id,
                "round_index": round_idx,
                "action_index": action_idx,
                "action_type": a.type,
                "player": a.player,
                "tile": a.tile,
                "turn": a.turn,
            })
    return rows


def _get_result_type(result: AgariResult | RyuukyokuResult | None) -> str:
    if isinstance(result, AgariResult):
        return "agari"
    if isinstance(result, RyuukyokuResult):
        return "ryuukyoku"
    return "unknown"


RAW_GAMES_SCHEMA = [
    bigquery.SchemaField("game_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("game_date", "TIMESTAMP"),
    bigquery.SchemaField("my_seat", "INTEGER"),
    bigquery.SchemaField("is_sanma", "BOOLEAN"),
    bigquery.SchemaField("is_tonnansen", "BOOLEAN"),
    bigquery.SchemaField("is_soku", "BOOLEAN"),
    bigquery.SchemaField("is_no_red", "BOOLEAN"),
    bigquery.SchemaField("lobby", "STRING"),
    bigquery.SchemaField("player0_name", "STRING"),
    bigquery.SchemaField("player1_name", "STRING"),
    bigquery.SchemaField("player2_name", "STRING"),
    bigquery.SchemaField("player3_name", "STRING"),
    bigquery.SchemaField("player0_dan", "INTEGER"),
    bigquery.SchemaField("player1_dan", "INTEGER"),
    bigquery.SchemaField("player2_dan", "INTEGER"),
    bigquery.SchemaField("player3_dan", "INTEGER"),
    bigquery.SchemaField("player0_rate", "FLOAT"),
    bigquery.SchemaField("player1_rate", "FLOAT"),
    bigquery.SchemaField("player2_rate", "FLOAT"),
    bigquery.SchemaField("player3_rate", "FLOAT"),
    bigquery.SchemaField("final_score0", "INTEGER"),
    bigquery.SchemaField("final_score1", "INTEGER"),
    bigquery.SchemaField("final_score2", "INTEGER"),
    bigquery.SchemaField("final_score3", "INTEGER"),
    bigquery.SchemaField("final_point0", "FLOAT"),
    bigquery.SchemaField("final_point1", "FLOAT"),
    bigquery.SchemaField("final_point2", "FLOAT"),
    bigquery.SchemaField("final_point3", "FLOAT"),
    bigquery.SchemaField("num_rounds", "INTEGER"),
]

RAW_ROUNDS_SCHEMA = [
    bigquery.SchemaField("game_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("round_index", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("round_number", "INTEGER"),
    bigquery.SchemaField("honba", "INTEGER"),
    bigquery.SchemaField("riichi_sticks", "INTEGER"),
    bigquery.SchemaField("dora_indicator", "STRING"),
    bigquery.SchemaField("dealer", "INTEGER"),
    bigquery.SchemaField("starting_score0", "INTEGER"),
    bigquery.SchemaField("starting_score1", "INTEGER"),
    bigquery.SchemaField("starting_score2", "INTEGER"),
    bigquery.SchemaField("starting_score3", "INTEGER"),
    bigquery.SchemaField("hand0", "STRING"),
    bigquery.SchemaField("hand1", "STRING"),
    bigquery.SchemaField("hand2", "STRING"),
    bigquery.SchemaField("hand3", "STRING"),
    bigquery.SchemaField("reach_players", "STRING"),
    bigquery.SchemaField("result_type", "STRING"),
    bigquery.SchemaField("agari_winner", "INTEGER"),
    bigquery.SchemaField("agari_from_who", "INTEGER"),
    bigquery.SchemaField("agari_is_tsumo", "BOOLEAN"),
    bigquery.SchemaField("agari_ten", "INTEGER"),
    bigquery.SchemaField("agari_fu", "INTEGER"),
    bigquery.SchemaField("agari_han", "INTEGER"),
    bigquery.SchemaField("agari_yaku", "STRING"),
    bigquery.SchemaField("agari_winning_tile", "STRING"),
    bigquery.SchemaField("agari_dora", "STRING"),
    bigquery.SchemaField("agari_ura_dora", "STRING"),
    bigquery.SchemaField("agari_dora_count", "INTEGER"),
    bigquery.SchemaField("agari_ura_dora_count", "INTEGER"),
    bigquery.SchemaField("agari_aka_dora_count", "INTEGER"),
    bigquery.SchemaField("score_change0", "INTEGER"),
    bigquery.SchemaField("score_change1", "INTEGER"),
    bigquery.SchemaField("score_change2", "INTEGER"),
    bigquery.SchemaField("score_change3", "INTEGER"),
    bigquery.SchemaField("ryuukyoku_reason", "STRING"),
    bigquery.SchemaField("tenpai_players", "STRING"),
]

RAW_ACTIONS_SCHEMA = [
    bigquery.SchemaField("game_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("round_index", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("action_index", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("action_type", "STRING"),
    bigquery.SchemaField("player", "INTEGER"),
    bigquery.SchemaField("tile", "STRING"),
    bigquery.SchemaField("turn", "INTEGER"),
]


def _ensure_table(
    client: bigquery.Client,
    table_id: str,
    schema: list[bigquery.SchemaField],
) -> bigquery.Table:
    """テーブルが存在しなければ作成する。"""
    table = bigquery.Table(table_id, schema=schema)
    return client.create_table(table, exists_ok=True)


def load_game_to_bigquery(
    game: Game,
    *,
    project: str = DEFAULT_PROJECT,
    dataset: str = DEFAULT_DATASET,
) -> dict[str, int]:
    """GameオブジェクトをBigQueryにロードする。

    Args:
        game: パース済みの対局データ
        project: GCPプロジェクトID
        dataset: BigQueryデータセット名

    Returns:
        各テーブルに挿入した行数の辞書
    """
    client = bigquery.Client(project=project)

    # テーブル作成（存在しなければ）
    games_table_id = _get_table_id(project, dataset, "raw_games")
    rounds_table_id = _get_table_id(project, dataset, "raw_rounds")
    actions_table_id = _get_table_id(project, dataset, "raw_actions")

    _ensure_table(client, games_table_id, RAW_GAMES_SCHEMA)
    _ensure_table(client, rounds_table_id, RAW_ROUNDS_SCHEMA)
    _ensure_table(client, actions_table_id, RAW_ACTIONS_SCHEMA)

    # データ変換
    games_rows = [_game_to_raw_games_row(game)]
    rounds_rows = _game_to_raw_rounds_rows(game)
    actions_rows = _game_to_raw_actions_rows(game)

    # 重複チェック: 同一game_idが既に存在する場合はスキップ
    try:
        query = f"""
            SELECT COUNT(*) as cnt
            FROM `{games_table_id}`
            WHERE game_id = @game_id
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("game_id", "STRING", game.game_id),
            ]
        )
        result = client.query(query, job_config=job_config).result()
        count = list(result)[0].cnt
    except Exception:
        count = 0
    if count > 0:
        return {"raw_games": 0, "raw_rounds": 0, "raw_actions": 0}

    # ロード（テーブル作成直後はStreaming Insertが失敗する場合があるためリトライ）
    def _insert_with_retry(table_id, rows, max_retries=3):
        for attempt in range(max_retries):
            try:
                return client.insert_rows_json(table_id, rows)
            except Exception:
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    raise

    errors_games = _insert_with_retry(games_table_id, games_rows)
    errors_rounds = _insert_with_retry(rounds_table_id, rounds_rows)
    errors_actions = _insert_with_retry(actions_table_id, actions_rows)

    all_errors = errors_games + errors_rounds + errors_actions
    if all_errors:
        raise RuntimeError(f"BigQuery insert errors: {all_errors}")

    return {
        "raw_games": len(games_rows),
        "raw_rounds": len(rounds_rows),
        "raw_actions": len(actions_rows),
    }


def load_all_games(
    games: list[Game],
    *,
    project: str = DEFAULT_PROJECT,
    dataset: str = DEFAULT_DATASET,
) -> dict[str, int]:
    """複数のGameオブジェクトをまとめてロードする。"""
    totals = {"raw_games": 0, "raw_rounds": 0, "raw_actions": 0}
    for game in games:
        result = load_game_to_bigquery(game, project=project, dataset=dataset)
        for key in totals:
            totals[key] += result[key]
    return totals
