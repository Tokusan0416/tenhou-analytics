"""天鳳成績ダッシュボード。"""

from __future__ import annotations

import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from google.cloud import bigquery

PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "invertible-vine-477701-j8")

COLOR_PRIMARY = "#1f77b4"
COLOR_SECONDARY = "#ff7f0e"
COLOR_POSITIVE = "#2ca02c"
COLOR_NEGATIVE = "#d62728"
COLOR_NEUTRAL = "#7f7f7f"

ROUND_LABELS = {
    0: "東1局", 1: "東2局", 2: "東3局", 3: "東4局",
    4: "南1局", 5: "南2局", 6: "南3局", 7: "南4局",
}


# ==============================
# データロード
# ==============================

@st.cache_resource
def get_bq_client() -> bigquery.Client:
    return bigquery.Client(project=PROJECT_ID)


@st.cache_data(ttl=300)
def query_df(sql: str):
    client = get_bq_client()
    return client.query(sql).to_dataframe()


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
    return query_df("""
        SELECT * FROM `tenhou_marts.mart_game_results` ORDER BY game_id
    """)


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
    return {
        "total_rounds": len(df),
        "avg_score_change": df["score_change"].mean(),
        "agari_rate": df["is_agari"].mean() * 100,
        "avg_agari_ten": df.loc[df["is_agari"], "agari_ten"].mean() if df["is_agari"].any() else 0,
        "avg_naki_agari_ten": df.loc[df["is_naki"] & df["is_agari"], "agari_ten"].mean() if (df["is_naki"] & df["is_agari"]).any() else 0,
        "avg_agari_turn": df.loc[df["is_agari"], "agari_turn"].mean() if df["is_agari"].any() else 0,
        "houjuu_rate": df["is_houjuu"].mean() * 100,
        "avg_houjuu_ten": df.loc[df["is_houjuu"], "houjuu_ten"].mean() if df["is_houjuu"].any() else 0,
        "reach_rate": df["is_reach"].mean() * 100,
        "first_reach_rate": df["is_first_reach"].mean() * 100,
        "naki_rate": df["is_naki"].mean() * 100,
        "avg_dora_count": df.loc[df["is_agari"], "dora_count"].fillna(0).mean() if df["is_agari"].any() else 0,
        "avg_ryuukyoku_score_change": df.loc[df["result_type"] == "ryuukyoku", "score_change"].mean() if (df["result_type"] == "ryuukyoku").any() else 0,
        "hi_tsumo_rate": df["is_hi_tsumo"].mean() * 100,
        "avg_hi_tsumo_ten": df.loc[df["is_hi_tsumo"], "hi_tsumo_ten"].mean() if df["is_hi_tsumo"].any() else 0,
    }


def stats_to_row(label: str, stats: dict) -> dict:
    """スタッツdictを表示用の1行dictに変換。"""
    return {
        "": label,
        "局数": stats["total_rounds"],
        "アガリ率": f"{stats['agari_rate']:.1f}%",
        "アガリ打点": f"{int(stats['avg_agari_ten']):,}",
        "放銃率": f"{stats['houjuu_rate']:.1f}%",
        "放銃打点": f"{int(stats['avg_houjuu_ten']):,}",
        "リーチ率": f"{stats['reach_rate']:.1f}%",
        "副露率": f"{stats['naki_rate']:.1f}%",
        "被ツモ率": f"{stats['hi_tsumo_rate']:.1f}%",
        "局収支": f"{stats['avg_score_change']:+.1f}",
    }


def grouped_stats_table(df: pd.DataFrame, group_col: str, label_fn=None) -> pd.DataFrame:
    """グループ別のスタッツ比較テーブルを作成。"""
    rows = []
    for val in sorted(df[group_col].unique()):
        subset = df[df[group_col] == val]
        s = calc_stats(subset)
        if s:
            label = label_fn(val) if label_fn else str(val)
            rows.append(stats_to_row(label, s))
    return pd.DataFrame(rows)


