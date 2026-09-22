"""データロード・スタッツ計算。"""

from __future__ import annotations

import pandas as pd
import streamlit as st
from config import PROJECT_ID
from google.cloud import bigquery


@st.cache_resource
def get_bq_client() -> bigquery.Client:
    return bigquery.Client(project=PROJECT_ID)


@st.cache_data(ttl=300)
def query_df(sql: str):
    return get_bq_client().query(sql).to_dataframe()


def load_round_player_stats():
    return query_df("""
        SELECT
            game_id, round_index, round_number, player_seat, lobby
            ,is_dealer, result_type, rank_at_start
            ,is_agari, is_tsumo, agari_ten, agari_han, agari_yaku, agari_type, agari_turn
            ,is_houjuu, houjuu_ten, houjuu_turn, houjuu_to_type
            ,is_hi_tsumo, hi_tsumo_ten, is_yoko_ido
            ,is_reach, is_first_reach, is_naki, naki_count
            ,dora_count, score_change
            ,opponents_reach_count, opponents_naki_count
        FROM `tenhou_warehouse.fct_round_player_stats`
        WHERE is_me
        ORDER BY game_id, round_index
    """)


def load_all_round_player_stats():
    return query_df("""
        SELECT player_name, is_me, is_agari, agari_ten, is_houjuu, houjuu_ten,
               is_reach, is_naki, score_change
        FROM `tenhou_warehouse.fct_round_player_stats`
    """)


def load_game_results():
    return query_df("""
        SELECT
            game_id, game_date_jst, game_order, seat, lobby
            ,dan, rate, final_rank, final_score, final_point
            ,agari_count, houjuu_count, reach_count, naki_count, num_rounds
            ,opponent1_name, opponent2_name, opponent3_name
            ,cumulative_point
        FROM `tenhou_marts.mart_game_results`
        ORDER BY game_order
    """)


def load_tenpai_stats():
    """テンパイ情報（配牌シャンテン・待ち形等）。"""
    return query_df("""
        SELECT
            haipai_shanten, reached_tenpai, tenpai_turn
            ,tenpai_wait_count, tenpai_wait_count_visible
            ,is_agari, agari_ten, is_houjuu, houjuu_ten
            ,is_reach, is_naki, score_change
        FROM `tenhou_warehouse.fct_tenpai_stats`
        WHERE is_me
    """)


def load_hand_states_by_turn():
    """巡目別のシャンテン数データ（自分のみ）。dbt int_hand_states_turnを参照。"""
    return query_df("""
        SELECT
            ht.game_id
            ,ht.round_index
            ,ht.action_index
            ,ht.shanten
            ,ht.is_tenpai
            ,ht.action_type
            ,ht.turn
        FROM `tenhou_staging.int_hand_states_turn` AS ht
        INNER JOIN `tenhou_warehouse.fct_games` AS g
            ON ht.game_id = g.game_id AND ht.player = g.seat
        WHERE g.is_me
        ORDER BY ht.game_id, ht.round_index, ht.action_index
    """)


def load_yaku_detail():
    return query_df("""
        SELECT rps.game_id, rps.round_index, rps.round_number,
               rps.is_dealer, rps.rank_at_start, rps.is_naki, rps.agari_yaku,
               rps.agari_ten, rps.agari_han
        FROM `tenhou_warehouse.fct_round_player_stats` AS rps
        WHERE rps.is_me AND rps.is_agari AND rps.agari_yaku IS NOT NULL
    """)


# ==============================
# 対局ごとスタッツ（相関分析用）
# ==============================


