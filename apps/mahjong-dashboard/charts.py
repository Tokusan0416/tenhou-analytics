"""plotlyチャート関数。"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config import (
    AGARI_DONUT_COLORS,
    COLORS,
    HOUJUU_DONUT_COLORS,
    RANK_COLORS,
    WIND_COLORS,
    round_label,
)
from data import calc_stats


def render_rank_distribution(game_stats: dict):
    """順位分布: カード形式で4列表示。"""
    rc = game_stats["rank_counts"]
    n = game_stats["total_games"]
    rank_labels = ["1位", "2位", "3位", "4位"]

    cols = st.columns(4)
    for i, (col, label, color) in enumerate(zip(cols, rank_labels, RANK_COLORS)):
        count = rc.get(i + 1, 0)
        pct = count / n * 100 if n > 0 else 0
        col.markdown(
            f'<div style="border-top: 4px solid {color}; padding: 8px 0 4px 0;">'
            f'<span style="color: {color}; font-size: 1.1em; font-weight: bold;">{label}</span><br>'
            f'<span style="font-size: 1.8em; font-weight: bold;">{count}</span>'
            f'<span style="font-size: 0.9em; color: #888;"> 回</span><br>'
            f'<span style="font-size: 1.1em; color: #666;">{pct:.2f}%</span>'
            f'</div>',
            unsafe_allow_html=True,
        )


def render_kpi_metrics(stats, game_stats, prev_stats, prev_game_stats):
    """主要KPIを2段構成で表示。"""

    def _m(col, label, val, fmt, prev_val, inverse, caption=None):
        suffix = "%" if "率" in label else ""
        display = f"{val:{fmt}}{suffix}"
        if prev_val is not None:
            delta = val - prev_val
            delta_fmt = fmt.replace("+", "")
            if delta_fmt == "d":
                delta_str = f"{int(delta):+d}"
            elif "," in delta_fmt:
                delta_str = f"{delta:+,.0f}"
            else:
                delta_str = f"{delta:+{delta_fmt}}"
            col.metric(label, display, delta=f"{delta_str}{suffix}",
                       delta_color="inverse" if inverse else "normal")
        else:
            col.metric(label, display)
        if caption:
            col.caption(caption)

    pg = prev_game_stats
    ps = prev_stats

    st.caption("**対局成績**")
    c = st.columns(7)
    _m(c[0], "対局数", game_stats["total_games"], "d", pg["total_games"] if pg else None, False)
    _m(c[1], "合計pt", game_stats["total_point"], "+.1f", pg["total_point"] if pg else None, False)
    _m(c[2], "平均pt", game_stats["avg_point"], "+.1f", pg["avg_point"] if pg else None, False)
    _m(c[3], "平均順位", game_stats["avg_rank"], ".2f", pg["avg_rank"] if pg else None, True)
    _m(c[4], "トップ率", game_stats["top_rate"], ".2f", pg["top_rate"] if pg else None, False,
       f"{game_stats['top_count']}回")
    _m(c[5], "連対率", game_stats["rentai_rate"], ".2f", pg["rentai_rate"] if pg else None, False,
       f"{game_stats['rentai_count']}回")
    _m(c[6], "ラス率", game_stats["last_rate"], ".2f", pg["last_rate"] if pg else None, True,
       f"{game_stats['last_count']}回")

    st.caption("**局成績**")
    c = st.columns(4)
    _m(c[0], "アガリ率", stats["agari_rate"], ".2f", ps["agari_rate"] if ps else None, False,
       f"{stats['agari_count']}回 / {stats['total_rounds']}局")
    _m(c[1], "放銃率", stats["houjuu_rate"], ".2f", ps["houjuu_rate"] if ps else None, True,
       f"{stats['houjuu_count']}回 / {stats['total_rounds']}局")
    _m(c[2], "リーチ率", stats["reach_rate"], ".2f", ps["reach_rate"] if ps else None, False,
       f"{stats['reach_count']}回 / {stats['total_rounds']}局")
    _m(c[3], "副露率", stats["naki_rate"], ".2f", ps["naki_rate"] if ps else None, False,
       f"{stats['naki_count']}回 / {stats['total_rounds']}局")


def render_radar_chart(stats, all_rounds):
    categories = ["アガリ率", "打点(千点)", "リーチ率", "副露率", "守備力", "局収支"]
    others = all_rounds[~all_rounds["is_me"]]
    avg = {
        "ar": others["is_agari"].mean() * 100 if not others.empty else 20,
        "at": (others.loc[others["is_agari"], "agari_ten"].mean() / 1000) if others["is_agari"].any() else 5,
        "rr": others["is_reach"].mean() * 100 if not others.empty else 20,
        "nr": others["is_naki"].mean() * 100 if not others.empty else 30,
        "hr": others["is_houjuu"].mean() * 100 if not others.empty else 12,
        "sc": others["score_change"].mean() if not others.empty else 0,
    }

    def n(val, lo, hi):
        return max(0, min(1, (val - lo) / (hi - lo))) if hi != lo else 0.5

    R = [(10, 30), (3, 10), (10, 35), (15, 45), (80, 95), (-10, 15)]
    my = [n(stats["agari_rate"], *R[0]), n(stats["avg_agari_ten"] / 1000, *R[1]),
          n(stats["reach_rate"], *R[2]), n(stats["naki_rate"], *R[3]),
          n(100 - stats["houjuu_rate"], *R[4]), n(stats["avg_score_change"], *R[5])]
    av = [n(avg["ar"], *R[0]), n(avg["at"], *R[1]), n(avg["rr"], *R[2]),
          n(avg["nr"], *R[3]), n(100 - avg["hr"], *R[4]), n(avg["sc"], *R[5])]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=my + [my[0]], theta=categories + [categories[0]],
        fill="toself", name="自分", line=dict(color=COLORS["primary"]),
        fillcolor="rgba(108,155,210,0.2)"))
    fig.add_trace(go.Scatterpolar(r=av + [av[0]], theta=categories + [categories[0]],
        fill="toself", name="同卓者平均", line=dict(color=COLORS["neutral"], dash="dot"),
        fillcolor="rgba(160,160,160,0.1)"))
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
    rc = {i + 1: RANK_COLORS[i] for i in range(4)}

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["game_number"], y=df["cumulative_point"],
        mode="lines", line=dict(color=COLORS["primary"], width=2), showlegend=False, hoverinfo="skip"))
    for rank, color in rc.items():
        m = df["final_rank"] == rank
        fig.add_trace(go.Scatter(x=df.loc[m, "game_number"], y=df.loc[m, "cumulative_point"],
            mode="markers", marker=dict(size=10, color=color), name=f"{rank}位",
            text=df.loc[m, "hover_text"], hovertemplate="%{text}<extra></extra>"))
    fig.add_hline(y=0, line_dash="dash", line_color=COLORS["neutral"], opacity=0.5)
    fig.update_layout(xaxis_title="対局数", yaxis_title="累積ポイント", height=400,
        margin=dict(t=30, b=50), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig


def render_rate_chart(games):
    """Rate推移チャート。"""
    df = games.copy()
    df["game_number"] = range(1, len(df) + 1)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["game_number"], y=df["rate"],
        mode="lines+markers", line=dict(color=COLORS["secondary"], width=2),
        marker=dict(size=6, color=COLORS["secondary"]),
        hovertemplate="第%{x}戦<br>R: %{y:.2f}<extra></extra>",
    ))
    fig.update_layout(
        xaxis_title="対局数", yaxis_title="Rate", height=300,
        margin=dict(t=30, b=50),
    )
    return fig


def render_dan_chart(games):
    """段位推移チャート。"""
    DAN_LABELS = {0:"新人",1:"９級",2:"８級",3:"７級",4:"６級",5:"５級",6:"４級",7:"３級",8:"２級",9:"１級",
        10:"初段",11:"二段",12:"三段",13:"四段",14:"五段",15:"六段",16:"七段",17:"八段",18:"九段",19:"十段",20:"天鳳"}

    df = games.copy()
    df["game_number"] = range(1, len(df) + 1)
    df["dan_name"] = df["dan"].map(DAN_LABELS)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["game_number"], y=df["dan"],
        mode="lines+markers", line=dict(color=COLORS["purple"], width=2),
        marker=dict(size=6, color=COLORS["purple"]),
        text=df["dan_name"],
        hovertemplate="第%{x}戦<br>段位: %{text}<extra></extra>",
    ))
    # Y軸を段位名で表示
    dan_vals = sorted(df["dan"].unique())
    fig.update_layout(
        xaxis_title="対局数", yaxis_title="段位", height=300,
        margin=dict(t=30, b=50),
        yaxis=dict(
            tickmode="array",
            tickvals=dan_vals,
            ticktext=[DAN_LABELS.get(d, str(d)) for d in dan_vals],
        ),
    )
    return fig


def render_score_donut(rounds, col, title, colors):
    data = rounds[rounds[col].notna()][col]
    if data.empty:
        return None
    bins = [0, 2000, 4000, 8000, 12000, float("inf")]
    labels = ["〜2000", "2000〜4000", "4000〜8000", "8000〜12000", "12000〜"]
    counts = pd.cut(data, bins=bins, labels=labels, right=False).value_counts().reindex(labels).fillna(0)

    fig = go.Figure(data=[go.Pie(
        labels=counts.index, values=counts.values, hole=0.45,
        marker_colors=colors, textinfo="label+percent", textposition="outside",
        hovertemplate="%{label}<br>%{value}回 (%{percent})<extra></extra>",
    )])
    fig.update_layout(title=dict(text=title, x=0.5, font=dict(size=14)),
        height=350, margin=dict(t=50, b=30, l=10, r=10), showlegend=False)
    return fig


def render_round_score_bar(rounds):
    df = rounds.copy()
    df["round_label"] = df["round_number"].apply(round_label)
    agg = df.groupby(["round_number", "round_label"]).agg(
        avg_score=("score_change", "mean"), count=("score_change", "count"),
    ).reset_index().sort_values("round_number")

    fig = go.Figure(data=[go.Bar(
        x=agg["round_label"], y=agg["avg_score"],
        marker_color=[COLORS["positive"] if v >= 0 else COLORS["negative"] for v in agg["avg_score"]],
        text=[f"{v:+.0f}" for v in agg["avg_score"]], textposition="auto",
        hovertemplate="%{x}<br>平均収支: %{y:+.1f}<br>局数: %{customdata}<extra></extra>",
        customdata=agg["count"],
    )])
    fig.add_hline(y=0, line_dash="dash", line_color=COLORS["neutral"], opacity=0.3)
    fig.update_layout(xaxis_title="局", yaxis_title="平均収支(百点)", height=400, margin=dict(t=30, b=50))
    return fig


def render_yaku_bar(yaku_df, total_agari):
    if yaku_df.empty:
        return None
    df = yaku_df.copy()
    df["pct"] = (df["count"] / total_agari * 100).round(2)
    df["label"] = df.apply(lambda r: f"{r['yaku_name']}({int(r['han'])}翻)", axis=1)
    df = df.sort_values("count", ascending=True).tail(15)

    fig = go.Figure(data=[go.Bar(
        y=df["label"], x=df["count"], orientation="h",
        marker_color=COLORS["primary"],
        text=df.apply(lambda r: f"{int(r['count'])}回 ({r['pct']:.2f}%)", axis=1),
        textposition="outside",
        hovertemplate="%{y}<br>%{x}回<extra></extra>",
    )])
    fig.update_layout(xaxis_title="回数", height=max(300, len(df) * 28 + 80),
        margin=dict(t=30, b=50, l=150))
    return fig


def render_trend_chart(rounds, games, period):
    rounds = rounds.copy()
    rounds["date"] = pd.to_datetime(rounds["game_id"].str[:8], format="%Y%m%d")
    fmt = {"日別": "%m/%d", "月別": "%Y-%m", "年別": "%Y"}[period]
    rounds["period"] = rounds["date"].dt.strftime(fmt)

    data = []
    for p in rounds["period"].unique():
        s = calc_stats(rounds[rounds["period"] == p])
        if s:
            data.append({"期間": p, "アガリ率": s["agari_rate"], "放銃率": s["houjuu_rate"],
                         "リーチ率": s["reach_rate"], "副露率": s["naki_rate"], "局数": s["total_rounds"]})
    if not data:
        return None
    df = pd.DataFrame(data)
    fig = go.Figure()
    for col, color in [("アガリ率", COLORS["positive"]), ("放銃率", COLORS["negative"]),
                        ("リーチ率", COLORS["primary"]), ("副露率", COLORS["secondary"])]:
        fig.add_trace(go.Scatter(x=df["期間"], y=df[col], name=col, mode="lines+markers",
            line=dict(color=color), hovertemplate=f"{col}: %{{y:.2f}}%<br>局数: %{{customdata}}<extra></extra>",
            customdata=df["局数"]))
    fig.update_layout(yaxis_title="%", height=400, margin=dict(t=30, b=50),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig


def render_rank_trend(games, period):
    games = games.copy()
    if "game_date_jst" not in games.columns:
        return None
    games["date"] = pd.to_datetime(games["game_date_jst"])
    fmt = {"日別": "%m/%d", "月別": "%Y-%m", "年別": "%Y"}[period]
    games["period"] = games["date"].dt.strftime(fmt)
    agg = games.groupby("period").agg(avg_rank=("final_rank", "mean"), games=("final_rank", "count")).reset_index()

    fig = go.Figure(data=[go.Bar(
        x=agg["period"], y=agg["avg_rank"],
        marker_color=[COLORS["positive"] if v <= 2.5 else COLORS["negative"] for v in agg["avg_rank"]],
        text=[f"{v:.2f}" for v in agg["avg_rank"]], textposition="auto",
        hovertemplate="平均順位: %{y:.2f}<br>対局数: %{customdata}<extra></extra>", customdata=agg["games"],
    )])
    fig.add_hline(y=2.5, line_dash="dash", line_color=COLORS["neutral"], opacity=0.5)
    fig.update_layout(yaxis_title="平均順位", yaxis=dict(autorange="reversed"),
        height=350, margin=dict(t=30, b=50))
    return fig


def render_agari_context_table(rounds: pd.DataFrame) -> pd.DataFrame | None:
    """状況別アガリ分析テーブル。"""
    if rounds.empty:
        return None

    contexts = [
        ("全体", rounds),
        ("リーチ時", rounds[rounds["is_reach"]]),
        ("ダマ時", rounds[~rounds["is_reach"] & ~rounds["is_naki"]]),
        ("副露時", rounds[rounds["is_naki"]]),
        ("親", rounds[rounds["is_dealer"]]),
        ("子", rounds[~rounds["is_dealer"]]),
        ("他家リーチなし", rounds[rounds["opponents_reach_count"] == 0]),
        ("他家リーチあり", rounds[rounds["opponents_reach_count"] >= 1]),
        ("他家副露なし", rounds[rounds["opponents_naki_count"] == 0]),
        ("他家副露あり", rounds[rounds["opponents_naki_count"] >= 1]),
    ]

    rows = []
    for label, subset in contexts:
        if subset.empty:
            continue
        n = len(subset)
        agari = subset[subset["is_agari"]]
        houjuu = subset[subset["is_houjuu"]]
        rows.append({
            "状況": label,
            "局数": n,
            "アガリ率": f"{agari.shape[0] / n * 100:.2f}%",
            "アガリ回数": agari.shape[0],
            "平均打点": f"{int(agari['agari_ten'].mean()):,}" if not agari.empty else "-",
            "最高打点": f"{int(agari['agari_ten'].max()):,}" if not agari.empty else "-",
            "平均巡目": f"{agari['agari_turn'].mean():.1f}" if not agari.empty and agari['agari_turn'].notna().any() else "-",
            "放銃率": f"{houjuu.shape[0] / n * 100:.2f}%",
            "放銃回数": houjuu.shape[0],
            "放銃打点": f"{int(houjuu['houjuu_ten'].mean()):,}" if not houjuu.empty else "-",
            "局収支": f"{subset['score_change'].mean():+.1f}",
        })
    return pd.DataFrame(rows)


def render_agari_type_chart(rounds: pd.DataFrame):
    """アガリ種別（リーチ/ダマ/副露）のバーチャート。"""
    agari = rounds[rounds["is_agari"]].copy()
    if agari.empty or "agari_type" not in agari.columns:
        return None

    type_order = ["リーチ", "ダマ", "副露"]
    type_colors = [COLORS["primary"], COLORS["purple"], COLORS["secondary"]]

    agg = agari.groupby("agari_type").agg(
        count=("agari_ten", "size"),
        avg_ten=("agari_ten", "mean"),
        max_ten=("agari_ten", "max"),
    ).reindex(type_order).dropna(subset=["count"]).reset_index()

    total = agg["count"].sum()
    agg["pct"] = (agg["count"] / total * 100).round(2)

    fig = go.Figure()
    for i, row in agg.iterrows():
        color = type_colors[type_order.index(row["agari_type"])] if row["agari_type"] in type_order else COLORS["neutral"]
        fig.add_trace(go.Bar(
            x=[row["agari_type"]], y=[row["count"]],
            name=row["agari_type"], marker_color=color,
            text=f"{row['pct']:.1f}%",
            textposition="auto", textfont=dict(size=14),
            hovertemplate=f"{row['agari_type']}<br>{int(row['count'])}回 ({row['pct']:.2f}%)<br>"
                          f"平均: {int(row['avg_ten']):,}点<br>最高: {int(row['max_ten']):,}点<extra></extra>",
        ))
    fig.update_layout(
        yaxis_title="回数", height=350, margin=dict(t=30, b=50),
        showlegend=False,
    )
    return fig


def render_houjuu_type_chart(rounds: pd.DataFrame):
    """放銃種別（放銃先がリーチ/ダマ/副露）のバーチャート。"""
    houjuu = rounds[rounds["is_houjuu"]].copy()
    if houjuu.empty or "houjuu_to_type" not in houjuu.columns:
        return None

    type_order = ["リーチ", "ダマ", "副露"]
    type_colors = [COLORS["negative"], COLORS["purple"], COLORS["secondary"]]

    agg = houjuu.groupby("houjuu_to_type").agg(
        count=("houjuu_ten", "size"),
        avg_ten=("houjuu_ten", "mean"),
        max_ten=("houjuu_ten", "max"),
    ).reindex(type_order).dropna(subset=["count"]).reset_index()

    total = agg["count"].sum()
    agg["pct"] = (agg["count"] / total * 100).round(2)

    fig = go.Figure()
    for _, row in agg.iterrows():
        color = type_colors[type_order.index(row["houjuu_to_type"])] if row["houjuu_to_type"] in type_order else COLORS["neutral"]
        fig.add_trace(go.Bar(
            x=[row["houjuu_to_type"]], y=[row["count"]],
            name=row["houjuu_to_type"], marker_color=color,
            text=f"{row['pct']:.1f}%",
            textposition="auto", textfont=dict(size=14),
            hovertemplate=f"{row['houjuu_to_type']}<br>{int(row['count'])}回 ({row['pct']:.2f}%)<br>"
                          f"平均: {int(row['avg_ten']):,}点<br>最高: {int(row['max_ten']):,}点<extra></extra>",
        ))
    fig.update_layout(yaxis_title="回数", height=350, margin=dict(t=30, b=50), showlegend=False)
    return fig


def render_han_distribution(rounds: pd.DataFrame, col: str, title: str, colors: list[str]):
    """翻数分布のドーナツチャート。"""
    data = rounds[rounds[col].notna()][col]
    if data.empty:
        return None
    bins = [1, 2, 3, 4, 5, 6, 8, 13, float("inf")]
    labels = ["1翻", "2翻", "3翻", "4翻", "5翻(満貫)", "6-7翻(跳満)", "8-12翻(倍満)", "13翻〜(役満)"]
    counts = pd.cut(data, bins=bins, labels=labels, right=False).value_counts().reindex(labels).fillna(0)
    counts = counts[counts > 0]

    if counts.empty:
        return None

    fig = go.Figure(data=[go.Pie(
        labels=counts.index, values=counts.values, hole=0.45,
        marker_colors=colors[:len(counts)],
        textinfo="label+percent", textposition="outside",
        hovertemplate="%{label}<br>%{value}回 (%{percent})<extra></extra>",
    )])
    fig.update_layout(title=dict(text=title, x=0.5, font=dict(size=14)),
        height=350, margin=dict(t=50, b=30, l=10, r=10), showlegend=False)
    return fig


def render_outcome_waterfall(rounds: pd.DataFrame):
    """局の結末別ウォーターフォールチャート: どこでポイントを稼ぎ/失っているか。"""
    outcomes = [
        ("リーチアガリ", rounds[rounds["is_agari"] & rounds["is_reach"]]),
        ("ダマアガリ", rounds[rounds["is_agari"] & ~rounds["is_reach"] & ~rounds["is_naki"]]),
        ("副露アガリ", rounds[rounds["is_agari"] & rounds["is_naki"]]),
        ("流局", rounds[rounds["result_type"] == "ryuukyoku"]),
        ("横移動", rounds[rounds["is_yoko_ido"]]),
        ("被ツモ", rounds[rounds["is_hi_tsumo"]]),
        ("放銃", rounds[rounds["is_houjuu"]]),
    ]

    labels, values, counts, colors, measures = [], [], [], [], []
    for label, subset in outcomes:
        if subset.empty:
            continue
        total_sc = subset["score_change"].sum()
        labels.append(label)
        values.append(total_sc)
        counts.append(len(subset))
        colors.append(COLORS["positive"] if total_sc >= 0 else COLORS["negative"])
        measures.append("relative")

    if not labels:
        return None

    # 合計を追加
    labels.append("合計")
    values.append(sum(values))
    counts.append(len(rounds))
    measures.append("total")
    colors.append(COLORS["primary"])

    fig = go.Figure(go.Waterfall(
        x=labels, y=values, measure=measures,
        increasing=dict(marker_color=COLORS["positive"]),
        decreasing=dict(marker_color=COLORS["negative"]),
        totals=dict(marker_color=COLORS["primary"]),
        text=[f"{v:+.0f}" for v in values],
        textposition="outside", textfont=dict(size=11),
        hovertemplate="%{x}<br>合計収支: %{y:+.0f}<br>回数: %{customdata}<extra></extra>",
        customdata=counts,
    ))
    fig.update_layout(
        yaxis_title="合計収支(百点)", height=400,
        margin=dict(t=30, b=50),
    )
    return fig


def render_opponents_situation_chart(rounds: pd.DataFrame, col: str = "opponents_reach_count", label: str = "他家リーチ"):
    """他家状況別のアガリ率・放銃率チャート。"""
    data = []
    for cnt in sorted(rounds[col].unique()):
        subset = rounds[rounds[col] == cnt]
        n = len(subset)
        if n < 3:
            continue
        data.append({
            label: f"{int(cnt)}人",
            "アガリ率": subset["is_agari"].mean() * 100,
            "放銃率": subset["is_houjuu"].mean() * 100,
            "局数": n,
        })

    if not data:
        return None

    df = pd.DataFrame(data)
    fig = go.Figure()
    fig.add_trace(go.Bar(name="アガリ率", x=df[label], y=df["アガリ率"],
        marker_color=COLORS["positive"],
        text=[f"{v:.2f}%" for v in df["アガリ率"]], textposition="auto"))
    fig.add_trace(go.Bar(name="放銃率", x=df[label], y=df["放銃率"],
        marker_color=COLORS["negative"],
        text=[f"{v:.2f}%" for v in df["放銃率"]], textposition="auto"))
    fig.update_layout(barmode="group", yaxis_title="%", height=350, margin=dict(t=30, b=50),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig


def render_cross_analysis_heatmap(rounds: pd.DataFrame, row_axis: str, col_axis: str, metric: str):
    """自分の状況 × 他家の状況のクロス分析ヒートマップ。"""
    df = rounds.copy()

    # 行軸のグルーピング
    if row_axis == "ALL":
        df["row_group"] = "全体"
    elif row_axis == "親/子":
        df["row_group"] = df["is_dealer"].apply(lambda x: "親" if x else "子")
    elif row_axis == "リーチ/ダマ/副露":
        df["row_group"] = df.apply(
            lambda r: "リーチ" if r["is_reach"] else "副露" if r["is_naki"] else "ダマ", axis=1)
    elif row_axis == "ツモ/出アガリ":
        df["row_group"] = df.apply(
            lambda r: "ツモ" if r.get("is_tsumo") is True else "出アガリ" if r.get("is_tsumo") is False else "非アガリ", axis=1)
    elif row_axis == "副露回数":
        df["row_group"] = df["naki_count"].clip(upper=3).apply(lambda x: f"{x}回" if x < 3 else "3回以上")

    # 列軸のグルーピング
    if col_axis == "ALL":
        df["col_group"] = "全体"
    elif col_axis == "ツモ/出アガリ":
        df["col_group"] = df.apply(
            lambda r: "ツモ" if r.get("is_tsumo") is True else "出アガリ" if r.get("is_tsumo") is False else "非アガリ", axis=1)
    elif col_axis == "リーチ/ダマ/副露":
        df["col_group"] = df.apply(
            lambda r: "リーチ" if r["is_reach"] else "副露" if r["is_naki"] else "ダマ", axis=1)
    elif col_axis == "他家リーチ数":
        df["col_group"] = df["opponents_reach_count"].clip(upper=2).apply(lambda x: f"{x}人" if x < 2 else "2人以上")
    elif col_axis == "他家副露数":
        df["col_group"] = df["opponents_naki_count"].clip(upper=3).apply(lambda x: f"{x}人" if x < 3 else "3人")

    # 指標の計算
    metric_fn = {
        "アガリ率": lambda s: s["is_agari"].mean() * 100 if len(s) > 0 else None,
        "放銃率": lambda s: s["is_houjuu"].mean() * 100 if len(s) > 0 else None,
        "局収支": lambda s: s["score_change"].mean() if len(s) > 0 else None,
        "アガリ打点": lambda s: s.loc[s["is_agari"], "agari_ten"].mean() if s["is_agari"].any() else None,
    }
    fn = metric_fn.get(metric)
    if fn is None:
        return None, None

    rows_order = sorted(df["row_group"].unique())
    cols_order = sorted(df["col_group"].unique())

    # ピボット計算
    data = {}
    count_data = {}
    for rg in rows_order:
        data[rg] = {}
        count_data[rg] = {}
        for cg in cols_order:
            subset = df[(df["row_group"] == rg) & (df["col_group"] == cg)]
            val = fn(subset) if len(subset) >= 3 else None
            data[rg][cg] = val
            count_data[rg][cg] = len(subset)

    z = [[data[rg].get(cg) for cg in cols_order] for rg in rows_order]
    counts = [[count_data[rg].get(cg) for cg in cols_order] for rg in rows_order]

    # テキスト表示
    fmt = ".2f" if metric in ("アガリ率", "放銃率") else "+.1f" if metric == "局収支" else ",.0f"
    suffix = "%" if metric in ("アガリ率", "放銃率") else ""
    text = [[f"{v:{fmt}}{suffix}<br>({c}局)" if v is not None else f"-<br>({c}局)"
             for v, c in zip(row_z, row_c)] for row_z, row_c in zip(z, counts)]

    fig = go.Figure(data=go.Heatmap(
        z=z, x=cols_order, y=rows_order,
        colorscale=[[0, COLORS["negative"]], [0.5, "#ffffff"], [1, COLORS["positive"]]],
        zmid=0 if metric == "局収支" else None,
        text=text, texttemplate="%{text}", textfont=dict(size=12),
        hovertemplate=f"{row_axis}: %{{y}}<br>{col_axis}: %{{x}}<br>{metric}: %{{z}}<extra></extra>",
    ))
    fig.update_layout(
        xaxis_title=col_axis, yaxis_title=row_axis,
        height=max(250, len(rows_order) * 60 + 100),
        margin=dict(t=30, b=50),
    )

    # テーブルも作成
    table_rows = []
    for rg in rows_order:
        row = {row_axis: rg}
        for cg in cols_order:
            val = data[rg][cg]
            c = count_data[rg][cg]
            if val is not None:
                row[f"{cg} ({c}局)"] = f"{val:{fmt}}{suffix}"
            else:
                row[f"{cg} ({c}局)"] = "-"
        table_rows.append(row)

    return fig, pd.DataFrame(table_rows)


def grouped_bar_chart(df, group_col, metrics, label_fn=None, colors=None):
    fig = go.Figure()
    groups = sorted(df[group_col].unique())
    if colors is None:
        colors = list(COLORS.values())
    metric_labels = {"agari_rate": "アガリ率", "houjuu_rate": "放銃率", "reach_rate": "リーチ率",
                     "naki_rate": "副露率", "hi_tsumo_rate": "被ツモ率"}
    for i, val in enumerate(groups):
        s = calc_stats(df[df[group_col] == val])
        if not s:
            continue
        label = label_fn(val) if label_fn else str(val)
        fig.add_trace(go.Bar(name=label, x=[metric_labels.get(m, m) for m in metrics],
            y=[s.get(m, 0) for m in metrics], marker_color=colors[i % len(colors)]))
    fig.update_layout(barmode="group", yaxis_title="%", height=400, margin=dict(t=30, b=50),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig
