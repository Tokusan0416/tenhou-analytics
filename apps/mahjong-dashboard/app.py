"""天鳳成績ダッシュボード - メインレイアウト。"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from charts import (
    grouped_bar_chart,
    render_agari_context_table,
    render_agari_type_chart,
    render_cross_analysis_heatmap,
    render_cumulative_point_chart,
    render_dan_chart,
    render_han_distribution,
    render_houjuu_type_chart,
    render_kpi_metrics,
    render_opponents_situation_chart,
    render_outcome_waterfall,
    render_radar_chart,
    render_rank_distribution,
    render_rank_trend,
    render_rate_chart,
    render_round_score_bar,
    render_score_donut,
    render_trend_chart,
    render_yaku_bar,
)
from config import AGARI_DONUT_COLORS, COLORS, HOUJUU_DONUT_COLORS, RANK_COLORS, WIND_COLORS, round_label
from data import (
    build_trend_table,
    calc_game_stats,
    calc_stats,
    grouped_stats_table,
    load_all_round_player_stats,
    load_game_results,
    load_round_player_stats,
    load_tenpai_stats,
    load_yaku_detail,
    process_yaku_data,
)

SEAT_LABELS = {0: "東家(起家)", 1: "南家", 2: "西家", 3: "北家"}


def main():
    st.set_page_config(page_title="天鳳成績ダッシュボード", layout="wide")
    st.title("天鳳成績ダッシュボード")

    rounds_raw = load_round_player_stats()
    all_rounds = load_all_round_player_stats()
    games = load_game_results()
    yaku_detail = load_yaku_detail()
    tenpai_data = load_tenpai_stats()

    if rounds_raw.empty:
        st.warning("データがありません。mjlogファイルをロードしてください。")
        return

    # 日付カラムを事前追加
    rounds_raw = rounds_raw.copy()
    rounds_raw["_date"] = pd.to_datetime(rounds_raw["game_id"].str[:8], format="%Y%m%d")
    games = games.copy()
    if "game_date_jst" in games.columns:
        games["_date"] = pd.to_datetime(games["game_date_jst"])
    else:
        games["_date"] = pd.to_datetime(games["game_id"].str[:8], format="%Y%m%d")

    # ===== サイドバー =====
    st.sidebar.header("フィルタ")

    # 期間切り替え
    today = rounds_raw["_date"].max().date()
    period_options = ["ALL", "今日", "今週", "今月", "今年", "直近7日", "直近30日"]
    selected_period = st.sidebar.radio("期間", period_options, horizontal=False)

    def _filter_by_period(df, date_col, period, ref_date):
        """期間でフィルタし、(当期df, 前期df)を返す。"""
        if period == "ALL":
            return df, pd.DataFrame()
        elif period == "今日":
            cur = df[df[date_col].dt.date == ref_date]
            prev_date = ref_date - pd.Timedelta(days=1)
            prev = df[df[date_col].dt.date == prev_date]
        elif period == "今週":
            week_start = ref_date - pd.Timedelta(days=ref_date.weekday())
            cur = df[df[date_col].dt.date >= week_start]
            prev_start = week_start - pd.Timedelta(days=7)
            prev = df[(df[date_col].dt.date >= prev_start) & (df[date_col].dt.date < week_start)]
        elif period == "今月":
            cur = df[df[date_col].dt.to_period("M") == pd.Period(ref_date, "M")]
            prev_month = pd.Period(ref_date, "M") - 1
            prev = df[df[date_col].dt.to_period("M") == prev_month]
        elif period == "今年":
            cur = df[df[date_col].dt.year == ref_date.year]
            prev = df[df[date_col].dt.year == ref_date.year - 1]
        elif period == "直近7日":
            start = ref_date - pd.Timedelta(days=6)
            cur = df[df[date_col].dt.date >= start]
            prev_start = start - pd.Timedelta(days=7)
            prev = df[(df[date_col].dt.date >= prev_start) & (df[date_col].dt.date < start)]
        elif period == "直近30日":
            start = ref_date - pd.Timedelta(days=29)
            cur = df[df[date_col].dt.date >= start]
            prev_start = start - pd.Timedelta(days=30)
            prev = df[(df[date_col].dt.date >= prev_start) & (df[date_col].dt.date < start)]
        else:
            return df, pd.DataFrame()
        return cur, prev

    rounds, prev_rounds = _filter_by_period(rounds_raw, "_date", selected_period, today)
    filtered_games, prev_games = _filter_by_period(games, "_date", selected_period, today)

    # 卓フィルタ
    if "lobby" in rounds.columns:
        lobbies = sorted(rounds_raw["lobby"].dropna().unique())
        if len(lobbies) > 1:
            selected_lobby = st.sidebar.multiselect("卓", options=lobbies, default=lobbies)
            rounds = rounds[rounds["lobby"].isin(selected_lobby)]
            filtered_games = filtered_games[filtered_games["lobby"].isin(selected_lobby)] if "lobby" in filtered_games.columns else filtered_games
            prev_rounds = prev_rounds[prev_rounds["lobby"].isin(selected_lobby)] if not prev_rounds.empty and "lobby" in prev_rounds.columns else prev_rounds
            prev_games = prev_games[prev_games["lobby"].isin(selected_lobby)] if not prev_games.empty and "lobby" in prev_games.columns else prev_games

    if rounds.empty:
        st.warning("選択した期間にデータがありません。")
        return

    stats = calc_stats(rounds)
    game_stats = calc_game_stats(filtered_games)

    # 前回同比
    prev_stats = calc_stats(prev_rounds) if not prev_rounds.empty else None
    prev_game_stats = calc_game_stats(prev_games) if not prev_games.empty else None

    # サイドバー情報
    period_label = selected_period if selected_period != "ALL" else "全期間"
    st.sidebar.metric("対象", f"{game_stats['total_games']}戦 / {stats['total_rounds']}局")
    if prev_stats:
        st.sidebar.caption(f"比較: {period_label}の前回同期間 ({prev_stats['total_rounds']}局)")

    # ===== KPI =====
    render_kpi_metrics(stats, game_stats, prev_stats, prev_game_stats)

    # ===== タブ =====
    tab_overview, tab_context, tab_shanten, tab_wait, tab_trend, tab_wind, tab_dealer, tab_seat, tab_round, tab_rank, tab_naki, tab_history = st.tabs(
        ["総合", "状況別分析", "シャンテン分析", "待ち形分析", "推移", "東場/南場", "親/子", "起家別", "局別", "順位状況別", "副露回数別", "対局履歴"]
    )

    # --- 総合タブ ---
    with tab_overview:
        col_rank_dist, col_radar = st.columns([1, 1])
        with col_rank_dist:
            st.subheader("順位分布")
            render_rank_distribution(game_stats)
        with col_radar:
            st.subheader("スタッツレーダー")
            st.plotly_chart(render_radar_chart(stats, all_rounds), use_container_width=True)

        st.divider()

        # 詳細スタッツ
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
            st.metric("被ツモ率", f"{stats['hi_tsumo_rate']:.2f}%")
            st.metric("被ツモ打点", f"{int(stats['avg_hi_tsumo_ten']):,}")
        with c3:
            st.subheader("その他")
            st.metric("先制リーチ率", f"{stats['first_reach_rate']:.2f}%")
            st.metric("流局平得", f"{stats['avg_ryuukyoku_score_change']:+.1f}")
            st.metric("局収支", f"{stats['avg_score_change']:+.1f}")
            adj = stats["agari_rate"] / 100 * stats["avg_agari_ten"] - stats["houjuu_rate"] / 100 * stats["avg_houjuu_ten"]
            st.metric("調整打点効率", f"{adj:+,.0f}")

        st.divider()

        # 打点分布セクション（独立した1行）
        st.subheader("打点分布")
        dist_col1, dist_col2, dist_col3 = st.columns([1, 1, 1])
        with dist_col1:
            dealer_filter = st.radio("親/子", ["全体", "親", "子"], horizontal=True, key="score_dealer")
            dist_mode = st.radio("表示", ["打点別", "翻数別"], horizontal=True, key="dist_mode")
        r_filtered = rounds if dealer_filter == "全体" else rounds[rounds["is_dealer"]] if dealer_filter == "親" else rounds[~rounds["is_dealer"]]

        dist_a, dist_b = st.columns(2)
        han_colors = ["#C8D8E8", "#A8C8D8", "#88B8C8", "#68A8B8", "#489898", "#288878", "#187858", "#084838"]
        with dist_a:
            if dist_mode == "打点別":
                fig = render_score_donut(r_filtered[r_filtered["is_agari"]], "agari_ten",
                    "アガリ打点分布", AGARI_DONUT_COLORS)
            else:
                fig = render_han_distribution(r_filtered[r_filtered["is_agari"]], "agari_han",
                    "アガリ翻数分布", han_colors)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
        with dist_b:
            if dist_mode == "打点別":
                fig = render_score_donut(r_filtered[r_filtered["is_houjuu"]], "houjuu_ten",
                    "放銃打点分布", HOUJUU_DONUT_COLORS)
            else:
                fig = render_han_distribution(r_filtered[r_filtered["is_houjuu"]], "houjuu_han",
                    "放銃翻数分布", HOUJUU_DONUT_COLORS)
            if fig:
                st.plotly_chart(fig, use_container_width=True)

        st.divider()

        # 局別平均収支
        st.subheader("局別平均収支")
        st.plotly_chart(render_round_score_bar(rounds), use_container_width=True)

        st.divider()

        # 役別アガリ（独立した1行）
        st.subheader("役別アガリ")
        yaku_dealer = st.radio("親/子", ["全体", "親", "子"], horizontal=True, key="yaku_dealer")
        r_yaku = rounds if yaku_dealer == "全体" else rounds[rounds["is_dealer"]] if yaku_dealer == "親" else rounds[~rounds["is_dealer"]]
        yaku_processed = process_yaku_data(yaku_detail, r_yaku)
        total_agari = int(r_yaku["is_agari"].sum())
        col_yaku_chart, col_yaku_table = st.columns([1, 1])
        with col_yaku_chart:
            fig = render_yaku_bar(yaku_processed, total_agari)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
        with col_yaku_table:
            if not yaku_processed.empty:
                yd = yaku_processed.copy()
                yd["役名"] = yd.apply(lambda r: f"{r['yaku_name']}({int(r['han'])}翻)", axis=1)
                yd["％"] = (yd["count"] / total_agari * 100).round(2) if total_agari > 0 else 0
                yd["平均打点"] = yd["avg_ten"].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "-")
                yd = yd.rename(columns={"count": "回数"})
                st.dataframe(yd[["役名", "回数", "％", "平均打点"]], use_container_width=True, hide_index=True)

    # --- 状況別分析タブ ---
    with tab_context:
        # ウォーターフォール
        st.subheader("局結末別の収支内訳")
        fig = render_outcome_waterfall(rounds)
        if fig:
            st.plotly_chart(fig, use_container_width=True)

        st.divider()

        # アガリ種別 + 放銃種別
        col_agari_type, col_houjuu_type = st.columns(2)
        with col_agari_type:
            st.subheader("アガリ種別")
            fig = render_agari_type_chart(rounds)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            agari_data = rounds[rounds["is_agari"]].copy()
            if not agari_data.empty and "agari_type" in agari_data.columns:
                type_rows = []
                for at in ["リーチ", "ダマ", "副露"]:
                    subset = agari_data[agari_data["agari_type"] == at]
                    if subset.empty:
                        continue
                    type_rows.append({
                        "種別": at, "回数": len(subset),
                        "割合": f"{len(subset) / len(agari_data) * 100:.2f}%",
                        "平均打点": f"{int(subset['agari_ten'].mean()):,}",
                        "最高打点": f"{int(subset['agari_ten'].max()):,}",
                        "平均巡目": f"{subset['agari_turn'].mean():.1f}" if subset['agari_turn'].notna().any() else "-",
                    })
                if type_rows:
                    st.dataframe(pd.DataFrame(type_rows), use_container_width=True, hide_index=True)

        with col_houjuu_type:
            st.subheader("放銃種別")
            fig = render_houjuu_type_chart(rounds)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            houjuu_data = rounds[rounds["is_houjuu"]].copy()
            if not houjuu_data.empty and "houjuu_to_type" in houjuu_data.columns:
                h_rows = []
                for ht in ["リーチ", "ダマ", "副露"]:
                    subset = houjuu_data[houjuu_data["houjuu_to_type"] == ht]
                    if subset.empty:
                        continue
                    h_rows.append({
                        "放銃先": ht, "回数": len(subset),
                        "割合": f"{len(subset) / len(houjuu_data) * 100:.2f}%",
                        "平均打点": f"{int(subset['houjuu_ten'].mean()):,}",
                        "最高打点": f"{int(subset['houjuu_ten'].max()):,}",
                        "平均巡目": f"{subset['houjuu_turn'].mean():.1f}" if subset['houjuu_turn'].notna().any() else "-",
                    })
                if h_rows:
                    st.dataframe(pd.DataFrame(h_rows), use_container_width=True, hide_index=True)

        st.divider()

        # 他家状況別
        st.subheader("他家状況別")
        col_opp_r, col_opp_n = st.columns(2)
        with col_opp_r:
            st.caption("他家リーチ数別")
            fig = render_opponents_situation_chart(rounds)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
        with col_opp_n:
            st.caption("他家副露数別")
            fig = render_opponents_situation_chart(rounds, col="opponents_naki_count", label="他家副露")
            if fig:
                st.plotly_chart(fig, use_container_width=True)

        st.divider()

        # クロス分析
        st.subheader("クロス分析")
        col_axis1, col_axis2, col_metric = st.columns(3)
        with col_axis1:
            row_axis = st.selectbox("行軸（自分の状況）", [
                "ALL", "親/子", "リーチ/ダマ/副露", "ツモ/出アガリ", "副露回数",
            ])
        with col_axis2:
            col_axis = st.selectbox("列軸", [
                "ALL", "ツモ/出アガリ", "リーチ/ダマ/副露", "他家リーチ数", "他家副露数",
            ])
        with col_metric:
            metric = st.selectbox("指標", [
                "アガリ率", "放銃率", "局収支", "アガリ打点",
            ])

        fig, cross_df = render_cross_analysis_heatmap(rounds, row_axis, col_axis, metric)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        if cross_df is not None:
            st.dataframe(cross_df, use_container_width=True, hide_index=True)

        st.divider()

        st.subheader("状況別スタッツ一覧")
        context_table = render_agari_context_table(rounds)
        if context_table is not None:
            st.dataframe(context_table, use_container_width=True, hide_index=True)

    # --- シャンテン分析タブ ---
    with tab_shanten:
        if tenpai_data.empty:
            st.info("テンパイデータがありません。")
        else:
            # 配牌シャンテン分布
            st.subheader("配牌シャンテン数分布")
            sh_counts = tenpai_data["haipai_shanten"].value_counts().sort_index()
            fig = go.Figure(data=[go.Bar(
                x=[f"{int(s)}シャンテン" for s in sh_counts.index],
                y=sh_counts.values,
                marker_color=COLORS["primary"],
                text=[f"{v}局" for v in sh_counts.values],
                textposition="auto",
            )])
            fig.update_layout(yaxis_title="局数", height=350, margin=dict(t=30, b=50))
            st.plotly_chart(fig, use_container_width=True)

            st.divider()

            # 配牌シャンテン別スタッツ
            st.subheader("配牌シャンテン別スタッツ")
            sh_rows = []
            for sh in sorted(tenpai_data["haipai_shanten"].unique()):
                subset = tenpai_data[tenpai_data["haipai_shanten"] == sh]
                n = len(subset)
                tenpai_s = subset[subset["reached_tenpai"]]
                agari_s = subset[subset["is_agari"]]
                houjuu_s = subset[subset["is_houjuu"]]
                reach_s = subset[subset["is_reach"]]
                sh_rows.append({
                    "配牌シャンテン": f"{int(sh)}シャンテン",
                    "局数": n,
                    "テンパイ率": f"{len(tenpai_s) / n * 100:.2f}%",
                    "テンパイ回数": len(tenpai_s),
                    "リーチ率": f"{len(reach_s) / n * 100:.2f}%",
                    "アガリ率": f"{len(agari_s) / n * 100:.2f}%",
                    "アガリ打点": f"{int(agari_s['agari_ten'].mean()):,}" if not agari_s.empty else "-",
                    "放銃率": f"{len(houjuu_s) / n * 100:.2f}%",
                    "局収支": f"{subset['score_change'].mean():+.1f}",
                    "平均テンパイ巡目": f"{tenpai_s['tenpai_turn'].mean():.1f}" if not tenpai_s.empty and tenpai_s['tenpai_turn'].notna().any() else "-",
                })
            st.dataframe(pd.DataFrame(sh_rows), use_container_width=True, hide_index=True)

    # --- 待ち形分析タブ ---
    with tab_wait:
        if tenpai_data.empty:
            st.info("テンパイデータがありません。")
        else:
            # アガリ時の待ち形
            st.subheader("アガリ時の待ち形")
            agari_tenpai = tenpai_data[tenpai_data["is_agari"] & tenpai_data["reached_tenpai"]]
            agari_group = st.radio("グループ", ["ALL", "リーチ", "ダマ", "副露"], horizontal=True, key="agari_wait_group")
            if agari_group == "リーチ":
                agari_tenpai = agari_tenpai[agari_tenpai["is_reach"]]
            elif agari_group == "ダマ":
                agari_tenpai = agari_tenpai[~agari_tenpai["is_reach"] & ~agari_tenpai["is_naki"]]
            elif agari_group == "副露":
                agari_tenpai = agari_tenpai[agari_tenpai["is_naki"]]

            if not agari_tenpai.empty:
                aw_rows = []
                for wt in ["両面", "カンチャン", "ペンチャン", "シャボ", "単騎", "多面"]:
                    subset = agari_tenpai[agari_tenpai["tenpai_wait_type"] == wt]
                    if subset.empty:
                        continue
                    aw_rows.append({
                        "待ち形": wt,
                        "アガリ回数": len(subset),
                        "割合": f"{len(subset) / len(agari_tenpai) * 100:.2f}%",
                        "平均打点": f"{int(subset['agari_ten'].mean()):,}",
                        "平均待ち枚数": f"{subset['tenpai_wait_count'].mean():.1f}",
                    })
                if aw_rows:
                    st.dataframe(pd.DataFrame(aw_rows), use_container_width=True, hide_index=True)
            else:
                st.info("該当するアガリデータがありません。")

            st.divider()

            # 放銃時の相手の待ち形
            st.subheader("放銃時の相手の待ち形")
            houjuu_wait = tenpai_data[tenpai_data["is_houjuu"]].copy()
            houjuu_group = st.radio("グループ", ["ALL", "リーチ", "ダマ", "副露"], horizontal=True, key="houjuu_wait_group")
            if houjuu_group == "リーチ":
                houjuu_wait = houjuu_wait[houjuu_wait["is_reach"]]
            elif houjuu_group == "ダマ":
                houjuu_wait = houjuu_wait[~houjuu_wait["is_reach"] & ~houjuu_wait["is_naki"]]
            elif houjuu_group == "副露":
                houjuu_wait = houjuu_wait[houjuu_wait["is_naki"]]

            if not houjuu_wait.empty and "houjuu_opponent_wait_type" in houjuu_wait.columns:
                hw_rows = []
                for wt in ["両面", "カンチャン", "ペンチャン", "シャボ", "単騎", "多面"]:
                    subset = houjuu_wait[houjuu_wait["houjuu_opponent_wait_type"] == wt]
                    if subset.empty:
                        continue
                    hw_rows.append({
                        "相手の待ち形": wt,
                        "放銃回数": len(subset),
                        "割合": f"{len(subset) / len(houjuu_wait) * 100:.2f}%",
                        "平均放銃打点": f"{int(subset['houjuu_ten'].mean()):,}",
                    })
                if hw_rows:
                    st.dataframe(pd.DataFrame(hw_rows), use_container_width=True, hide_index=True)
            else:
                st.info("該当する放銃データがありません。")

    # --- 推移タブ ---
    with tab_trend:
        period = st.radio("集計単位", ["日別", "月別", "年別"], horizontal=True)

        col_rt, col_tt = st.columns(2)
        with col_rt:
            st.subheader(f"平均順位推移（{period}）")
            fig = render_rank_trend(filtered_games, period)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
        with col_tt:
            st.subheader(f"指標推移（{period}）")
            fig = render_trend_chart(rounds, filtered_games, period)
            if fig:
                st.plotly_chart(fig, use_container_width=True)

        st.divider()
        st.subheader(f"スタッツ一覧（{period}）")
        trend_table = build_trend_table(rounds, filtered_games, period)
        if trend_table is not None:
            st.dataframe(trend_table, use_container_width=True, hide_index=True)

    # --- 東場/南場タブ ---
    with tab_wind:
        rw = rounds.copy()
        rw["wind_group"] = rw["round_number"].apply(lambda x: "東場" if x <= 3 else "南場" if x <= 7 else "西場")
        st.subheader("場別スタッツ比較")
        st.dataframe(grouped_stats_table(rw, "wind_group"), use_container_width=True, hide_index=True)
        fig = grouped_bar_chart(rw, "wind_group",
            ["agari_rate", "houjuu_rate", "reach_rate", "naki_rate", "hi_tsumo_rate"], colors=WIND_COLORS)
        st.plotly_chart(fig, use_container_width=True)

    # --- 親/子タブ ---
    with tab_dealer:
        rd = rounds.copy()
        rd["dealer_group"] = rd["is_dealer"].apply(lambda x: "親" if x else "子")
        st.subheader("親 vs 子 スタッツ比較")
        st.dataframe(grouped_stats_table(rd, "dealer_group"), use_container_width=True, hide_index=True)
        fig = grouped_bar_chart(rd, "dealer_group",
            ["agari_rate", "houjuu_rate", "reach_rate", "naki_rate", "hi_tsumo_rate"],
            colors=[COLORS["positive"], COLORS["primary"]])
        st.plotly_chart(fig, use_container_width=True)

    # --- 起家別タブ ---
    with tab_seat:
        rs = rounds.copy()
        rs["seat_label"] = rs["player_seat"].map(SEAT_LABELS)
        # 対局成績をseat別に集計するためgamesにもseat情報を付与
        fg_seat = filtered_games.copy()
        if "seat" in fg_seat.columns:
            fg_seat["player_seat"] = fg_seat["seat"]
        st.subheader("起家別（東南西北）スタッツ比較")
        st.dataframe(grouped_stats_table(rs, "player_seat",
            games=fg_seat if "player_seat" in fg_seat.columns else None,
            label_fn=lambda x: SEAT_LABELS.get(x, str(x))),
            use_container_width=True, hide_index=True)
        fig = grouped_bar_chart(rs, "player_seat",
            ["agari_rate", "houjuu_rate", "reach_rate", "naki_rate"],
            label_fn=lambda x: SEAT_LABELS.get(x, str(x)), colors=RANK_COLORS)
        st.plotly_chart(fig, use_container_width=True)

    # --- 局別タブ ---
    with tab_round:
        st.subheader("局別スタッツ比較")
        st.dataframe(grouped_stats_table(rounds, "round_number", label_fn=round_label),
            use_container_width=True, hide_index=True)
        fig = grouped_bar_chart(rounds, "round_number",
            ["agari_rate", "houjuu_rate", "reach_rate", "naki_rate"],
            label_fn=round_label,
            colors=[COLORS["primary"], COLORS["secondary"], COLORS["positive"], COLORS["negative"],
                    COLORS["purple"], COLORS["brown"], COLORS["pink"], COLORS["neutral"], "#bcbd22"])
        st.plotly_chart(fig, use_container_width=True)

    # --- 順位状況別タブ ---
    with tab_rank:
        st.subheader("局開始時の順位別スタッツ比較")
        st.dataframe(grouped_stats_table(rounds, "rank_at_start", label_fn=lambda x: f"{int(x)}位"),
            use_container_width=True, hide_index=True)
        fig = grouped_bar_chart(rounds, "rank_at_start",
            ["agari_rate", "houjuu_rate", "reach_rate", "naki_rate"],
            label_fn=lambda x: f"{int(x)}位", colors=RANK_COLORS)
        st.plotly_chart(fig, use_container_width=True)

    # --- 副露回数別タブ ---
    with tab_naki:
        rn = rounds.copy()
        rn["naki_group"] = rn["naki_count"].clip(upper=3).apply(lambda x: f"{x}回" if x < 3 else "3回以上")
        st.subheader("副露回数別スタッツ比較")
        st.dataframe(grouped_stats_table(rn, "naki_group"), use_container_width=True, hide_index=True)
        fig = grouped_bar_chart(rn, "naki_group",
            ["agari_rate", "houjuu_rate", "hi_tsumo_rate"],
            colors=[COLORS["neutral"], COLORS["primary"], COLORS["secondary"], COLORS["negative"]])
        st.plotly_chart(fig, use_container_width=True)

    # --- 対局履歴タブ ---
    with tab_history:
        st.subheader("累積ポイント推移")
        st.plotly_chart(render_cumulative_point_chart(filtered_games), use_container_width=True)

        col_rate, col_dan = st.columns(2)
        with col_rate:
            st.subheader("Rate推移")
            st.plotly_chart(render_rate_chart(filtered_games), use_container_width=True)
        with col_dan:
            st.subheader("段位推移")
            st.plotly_chart(render_dan_chart(filtered_games), use_container_width=True)

        st.subheader("対局結果一覧")
        DAN_LABELS = {0:"新人",1:"９級",2:"８級",3:"７級",4:"６級",5:"５級",6:"４級",7:"３級",8:"２級",9:"１級",
            10:"初段",11:"二段",12:"三段",13:"四段",14:"五段",15:"六段",16:"七段",17:"八段",18:"九段",19:"十段",20:"天鳳"}
        display_cols = ["game_date_jst", "seat", "dan", "rate",
            "final_rank", "final_score", "final_point",
            "agari_count", "houjuu_count", "reach_count", "naki_count",
            "num_rounds",
            "opponent1_name", "opponent2_name", "opponent3_name", "cumulative_point"]
        available = [c for c in display_cols if c in filtered_games.columns]
        ddf = filtered_games[available].copy()
        if "seat" in ddf.columns:
            ddf["seat"] = ddf["seat"].map(SEAT_LABELS)
        if "dan" in ddf.columns:
            ddf["dan"] = ddf["dan"].map(DAN_LABELS)
        ddf = ddf.rename(columns={
            "game_date_jst": "日付", "seat": "席",
            "dan": "段位", "rate": "R",
            "final_rank": "順位", "final_score": "最終点数", "final_point": "ポイント",
            "agari_count": "アガリ", "houjuu_count": "放銃",
            "reach_count": "立直", "naki_count": "副露",
            "num_rounds": "局数",
            "opponent1_name": "対戦者1", "opponent2_name": "対戦者2",
            "opponent3_name": "対戦者3", "cumulative_point": "累積pt"})
        st.dataframe(ddf, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