def grouped_bar_chart(df: pd.DataFrame, group_col: str, metrics: list[str],
                      label_fn=None, colors=None) -> go.Figure:
    """グループ別の指標をバーチャートで比較。"""
    fig = go.Figure()
    groups = sorted(df[group_col].unique())
    if colors is None:
        colors = [COLOR_PRIMARY, COLOR_SECONDARY, COLOR_POSITIVE, COLOR_NEGATIVE, COLOR_NEUTRAL]

    for i, val in enumerate(groups):
        subset = df[df[group_col] == val]
        s = calc_stats(subset)
        if s is None:
            continue
        label = label_fn(val) if label_fn else str(val)
        values = []
        for m in metrics:
            values.append(s.get(m, 0))
        fig.add_trace(go.Bar(
            name=label, x=[m.replace("_rate", "率").replace("_", " ") for m in metrics],
            y=values, marker_color=colors[i % len(colors)],
        ))

    fig.update_layout(
        barmode="group", yaxis_title="%", height=400,
        margin=dict(t=30, b=50),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


# ==============================
# チャート関数
# ==============================

def render_radar_chart(stats: dict, all_rounds: pd.DataFrame):
    categories = ["アガリ率", "平均打点\n(千点)", "リーチ率", "副露率", "守備力\n(100-放銃率)", "局収支"]
    others = all_rounds[~all_rounds["is_me"]]
    avg_vals = {
        "agari_rate": others["is_agari"].mean() * 100 if not others.empty else 20,
        "agari_ten": (others.loc[others["is_agari"], "agari_ten"].mean() / 1000) if others["is_agari"].any() else 5,
        "reach_rate": others["is_reach"].mean() * 100 if not others.empty else 20,
        "naki_rate": others["is_naki"].mean() * 100 if not others.empty else 30,
        "houjuu_rate": others["is_houjuu"].mean() * 100 if not others.empty else 12,
        "score_change": others["score_change"].mean() if not others.empty else 0,
    }

    def norm(val, lo, hi):
        return max(0, min(1, (val - lo) / (hi - lo))) if hi != lo else 0.5

    ranges = [(10, 30), (3, 10), (10, 35), (15, 45), (80, 95), (-10, 15)]
    my = [
        norm(stats["agari_rate"], *ranges[0]),
        norm(stats["avg_agari_ten"] / 1000, *ranges[1]),
        norm(stats["reach_rate"], *ranges[2]),
        norm(stats["naki_rate"], *ranges[3]),
        norm(100 - stats["houjuu_rate"], *ranges[4]),
        norm(stats["avg_score_change"], *ranges[5]),
    ]
    avg = [
        norm(avg_vals["agari_rate"], *ranges[0]),
        norm(avg_vals["agari_ten"], *ranges[1]),
        norm(avg_vals["reach_rate"], *ranges[2]),
        norm(avg_vals["naki_rate"], *ranges[3]),
        norm(100 - avg_vals["houjuu_rate"], *ranges[4]),
        norm(avg_vals["score_change"], *ranges[5]),
    ]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=my + [my[0]], theta=categories + [categories[0]],
        fill="toself", name="自分", line=dict(color=COLOR_PRIMARY), fillcolor="rgba(31,119,180,0.2)"))
    fig.add_trace(go.Scatterpolar(r=avg + [avg[0]], theta=categories + [categories[0]],
        fill="toself", name="同卓者平均", line=dict(color=COLOR_NEUTRAL, dash="dot"), fillcolor="rgba(127,127,127,0.1)"))
    fig.update_layout(polar=dict(radialaxis=dict(visible=False, range=[0, 1])),
        showlegend=True, height=400, margin=dict(t=30, b=30, l=60, r=60))
    return fig