def build_per_game_stats(rounds: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """fct_round_player_statsを対局単位に集約し、相関分析用のDataFrameを返す。"""
    if rounds.empty:
        return pd.DataFrame()

    g = rounds.groupby("game_id").agg(
        num_rounds=("round_index", "size"),
        agari_rate=("is_agari", "mean"),
        houjuu_rate=("is_houjuu", "mean"),
        reach_rate=("is_reach", "mean"),
        naki_rate=("is_naki", "mean"),
        hi_tsumo_rate=("is_hi_tsumo", "mean"),
        avg_score_change=("score_change", "mean"),
    )
    # アガリ打点・放銃打点
    agari = rounds[rounds["is_agari"]].groupby("game_id")["agari_ten"].mean()
    houjuu = rounds[rounds["is_houjuu"]].groupby("game_id")["houjuu_ten"].mean()
    g["avg_agari_ten"] = agari
    g["avg_houjuu_ten"] = houjuu

    # 率を%に変換
    for col in [
        "agari_rate",
        "houjuu_rate",
        "reach_rate",
        "naki_rate",
        "hi_tsumo_rate",
    ]:
        g[col] = g[col] * 100

    # 順位情報をjoin
    if not games.empty and "final_rank" in games.columns:
        rank_info = games.set_index("game_id")[["final_rank", "final_point"]]
        g = g.join(rank_info, how="left")

    return g.reset_index()


# ==============================
# スタッツ計算
# ==============================


def calc_stats(df: pd.DataFrame) -> dict | None:
    if df.empty:
        return None
    n = len(df)
    agari_n = int(df["is_agari"].sum())
    houjuu_n = int(df["is_houjuu"].sum())
    reach_n = int(df["is_reach"].sum())
    naki_n = int(df["is_naki"].sum())
    return {
        "total_rounds": n,
        "agari_count": agari_n,
        "houjuu_count": houjuu_n,
        "reach_count": reach_n,
        "naki_count": naki_n,
        "avg_score_change": df["score_change"].mean(),
        "agari_rate": agari_n / n * 100,
        "avg_agari_ten": df.loc[df["is_agari"], "agari_ten"].mean() if agari_n else 0,
        "avg_naki_agari_ten": df.loc[df["is_naki"] & df["is_agari"], "agari_ten"].mean()
        if (df["is_naki"] & df["is_agari"]).any()
        else 0,
        "avg_agari_turn": df.loc[df["is_agari"], "agari_turn"].mean() if agari_n else 0,
        "houjuu_rate": houjuu_n / n * 100,
        "avg_houjuu_ten": df.loc[df["is_houjuu"], "houjuu_ten"].mean()
        if houjuu_n
        else 0,
        "reach_rate": reach_n / n * 100,
        "first_reach_rate": df["is_first_reach"].sum() / n * 100,
        "reach_agari_count": int((df["is_reach"] & df["is_agari"]).sum()),
        "reach_agari_rate": (df["is_reach"] & df["is_agari"]).sum() / reach_n * 100
        if reach_n
        else 0,
        "naki_rate": naki_n / n * 100,
        "avg_dora_count": df.loc[df["is_agari"], "dora_count"].fillna(0).mean()
        if agari_n
        else 0,
        "avg_ryuukyoku_score_change": df.loc[
            df["result_type"] == "ryuukyoku", "score_change"
        ].mean()
        if (df["result_type"] == "ryuukyoku").any()
        else 0,
        "hi_tsumo_rate": df["is_hi_tsumo"].sum() / n * 100,
        "avg_hi_tsumo_ten": df.loc[df["is_hi_tsumo"], "hi_tsumo_ten"].mean()
        if df["is_hi_tsumo"].any()
        else 0,
    }


def calc_game_stats(games: pd.DataFrame) -> dict | None:
    if games.empty:
        return None
    n = len(games)
    return {
        "total_games": n,
        "avg_rank": games["final_rank"].mean(),
        "total_point": games["final_point"].sum(),
        "avg_point": games["final_point"].mean(),
        "top_count": int((games["final_rank"] == 1).sum()),
        "top_rate": (games["final_rank"] == 1).mean() * 100,
        "rentai_count": int((games["final_rank"] <= 2).sum()),
        "rentai_rate": (games["final_rank"] <= 2).mean() * 100,
        "last_count": int((games["final_rank"] == 4).sum()),
        "last_rate": (games["final_rank"] == 4).mean() * 100,
        "rank_counts": games["final_rank"].value_counts().sort_index().to_dict(),
    }


def stats_to_row(label: str, s: dict, gs: dict | None = None) -> dict:
    row = {"": label, "局数": s["total_rounds"]}
    if gs:
        row["対局数"] = gs["total_games"]
        row["合計pt"] = f"{gs['total_point']:+.1f}"
        row["平均pt"] = f"{gs['avg_point']:+.1f}"
        row["平均順位"] = f"{gs['avg_rank']:.2f}"
        row["トップ率"] = f"{gs['top_rate']:.2f}%"
        row["トップ回数"] = gs["top_count"]
        row["連対率"] = f"{gs['rentai_rate']:.2f}%"
        row["連対回数"] = gs["rentai_count"]
        row["ラス率"] = f"{gs['last_rate']:.2f}%"
        row["ラス回数"] = gs["last_count"]
    row["アガリ率"] = f"{s['agari_rate']:.2f}%"
    row["アガリ回数"] = s["agari_count"]
    row["アガリ打点"] = f"{int(s['avg_agari_ten']):,}"
    row["放銃率"] = f"{s['houjuu_rate']:.2f}%"
    row["放銃回数"] = s["houjuu_count"]
    row["放銃打点"] = f"{int(s['avg_houjuu_ten']):,}"
    row["リーチ率"] = f"{s['reach_rate']:.2f}%"
    row["リーチ回数"] = s["reach_count"]
    row["リーチ時アガリ率"] = f"{s['reach_agari_rate']:.2f}%"
    row["リーチ時アガリ回数"] = s["reach_agari_count"]
    row["副露率"] = f"{s['naki_rate']:.2f}%"
    row["副露回数"] = s["naki_count"]
    row["被ツモ率"] = f"{s['hi_tsumo_rate']:.2f}%"
    row["局収支"] = f"{s['avg_score_change']:+.1f}"
    return row


def calc_tenpai_group_stats(
    df: pd.DataFrame,
    group_col: str,
    label_col: str | None = None,
    label_suffix: str = "",
    count_label: str = "テンパイ回数",
    extra_fn: callable | None = None,
) -> list[dict]:
    """DataFrameをgroup_colでグループ化し、共通指標を計算。

    is_agari, is_houjuu, agari_ten, score_change を使って集計する。
    extra_fn(subset, n) を渡すと追加カラムのdictを返せる。
    """
    rows = []
    for val in sorted(df[group_col].unique()):
        subset = df[df[group_col] == val]
        if subset.empty:
            continue
        n = len(subset)
        agari_s = subset[subset["is_agari"]]
        houjuu_s = subset[subset["is_houjuu"]]
        row: dict = {}
        col_label = label_col or group_col
        row[col_label] = f"{int(val)}{label_suffix}" if label_suffix else str(val)
        row[count_label] = n
        # 追加カラム（ラベルと回数の直後に挿入）
        if extra_fn:
            row.update(extra_fn(subset, n))
        row["アガリ率"] = f"{len(agari_s) / n * 100:.2f}%"
        row["アガリ回数"] = len(agari_s)
        row["アガリ打点"] = (
            f"{int(agari_s['agari_ten'].mean()):,}" if not agari_s.empty else "-"
        )
        row["放銃率"] = f"{len(houjuu_s) / n * 100:.2f}%"
        row["放銃回数"] = len(houjuu_s)
        row["局収支"] = f"{subset['score_change'].mean():+.1f}"
        rows.append(row)
    return rows


def process_yaku_data(
    yaku_detail: pd.DataFrame, filtered_rounds: pd.DataFrame
) -> pd.DataFrame:
    """役名×翻数で集計。"""
    if filtered_rounds.empty or yaku_detail.empty:
        return pd.DataFrame()
    filtered = yaku_detail.merge(
        filtered_rounds[["game_id", "round_index"]].drop_duplicates(),
        on=["game_id", "round_index"],
        how="inner",
    )
    if filtered.empty:
        return pd.DataFrame()

    rows = []
    for _, r in filtered.iterrows():
        for entry in str(r["agari_yaku"]).split(","):
            parts = entry.rsplit(":", 1)
            if len(parts) != 2:
                continue
            name_raw, han_str = parts[0], parts[1]
            if name_raw in ("ドラ", "裏ドラ", "赤ドラ"):
                continue
            for prefix in ("場風 ", "自風 ", "役牌 "):
                if name_raw.startswith(prefix):
                    name_raw = name_raw[len(prefix) :]
                    break
            rows.append(
                {
                    "yaku_name": name_raw,
                    "han": int(han_str),
                    "agari_ten": r.get("agari_ten", 0),
                }
            )

    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    return (
        df.groupby(["yaku_name", "han"])
        .agg(
            count=("agari_ten", "size"),
            avg_ten=("agari_ten", "mean"),
        )
        .reset_index()
        .sort_values("count", ascending=False)
    )


def grouped_stats_table(
    df: pd.DataFrame, group_col: str, games: pd.DataFrame | None = None, label_fn=None
) -> pd.DataFrame:
    rows = []
    for val in sorted(df[group_col].unique()):
        subset = df[df[group_col] == val]
        s = calc_stats(subset)
        if not s:
            continue
        label = label_fn(val) if label_fn else str(val)
        gs = None
        if games is not None:
            if group_col in games.columns:
                gs = calc_game_stats(games[games[group_col] == val])
            else:
                game_ids = subset["game_id"].unique()
                gs = calc_game_stats(games[games["game_id"].isin(game_ids)])
        rows.append(stats_to_row(label, s, gs))
    return pd.DataFrame(rows)


def build_trend_table(
    rounds: pd.DataFrame, games: pd.DataFrame, period: str
) -> pd.DataFrame | None:
    """期間別のスタッツ一覧テーブル。"""
    rounds = rounds.copy()
    rounds["date"] = pd.to_datetime(rounds["game_id"].str[:8], format="%Y%m%d")
    fmt = {"日別": "%m/%d", "月別": "%Y-%m", "年別": "%Y"}[period]
    rounds["period"] = rounds["date"].dt.strftime(fmt)

    games = games.copy()
    if "game_date_jst" in games.columns:
        games["date"] = pd.to_datetime(games["game_date_jst"])
        games["period"] = games["date"].dt.strftime(fmt)

    rows = []
    for p in sorted(rounds["period"].unique()):
        s = calc_stats(rounds[rounds["period"] == p])
        if not s:
            continue
        gs = (
            calc_game_stats(games[games["period"] == p])
            if "period" in games.columns
            else None
        )
        rows.append(stats_to_row(p, s, gs))
    return pd.DataFrame(rows) if rows else None
