"""天鳳成績ダッシュボード。"""

from __future__ import annotations

import os

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from google.cloud import bigquery

PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "invertible-vine-477701-j8")

# カラーパレット
COLOR_PRIMARY = "#1f77b4"
COLOR_SECONDARY = "#ff7f0e"
COLOR_POSITIVE = "#2ca02c"
COLOR_NEGATIVE = "#d62728"
COLOR_NEUTRAL = "#7f7f7f"


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


def load_all_player_stats():
    """同卓者含む全プレイヤーのスタッツ（レーダーチャート比較用）。"""
    return query_df("""
        SELECT *
        FROM `tenhou_marts.mart_player_stats`
        WHERE total_games >= 3
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


def load_round_details():
    """局単位の詳細データ（打点分布・ヒートマップ用）。"""
    return query_df("""
        SELECT
            rps.game_id
            ,rps.round_index
            ,r.round_number
            ,rps.is_agari
            ,rps.agari_ten
            ,rps.is_houjuu
            ,rps.houjuu_ten
            ,rps.score_change
            ,rps.is_reach
            ,rps.is_naki
        FROM `tenhou_warehouse.fct_round_player_stats` AS rps
        INNER JOIN `tenhou_warehouse.fct_rounds` AS r
            ON rps.game_id = r.game_id AND rps.round_index = r.round_index
        WHERE rps.is_me
        ORDER BY rps.game_id, rps.round_index
    """)


# ==============================
# チャート関数
# ==============================

def render_radar_chart(my_stats, all_stats):
    """スタッツレーダーチャート: 自分 vs 同卓者平均。"""
    categories = [
        "アガリ率", "平均打点\n(千点)", "リーチ率",
        "副露率", "守備力\n(100-放銃率)", "局収支",
    ]

    avg = all_stats[~all_stats["is_me"]].mean(numeric_only=True).fillna(0)
    my = my_stats.iloc[0]

    def normalize(val, min_val, max_val):
        return max(0, min(1, (val - min_val) / (max_val - min_val))) if max_val != min_val else 0.5

    ranges = [
        (10, 30),     # アガリ率
        (3, 10),      # 平均打点(千点)
        (10, 35),     # リーチ率
        (15, 45),     # 副露率
        (80, 95),     # 守備力(100-放銃率)
        (-10, 15),    # 局収支
    ]

    my_values = [
        normalize(float(my["agari_rate"]), *ranges[0]),
        normalize(float(my["avg_agari_ten"]) / 1000, *ranges[1]),
        normalize(float(my["reach_rate"]), *ranges[2]),
        normalize(float(my["naki_rate"]), *ranges[3]),
        normalize(100 - float(my["houjuu_rate"]), *ranges[4]),
        normalize(float(my["avg_score_change"]), *ranges[5]),
    ]

    avg_values = [
        normalize(float(avg.get("agari_rate", 20)), *ranges[0]),
        normalize(float(avg.get("avg_agari_ten", 5000)) / 1000, *ranges[1]),
        normalize(float(avg.get("reach_rate", 20)), *ranges[2]),
        normalize(float(avg.get("naki_rate", 30)), *ranges[3]),
        normalize(100 - float(avg.get("houjuu_rate", 12)), *ranges[4]),
        normalize(float(avg.get("avg_score_change", 0)), *ranges[5]),
    ]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=my_values + [my_values[0]],
        theta=categories + [categories[0]],
        fill="toself",
        name="自分",
        line=dict(color=COLOR_PRIMARY),
        fillcolor="rgba(31, 119, 180, 0.2)",
    ))
    fig.add_trace(go.Scatterpolar(
        r=avg_values + [avg_values[0]],
        theta=categories + [categories[0]],
        fill="toself",
        name="同卓者平均",
        line=dict(color=COLOR_NEUTRAL, dash="dot"),
        fillcolor="rgba(127, 127, 127, 0.1)",
    ))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=False, range=[0, 1])),
        showlegend=True,
        height=400,
        margin=dict(t=30, b=30, l=60, r=60),
    )
    return fig


def render_cumulative_point_chart(games):
    """累積ポイント推移（ホバーで対戦相手・順位表示）。"""
    df = games.copy()
    df["game_number"] = range(1, len(df) + 1)
    df["hover_text"] = df.apply(
        lambda r: (
            f"第{r['game_number']}戦<br>"
            f"順位: {int(r['final_rank'])}位 ({r['final_point']:+.1f}pt)<br>"
            f"累積: {r['cumulative_point']:+.1f}pt<br>"
            f"vs {r['opponent1_name']}, {r['opponent2_name']}, {r['opponent3_name']}"
        ),
        axis=1,
    )

    # 各点の色を順位で変える
    rank_colors = {1: COLOR_POSITIVE, 2: COLOR_PRIMARY, 3: COLOR_SECONDARY, 4: COLOR_NEGATIVE}
    df["color"] = df["final_rank"].map(rank_colors)

    fig = go.Figure()
    # ライン
    fig.add_trace(go.Scatter(
        x=df["game_number"],
        y=df["cumulative_point"],
        mode="lines",
        line=dict(color=COLOR_PRIMARY, width=2),
        showlegend=False,
        hoverinfo="skip",
    ))
    # 各点（順位で色分け）
    for rank, color in rank_colors.items():
        mask = df["final_rank"] == rank
        fig.add_trace(go.Scatter(
            x=df.loc[mask, "game_number"],
            y=df.loc[mask, "cumulative_point"],
            mode="markers",
            marker=dict(size=10, color=color),
            name=f"{rank}位",
            text=df.loc[mask, "hover_text"],
            hovertemplate="%{text}<extra></extra>",
        ))
    # 0ptライン
    fig.add_hline(y=0, line_dash="dash", line_color=COLOR_NEUTRAL, opacity=0.5)
    fig.update_layout(
        xaxis_title="対局数",
        yaxis_title="累積ポイント",
        height=400,
        margin=dict(t=30, b=50),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def render_score_distribution(rounds):
    """打点分布ヒストグラム（アガリ vs 放銃）。"""
    agari = rounds[rounds["is_agari"]]["agari_ten"].dropna()
    houjuu = rounds[rounds["is_houjuu"]]["houjuu_ten"].dropna()

    fig = go.Figure()
    if not agari.empty:
        fig.add_trace(go.Histogram(
            x=agari,
            name="アガリ打点",
            marker_color=COLOR_POSITIVE,
            opacity=0.7,
            xbins=dict(size=2000),
        ))
    if not houjuu.empty:
        fig.add_trace(go.Histogram(
            x=houjuu,
            name="放銃打点",
            marker_color=COLOR_NEGATIVE,
            opacity=0.7,
            xbins=dict(size=2000),
        ))
    fig.update_layout(
        barmode="overlay",
        xaxis_title="打点",
        yaxis_title="回数",
        height=350,
        margin=dict(t=30, b=50),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def render_round_heatmap(rounds, games):
    """局収支ヒートマップ（横: 局番号、縦: 対局）。"""
    import pandas as pd

    round_labels = {
        0: "東1", 1: "東2", 2: "東3", 3: "東4",
        4: "南1", 5: "南2", 6: "南3", 7: "南4",
    }

    df = rounds.copy()
    df["round_label"] = df["round_number"].map(round_labels).fillna(df["round_number"].astype(str))

    # 対局番号を付与
    game_order = {gid: i + 1 for i, gid in enumerate(games["game_id"].values)}
    df["game_number"] = df["game_id"].map(game_order)
    df = df.dropna(subset=["game_number"])

    # 同一対局・同一局番号で複数行ある場合（連荘）は合算
    pivot = df.pivot_table(
        values="score_change",
        index="game_number",
        columns="round_label",
        aggfunc="sum",
    )

    # 列を局の順序で並び替え
    col_order = [round_labels.get(i, str(i)) for i in range(8)]
    col_order = [c for c in col_order if c in pivot.columns]
    pivot = pivot[col_order]

    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=pivot.columns.tolist(),
        y=[f"第{int(g)}戦" for g in pivot.index],
        colorscale=[
            [0, COLOR_NEGATIVE],
            [0.5, "#ffffff"],
            [1, COLOR_POSITIVE],
        ],
        zmid=0,
        text=pivot.values,
        texttemplate="%{text:.0f}",
        textfont=dict(size=10),
        hovertemplate="対局: %{y}<br>局: %{x}<br>収支: %{z:+.0f}<extra></extra>",
    ))
    fig.update_layout(
        xaxis_title="局",
        yaxis_title="対局",
        height=max(300, len(pivot) * 35 + 100),
        margin=dict(t=30, b=50),
        yaxis=dict(autorange="reversed"),
    )
    return fig


def render_yaku_treemap(yaku):
    """役構成ツリーマップ。"""
    if yaku.empty:
        return None

    df = yaku.copy()

    # カテゴリ分類
    menzen_yaku = {"立直", "門前清自摸和", "平和", "一盃口", "二盃口", "七対子", "一発"}
    furo_yaku = {
        "役牌 白", "役牌 發", "役牌 中",
        "自風 東", "自風 南", "自風 西", "自風 北",
        "場風 東", "場風 南", "場風 西", "場風 北",
    }

    def classify(name):
        if name in menzen_yaku:
            return "門前系"
        if name in furo_yaku:
            return "副露系"
        return "その他"

    df["category"] = df["yaku_name"].apply(classify)

    fig = px.treemap(
        df,
        path=["category", "yaku_name"],
        values="yaku_count",
        color="yaku_count",
        color_continuous_scale=[COLOR_PRIMARY, COLOR_SECONDARY],
    )
    fig.update_layout(
        height=400,
        margin=dict(t=30, b=10, l=10, r=10),
        coloraxis_showscale=False,
    )
    fig.update_traces(
        texttemplate="<b>%{label}</b><br>%{value}回",
        textfont=dict(size=13),
    )
    return fig


# ==============================
# メイン
# ==============================

def main():
    st.set_page_config(page_title="天鳳成績ダッシュボード", layout="wide")
    st.title("天鳳成績ダッシュボード")

    stats = load_player_stats()
    all_stats = load_all_player_stats()
    games = load_game_results()
    yaku = load_yaku_stats()
    rounds = load_round_details()

    if stats.empty:
        st.warning("データがありません。mjlogファイルをロードしてください。")
        return

    row = stats.iloc[0]

    # ===== 総合スタッツ =====
    st.header("総合スタッツ")
    cols = st.columns(5)
    cols[0].metric("対局数", f"{int(row['total_games'])}戦")
    cols[1].metric("平均順位", f"{row['avg_rank']:.2f}")
    cols[2].metric("トップ率", f"{row['top_rate']}%")
    cols[3].metric("ラス率", f"{row['last_rate']}%")
    cols[4].metric("平均ポイント", f"{row['avg_point']:+.1f}")

    st.divider()

    # ===== レーダーチャート + 詳細スタッツ =====
    col_radar, col_detail = st.columns([1, 1])

    with col_radar:
        st.subheader("スタッツレーダー")
        fig_radar = render_radar_chart(stats, all_stats)
        st.plotly_chart(fig_radar, use_container_width=True)

    with col_detail:
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

        with col_reach:
            st.subheader("リーチ・副露")
            st.metric("リーチ率", f"{row['reach_rate']}%")
            st.metric("先制率", f"{row['first_reach_rate']}%")
            st.metric("副露率", f"{row['naki_rate']}%")
            st.metric("局収支", f"{row['avg_score_change']:+.1f}")

    st.divider()

    # ===== 対局履歴 =====
    st.header("対局履歴")

    col_cumulative, col_rank = st.columns([3, 1])

    with col_cumulative:
        st.subheader("累積ポイント推移")
        fig_cumulative = render_cumulative_point_chart(games)
        st.plotly_chart(fig_cumulative, use_container_width=True)

    with col_rank:
        st.subheader("順位分布")
        rank_counts = games["final_rank"].value_counts().sort_index()
        rank_colors = [COLOR_POSITIVE, COLOR_PRIMARY, COLOR_SECONDARY, COLOR_NEGATIVE]
        fig_rank = go.Figure(data=[go.Bar(
            x=[f"{i}位" for i in rank_counts.index],
            y=rank_counts.values,
            marker_color=rank_colors[:len(rank_counts)],
            text=rank_counts.values,
            textposition="auto",
        )])
        fig_rank.update_layout(
            height=400,
            margin=dict(t=30, b=50),
            yaxis_title="回数",
        )
        st.plotly_chart(fig_rank, use_container_width=True)

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

    # ===== 打点分布 + 局収支ヒートマップ =====
    st.header("打点分析")

    col_dist, col_heat = st.columns(2)

    with col_dist:
        st.subheader("打点分布（アガリ vs 放銃）")
        fig_dist = render_score_distribution(rounds)
        st.plotly_chart(fig_dist, use_container_width=True)

    with col_heat:
        st.subheader("局収支ヒートマップ")
        fig_heat = render_round_heatmap(rounds, games)
        st.plotly_chart(fig_heat, use_container_width=True)

    st.divider()

    # ===== 役別スタッツ =====
    st.header("役別アガリ分析")

    col_treemap, col_yaku_table = st.columns([2, 1])

    with col_treemap:
        st.subheader("役構成（門前系 / 副露系 / その他）")
        fig_treemap = render_yaku_treemap(yaku)
        if fig_treemap:
            st.plotly_chart(fig_treemap, use_container_width=True)

    with col_yaku_table:
        st.subheader("役別アガリ回数")
        if not yaku.empty:
            yaku_display = yaku[["yaku_name", "yaku_count", "avg_han"]].copy()
            yaku_display.columns = ["役名", "回数", "平均翻数"]
            st.dataframe(yaku_display, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