def render_cumulative_point_chart(games):
    df = games.copy()
    df["game_number"] = range(1, len(df) + 1)
    df["hover_text"] = df.apply(lambda r: (
        f"第{r['game_number']}戦<br>順位: {int(r['final_rank'])}位 ({r['final_point']:+.1f}pt)<br>"
        f"累積: {r['cumulative_point']:+.1f}pt<br>"
        f"vs {r['opponent1_name']}, {r['opponent2_name']}, {r['opponent3_name']}"
    ), axis=1)
    rank_colors = {1: COLOR_POSITIVE, 2: COLOR_PRIMARY, 3: COLOR_SECONDARY, 4: COLOR_NEGATIVE}

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["game_number"], y=df["cumulative_point"],
        mode="lines", line=dict(color=COLOR_PRIMARY, width=2), showlegend=False, hoverinfo="skip"))
    for rank, color in rank_colors.items():
        mask = df["final_rank"] == rank
        fig.add_trace(go.Scatter(x=df.loc[mask, "game_number"], y=df.loc[mask, "cumulative_point"],
            mode="markers", marker=dict(size=10, color=color), name=f"{rank}位",
            text=df.loc[mask, "hover_text"], hovertemplate="%{text}<extra></extra>"))
    fig.add_hline(y=0, line_dash="dash", line_color=COLOR_NEUTRAL, opacity=0.5)
    fig.update_layout(xaxis_title="対局数", yaxis_title="累積ポイント", height=400,
        margin=dict(t=30, b=50), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig


def render_score_distribution(rounds):
    agari = rounds[rounds["is_agari"]]["agari_ten"].dropna()
    houjuu = rounds[rounds["is_houjuu"]]["houjuu_ten"].dropna()
    fig = go.Figure()
    if not agari.empty:
        fig.add_trace(go.Histogram(x=agari, name="アガリ打点", marker_color=COLOR_POSITIVE, opacity=0.7, xbins=dict(size=2000)))
    if not houjuu.empty:
        fig.add_trace(go.Histogram(x=houjuu, name="放銃打点", marker_color=COLOR_NEGATIVE, opacity=0.7, xbins=dict(size=2000)))
    fig.update_layout(barmode="overlay", xaxis_title="打点", yaxis_title="回数", height=350,
        margin=dict(t=30, b=50), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig


def render_round_heatmap(rounds, games):
    df = rounds.copy()
    df["round_label"] = df["round_number"].map(ROUND_LABELS).fillna(df["round_number"].astype(str))
    game_order = {gid: i + 1 for i, gid in enumerate(games["game_id"].values)}
    df["game_number"] = df["game_id"].map(game_order)
    df = df.dropna(subset=["game_number"])
    pivot = df.pivot_table(values="score_change", index="game_number", columns="round_label", aggfunc="sum")
    col_order = [ROUND_LABELS.get(i, str(i)) for i in range(8)]
    col_order = [c for c in col_order if c in pivot.columns]
    pivot = pivot[col_order]
    fig = go.Figure(data=go.Heatmap(
        z=pivot.values, x=pivot.columns.tolist(), y=[f"第{int(g)}戦" for g in pivot.index],
        colorscale=[[0, COLOR_NEGATIVE], [0.5, "#ffffff"], [1, COLOR_POSITIVE]],
        zmid=0, text=pivot.values, texttemplate="%{text:.0f}", textfont=dict(size=10),
        hovertemplate="対局: %{y}<br>局: %{x}<br>収支: %{z:+.0f}<extra></extra>"))
    fig.update_layout(xaxis_title="局", yaxis_title="対局",
        height=max(300, len(pivot) * 35 + 100), margin=dict(t=30, b=50), yaxis=dict(autorange="reversed"))
    return fig


def render_yaku_treemap(yaku_df):
    if yaku_df.empty:
        return None
    fig = px.treemap(yaku_df, path=["yaku_category", "yaku_name"], values="count",
        color="count", color_continuous_scale=[COLOR_PRIMARY, COLOR_SECONDARY])
    fig.update_layout(height=400, margin=dict(t=30, b=10, l=10, r=10), coloraxis_showscale=False)
    fig.update_traces(texttemplate="<b>%{label}</b><br>%{value}回", textfont=dict(size=13))
    return fig


# ==============================
# 役データ加工
# ==============================

def process_yaku_data(yaku_detail, filtered_rounds):
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
            name_raw, han = parts[0], parts[1]
            if name_raw in ("ドラ", "裏ドラ", "赤ドラ"):
                continue
            if name_raw.startswith("場風 "):
                name, cat = name_raw[3:], "場風"
            elif name_raw.startswith("自風 "):
                name, cat = name_raw[3:], "自風"
            elif name_raw.startswith("役牌 "):
                name, cat = name_raw[3:], "三元牌"
            elif name_raw in ("立直", "一発", "門前清自摸和", "平和", "一盃口", "二盃口", "七対子"):
                name, cat = name_raw, "門前系"
            else:
                name, cat = name_raw, "その他"
            rows.append({"yaku_name": name, "yaku_category": cat, "han": int(han)})

    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    return df.groupby(["yaku_category", "yaku_name"]).agg(count=("han", "size"), avg_han=("han", "mean")).reset_index().sort_values("count", ascending=False)


# ==============================
# メイン
# ==============================

def main():
    st.set_page_config(page_title="天鳳成績ダッシュボード", layout="wide")
    st.title("天鳳成績ダッシュボード")

    rounds_raw = load_round_player_stats()
    all_rounds = load_all_round_player_stats()
    games = load_game_results()
    yaku_detail = load_yaku_detail()

    if rounds_raw.empty:
        st.warning("データがありません。mjlogファイルをロードしてください。")
        return

    # ===== サイドバー: 日付フィルタ =====
    st.sidebar.header("フィルタ")
    game_ids = rounds_raw["game_id"].unique()
    # game_idから日付を抽出
    date_strs = sorted(set(gid[:8] for gid in game_ids))
    dates = [pd.to_datetime(d, format="%Y%m%d").date() for d in date_strs]

    if len(dates) >= 2:
        date_range = st.sidebar.date_input(
            "日付範囲",
            value=(min(dates), max(dates)),
            min_value=min(dates),
            max_value=max(dates),
        )
        if isinstance(date_range, tuple) and len(date_range) == 2:
            start_str = date_range[0].strftime("%Y%m%d")
            end_str = date_range[1].strftime("%Y%m%d")
            rounds = rounds_raw[
                (rounds_raw["game_id"].str[:8] >= start_str) &
                (rounds_raw["game_id"].str[:8] <= end_str)
            ]
        else:
            rounds = rounds_raw
    else:
        rounds = rounds_raw

    if rounds.empty:
        st.warning("選択した日付範囲にデータがありません。")
        return

    stats = calc_stats(rounds)
    st.sidebar.metric("対象局数", f"{stats['total_rounds']}局")
    st.sidebar.metric("対局数", f"{len(rounds['game_id'].unique())}戦")

    # ===== 総合メトリクス =====
    cols = st.columns(6)
    cols[0].metric("局収支", f"{stats['avg_score_change']:+.1f}")
    cols[1].metric("アガリ率", f"{stats['agari_rate']:.1f}%")
    cols[2].metric("放銃率", f"{stats['houjuu_rate']:.1f}%")
    cols[3].metric("リーチ率", f"{stats['reach_rate']:.1f}%")
    cols[4].metric("副露率", f"{stats['naki_rate']:.1f}%")
    agari_houjuu_diff = stats["agari_rate"] - stats["houjuu_rate"]
    cols[5].metric("アガリ放銃差", f"{agari_houjuu_diff:+.1f}%")

    # ===== タブ =====
    tab_overview, tab_wind, tab_dealer, tab_round, tab_rank, tab_history = st.tabs(
        ["総合", "東場/南場", "親/子", "局別", "順位状況別", "対局履歴"]
    )

    # --- 総合タブ ---
    with tab_overview:
        col_radar, col_detail = st.columns([1, 1])
        with col_radar:
            st.subheader("スタッツレーダー")
            st.plotly_chart(render_radar_chart(stats, all_rounds), use_container_width=True)
        with col_detail:
            c1, c2, c3 = st.columns(3)
            with c1:
                st.subheader("攻撃")
                st.metric("アガリ打点", f"{int(stats['avg_agari_ten']):,}")
                st.metric("副露アガリ打点", f"{int(stats['avg_naki_agari_ten']):,}")
                st.metric("アガリ巡目", f"{stats['avg_agari_turn']:.1f}")
                st.metric("平均ドラ", f"{stats['avg_dora_count']:.2f}")
            with c2:
                st.subheader("守備")
                st.metric("放銃打点", f"{int(stats['avg_houjuu_ten']):,}")
                st.metric("被ツモ率", f"{stats['hi_tsumo_rate']:.1f}%")
                st.metric("被ツモ打点", f"{int(stats['avg_hi_tsumo_ten']):,}")
                adjusted = stats["agari_rate"] / 100 * stats["avg_agari_ten"] - stats["houjuu_rate"] / 100 * stats["avg_houjuu_ten"]
                st.metric("調整打点効率", f"{adjusted:+,.0f}")
            with c3:
                st.subheader("リーチ・副露")
                st.metric("先制率", f"{stats['first_reach_rate']:.1f}%")
                st.metric("流局平得", f"{stats['avg_ryuukyoku_score_change']:+.1f}")

        st.divider()
        col_dist, col_heat = st.columns(2)
        with col_dist:
            st.subheader("打点分布（アガリ vs 放銃）")
            st.plotly_chart(render_score_distribution(rounds), use_container_width=True)
        with col_heat:
            st.subheader("局収支ヒートマップ")
            st.plotly_chart(render_round_heatmap(rounds, games), use_container_width=True)

        st.divider()
        yaku_processed = process_yaku_data(yaku_detail, rounds)
        col_tree, col_ytable = st.columns([2, 1])
        with col_tree:
            st.subheader("役構成")
            fig = render_yaku_treemap(yaku_processed)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
        with col_ytable:
            st.subheader("役別アガリ回数")
            if not yaku_processed.empty:
                yd = yaku_processed[["yaku_name", "count", "avg_han"]].copy()
                yd["avg_han"] = yd["avg_han"].round(1)
                yd.columns = ["役名", "回数", "平均翻数"]
                st.dataframe(yd, use_container_width=True, hide_index=True)

    # --- 東場/南場タブ ---
    with tab_wind:
        rounds["wind_group"] = rounds["round_number"].apply(lambda x: "東場" if x <= 3 else "南場")
        st.subheader("東場 vs 南場 スタッツ比較")
        table = grouped_stats_table(rounds, "wind_group")
        st.dataframe(table, use_container_width=True, hide_index=True)

        metrics = ["agari_rate", "houjuu_rate", "reach_rate", "naki_rate", "hi_tsumo_rate"]
        fig = grouped_bar_chart(rounds, "wind_group", metrics, colors=[COLOR_PRIMARY, COLOR_SECONDARY])
        st.plotly_chart(fig, use_container_width=True)

    # --- 親/子タブ ---
    with tab_dealer:
        rounds["dealer_group"] = rounds["is_dealer"].apply(lambda x: "親" if x else "子")
        st.subheader("親 vs 子 スタッツ比較")
        table = grouped_stats_table(rounds, "dealer_group")
        st.dataframe(table, use_container_width=True, hide_index=True)

        metrics = ["agari_rate", "houjuu_rate", "reach_rate", "naki_rate", "hi_tsumo_rate"]
        fig = grouped_bar_chart(rounds, "dealer_group", metrics, colors=[COLOR_POSITIVE, COLOR_PRIMARY])
        st.plotly_chart(fig, use_container_width=True)

    # --- 局別タブ ---
    with tab_round:
        st.subheader("局別スタッツ比較")
        rounds["round_label_sort"] = rounds["round_number"]
        table = grouped_stats_table(rounds, "round_number", label_fn=lambda x: ROUND_LABELS.get(x, str(x)))
        st.dataframe(table, use_container_width=True, hide_index=True)

        metrics = ["agari_rate", "houjuu_rate", "reach_rate", "naki_rate"]
        fig = grouped_bar_chart(rounds, "round_number", metrics,
            label_fn=lambda x: ROUND_LABELS.get(x, str(x)),
            colors=[COLOR_PRIMARY, COLOR_SECONDARY, COLOR_POSITIVE, COLOR_NEGATIVE,
                    "#9467bd", "#8c564b", "#e377c2", "#7f7f7f"])
        st.plotly_chart(fig, use_container_width=True)

    # --- 順位状況別タブ ---
    with tab_rank:
        st.subheader("局開始時の順位別スタッツ比較")
        table = grouped_stats_table(rounds, "rank_at_start", label_fn=lambda x: f"{int(x)}位")
        st.dataframe(table, use_container_width=True, hide_index=True)

        metrics = ["agari_rate", "houjuu_rate", "reach_rate", "naki_rate"]
        fig = grouped_bar_chart(rounds, "rank_at_start", metrics,
            label_fn=lambda x: f"{int(x)}位",
            colors=[COLOR_POSITIVE, COLOR_PRIMARY, COLOR_SECONDARY, COLOR_NEGATIVE])
        st.plotly_chart(fig, use_container_width=True)

    # --- 対局履歴タブ ---
    with tab_history:
        col_cum, col_rnk = st.columns([3, 1])
        with col_cum:
            st.subheader("累積ポイント推移")
            st.plotly_chart(render_cumulative_point_chart(games), use_container_width=True)
        with col_rnk:
            st.subheader("順位分布")
            rc = games["final_rank"].value_counts().sort_index()
            fig_r = go.Figure(data=[go.Bar(
                x=[f"{i}位" for i in rc.index], y=rc.values,
                marker_color=[COLOR_POSITIVE, COLOR_PRIMARY, COLOR_SECONDARY, COLOR_NEGATIVE][:len(rc)],
                text=rc.values, textposition="auto")])
            fig_r.update_layout(height=400, margin=dict(t=30, b=50), yaxis_title="回数")
            st.plotly_chart(fig_r, use_container_width=True)

        st.subheader("対局結果一覧")
        display_cols = ["game_id", "game_date_jst", "final_rank", "final_point", "num_rounds",
            "opponent1_name", "opponent2_name", "opponent3_name", "cumulative_point"]
        available = [c for c in display_cols if c in games.columns]
        ddf = games[available].rename(columns={
            "game_id": "対局ID", "game_date_jst": "日付", "final_rank": "順位",
            "final_point": "ポイント", "num_rounds": "局数",
            "opponent1_name": "対戦者1", "opponent2_name": "対戦者2",
            "opponent3_name": "対戦者3", "cumulative_point": "累積ポイント"})
        st.dataframe(ddf, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
