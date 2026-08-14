"""共通設定・カラーパレット・定数。"""

import os

PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "invertible-vine-477701-j8")

# パステル系の統一カラーパレット
COLORS = {
    "primary": "#6C9BD2",     # 柔らかい青
    "secondary": "#F0A868",   # 柔らかいオレンジ
    "positive": "#7BC8A4",    # 柔らかい緑
    "negative": "#E8887D",    # 柔らかい赤
    "neutral": "#A0A0A0",     # グレー
    "purple": "#B8A9D4",      # 柔らかい紫
    "brown": "#C4A882",       # 柔らかい茶
    "pink": "#E8B4C8",        # 柔らかいピンク
}

# 順位カラー（1位〜4位）
RANK_COLORS = [
    COLORS["positive"],   # 1位: 緑
    COLORS["primary"],    # 2位: 青
    COLORS["secondary"],  # 3位: オレンジ
    COLORS["negative"],   # 4位: 赤
]

# アガリ打点分布カラー（低→高）
AGARI_DONUT_COLORS = ["#C8E6D0", "#9DD4AE", "#72C28D", "#4DAF6B", "#2E9B55"]

# 放銃打点分布カラー（低→高）
HOUJUU_DONUT_COLORS = ["#F5D5C8", "#EDBA9F", "#E49F78", "#D98453", "#C96A3A"]

# 場別カラー
WIND_COLORS = [COLORS["primary"], COLORS["secondary"], COLORS["positive"]]

# 局ラベル
WIND_CHARS = {0: "東", 1: "南", 2: "西", 3: "北"}


def round_label(rn: int) -> str:
    return WIND_CHARS.get(rn // 4, "?") + str(rn % 4 + 1) + "局"
