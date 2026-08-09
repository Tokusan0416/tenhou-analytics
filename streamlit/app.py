"""天鳳成績ダッシュボード。"""

from __future__ import annotations

import os

import streamlit as st
from google.cloud import bigquery

PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "invertible-vine-477701-j8")


@st.cache_resource
def get_bq_client() -> bigquery.Client:
    return bigquery.Client(project=PROJECT_ID)


@st.cache_data(ttl=300)
def query_df(sql: str):
    client = get_bq_client()
    return client.query(sql).to_dataframe()


def load_player_stats():
    return query_df("""
        SELECT *
        FROM `tenhou_marts.mart_player_stats`
        WHERE is_me
    """)


def load_game_results():
    return query_df("""
        SELECT *
        FROM `tenhou_marts.mart_game_results`
        ORDER BY game_id
    """)


def load_yaku_stats():
    return query_df("""
        SELECT *
        FROM `tenhou_marts.mart_yaku_stats`
        WHERE is_me
        ORDER BY yaku_count DESC
    """)


def main():
    st.set_page_config(page_title="天鳳成績ダッシュボード", layout="wide")
    st.title("天鳳成績ダッシュボード")

    stats = load_player_stats()
    games = load_game_results()
    yaku = load_yaku_stats()

    if stats.empty:
        st.warning("データがありません。mjlogファイルをロードしてください。")
        return

    row = stats.iloc[0]

    # --- サマリーメトリクス ---
    st.header("総合スタッツ")
    cols = st.columns(5)
    cols[0].metric("対局数", f"{int(row['total_games'])}戦")
    cols[1].metric("平均順位", f"{row['avg_rank']:.2f}")
    cols[2].metric("トップ率", f"{row['top_rate']}%")
    cols[3].metric("ラス率", f"{row['last_rate']}%")
    cols[4].metric("平均ポイント", f"{row['avg_point']:+.1f}")

    st.divider()

    # --- 攻撃 / 守備 / リーチ・副露 ---
    col_attack, col_defense, col_reach = st.columns(3)

    with col_attack:
        st.subheader("攻撃")
        st.metric("アガリ率", f"{row['agari_rate']}%")
        st.metric("アガリ打点", f"{int(row['avg_agari_ten']):,}")
        st.metric("副露アガリ打点", f"{int(row['avg_naki_agari_ten']):,}")
        st.metric("アガリ巡目", f"{row['avg_agari_turn']:.1f}")
        st.metric("平均ドラ", f"{row['avg_dora_count']:.2f}")

    with col_defense:
        st.subheader("守備")
        st.metric("放銃率", f"{row['houjuu_rate']}%")
        st.metric("放銃打点", f"{int(row['avg_houjuu_ten']):,}")
        st.metric("アガリ放銃差", f"{row['agari_houjuu_diff']:+.1f}%")
        st.metric("調整打点効率", f"{int(row['adjusted_score_efficiency']):,}")
        st.metric("局収支", f"{row['avg_score_change']:+.1f}")

    with col_reach:
        st.subheader("リーチ・副露")
        st.metric("リーチ率", f"{row['reach_rate']}%")
        st.metric("リーチ先制率", f"{row['first_reach_rate']}%")
        st.metric("副露率", f"{row['naki_rate']}%")
        st.metric("流局平得", f"{row['avg_ryuukyoku_score_change']:+.1f}")

    st.divider()

    # --- 対局履歴 ---
    st.header("対局履歴")

    col_chart, col_table = st.columns([2, 1])

    with col_chart:
        st.subheader("累積ポイント推移")
        chart_data = games[["game_id", "cumulative_point"]].copy()
        chart_data = chart_data.rename(columns={"cumulative_point": "累積ポイント"})
        chart_data["対局"] = range(1, len(chart_data) + 1)
        st.line_chart(chart_data, x="対局", y="累積ポイント")

    with col_table:
        st.subheader("順位分布")
        rank_counts = games["final_rank"].value_counts().sort_index()
        rank_df = rank_counts.reset_index()
        rank_df.columns = ["順位", "回数"]
        st.bar_chart(rank_df, x="順位", y="回数")

    st.subheader("対局結果一覧")
    display_cols = [
        "game_id", "final_rank", "final_point", "num_rounds",
        "opponent1_name", "opponent2_name", "opponent3_name",
        "cumulative_point",
    ]
    display_df = games[display_cols].copy()
    display_df.columns = [
        "対局ID", "順位", "ポイント", "局数",
        "対戦者1", "対戦者2", "対戦者3",
        "累積ポイント",
    ]
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    st.divider()

    # --- 役別スタッツ ---
    st.header("役別アガリ回数")
    if not yaku.empty:
        yaku_display = yaku[["yaku_name", "yaku_count", "avg_han"]].copy()
        yaku_display.columns = ["役名", "回数", "平均翻数"]
        col_yaku_chart, col_yaku_table = st.columns([2, 1])
        with col_yaku_chart:
            st.bar_chart(yaku_display, x="役名", y="回数")
        with col_yaku_table:
            st.dataframe(yaku_display, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
