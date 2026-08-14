"""データロード・スタッツ計算。"""

from __future__ import annotations

import pandas as pd
import streamlit as st
from google.cloud import bigquery

from config import PROJECT_ID


@st.cache_resource
def get_bq_client() -> bigquery.Client:
    return bigquery.Client(project=PROJECT_ID)


@st.cache_data(ttl=300)
def query_df(sql: str):
    return get_bq_client().query(sql).to_dataframe()


def load_round_player_stats():
    return query_df("""
        SELECT rps.*, dr.round_label, dr.wind, dr.is_ouras
        FROM `tenhou_warehouse.fct_round_player_stats` AS rps
        INNER JOIN `tenhou_warehouse.dim_rounds` AS dr ON rps.round_number = dr.round_number
        WHERE rps.is_me
        ORDER BY rps.game_id, rps.round_index
    """)


def load_all_round_player_stats():
    return query_df("""
        SELECT player_name, is_me, is_agari, agari_ten, is_houjuu, houjuu_ten,
               is_reach, is_naki, score_change
        FROM `tenhou_warehouse.fct_round_player_stats`
    """)


def load_game_results():
    return query_df("SELECT * FROM `tenhou_marts.mart_game_results` ORDER BY game_id")


def load_yaku_detail():
    return query_df("""
        SELECT rps.game_id, rps.round_index, rps.round_number,
               rps.is_dealer, rps.rank_at_start, rps.is_naki, rps.agari_yaku
        FROM `tenhou_warehouse.fct_round_player_stats` AS rps
        WHERE rps.is_me AND rps.is_agari AND rps.agari_yaku IS NOT NULL
    """)


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
        "avg_naki_agari_ten": df.loc[df["is_naki"] & df["is_agari"], "agari_ten"].mean() if (df["is_naki"] & df["is_agari"]).any() else 0,
        "avg_agari_turn": df.loc[df["is_agari"], "agari_turn"].mean() if agari_n else 0,
        "houjuu_rate": houjuu_n / n * 100,
        "avg_houjuu_ten": df.loc[df["is_houjuu"], "houjuu_ten"].mean() if houjuu_n else 0,
        "reach_rate": reach_n / n * 100,
        "first_reach_rate": df["is_first_reach"].sum() / n * 100,
        "naki_rate": naki_n / n * 100,
        "avg_dora_count": df.loc[df["is_agari"], "dora_count"].fillna(0).mean() if agari_n else 0,
        "avg_ryuukyoku_score_change": df.loc[df["result_type"] == "ryuukyoku", "score_change"].mean() if (df["result_type"] == "ryuukyoku").any() else 0,
        "hi_tsumo_rate": df["is_hi_tsumo"].sum() / n * 100,
        "avg_hi_tsumo_ten": df.loc[df["is_hi_tsumo"], "hi_tsumo_ten"].mean() if df["is_hi_tsumo"].any() else 0,
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
    row["副露率"] = f"{s['naki_rate']:.2f}%"
    row["副露回数"] = s["naki_count"]
    row["被ツモ率"] = f"{s['hi_tsumo_rate']:.2f}%"
    row["局収支"] = f"{s['avg_score_change']:+.1f}"
    return row


def process_yaku_data(yaku_detail: pd.DataFrame, filtered_rounds: pd.DataFrame) -> pd.DataFrame:
    """役名×翻数で集計。"""
    if filtered_rounds.empty or yaku_detail.empty:
        return pd.DataFrame()
    keys = set(zip(filtered_rounds["game_id"], filtered_rounds["round_index"]))
    filtered = yaku_detail[yaku_detail.apply(lambda r: (r["game_id"], r["round_index"]) in keys, axis=1)]
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
                    name_raw = name_raw[len(prefix):]
                    break
            rows.append({"yaku_name": name_raw, "han": int(han_str)})

    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    return df.groupby(["yaku_name", "han"]).size().reset_index(name="count").sort_values("count", ascending=False)


def grouped_stats_table(df: pd.DataFrame, group_col: str,
                        games: pd.DataFrame | None = None, label_fn=None) -> pd.DataFrame:
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


def build_trend_table(rounds: pd.DataFrame, games: pd.DataFrame, period: str) -> pd.DataFrame | None:
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
        gs = calc_game_stats(games[games["period"] == p]) if "period" in games.columns else None
        rows.append(stats_to_row(p, s, gs))
    return pd.DataFrame(rows) if rows else None
