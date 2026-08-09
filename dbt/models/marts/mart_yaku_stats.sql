-- 役別のアガリ回数集計
-- agari_yakuは "役牌 白:1,ドラ:2" のようなカンマ区切り文字列
WITH
    agari_rounds AS (
        SELECT
            player_name
            ,is_me
            ,agari_yaku
        FROM
            {{ ref('fct_round_player_stats') }}
        WHERE
            is_agari
            AND agari_yaku IS NOT NULL
    )

    ,yaku_split AS (
        SELECT
            player_name
            ,is_me
            -- "役名:翻数" から役名を抽出
            ,REGEXP_EXTRACT(yaku_entry, r'^(.+):') AS yaku_name
            ,CAST(REGEXP_EXTRACT(yaku_entry, r':(\d+)$') AS INT64) AS han
        FROM
            agari_rounds
            ,UNNEST(SPLIT(agari_yaku, ',')) AS yaku_entry
    )

SELECT
    player_name
    ,is_me
    ,yaku_name
    ,COUNT(*) AS yaku_count
    ,ROUND(AVG(han), 1) AS avg_han
FROM
    yaku_split
WHERE
    yaku_name IS NOT NULL
    -- ドラ系は別途集計済みなので除外
    AND yaku_name NOT IN ('ドラ', '裏ドラ', '赤ドラ')
GROUP BY
    player_name
    ,is_me
    ,yaku_name
ORDER BY
    player_name
    ,yaku_count DESC
