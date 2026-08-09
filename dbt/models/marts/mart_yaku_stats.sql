-- 役別のアガリ回数集計
-- agari_yakuは "役牌 白:1,ドラ:2" のようなカンマ区切り文字列
-- 風牌・三元牌は正規化、門前/副露による翻数変化も判定
WITH
    agari_rounds AS (
        SELECT
            player_name
            ,is_me
            ,is_naki
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
            ,is_naki
            ,REGEXP_EXTRACT(yaku_entry, r'^(.+):') AS yaku_name_raw
            ,CAST(REGEXP_EXTRACT(yaku_entry, r':(\d+)$') AS INT64) AS han
        FROM
            agari_rounds
            ,UNNEST(SPLIT(agari_yaku, ',')) AS yaku_entry
    )

    ,yaku_normalized AS (
        SELECT
            player_name
            ,is_me
            ,is_naki
            -- 風牌・三元牌の正規化
            ,CASE
                WHEN yaku_name_raw LIKE '場風 %' THEN REPLACE(yaku_name_raw, '場風 ', '')
                WHEN yaku_name_raw LIKE '自風 %' THEN REPLACE(yaku_name_raw, '自風 ', '')
                WHEN yaku_name_raw LIKE '役牌 %' THEN REPLACE(yaku_name_raw, '役牌 ', '')
                ELSE yaku_name_raw
            END AS yaku_name
            -- 役のカテゴリ
            ,CASE
                WHEN yaku_name_raw LIKE '場風 %' THEN '場風'
                WHEN yaku_name_raw LIKE '自風 %' THEN '自風'
                WHEN yaku_name_raw IN ('役牌 白', '役牌 發', '役牌 中') THEN '三元牌'
                WHEN yaku_name_raw IN ('立直', '一発', '門前清自摸和', '平和', '一盃口', '二盃口', '七対子') THEN '門前系'
                WHEN yaku_name_raw IN ('ドラ', '裏ドラ', '赤ドラ') THEN 'ドラ系'
                WHEN yaku_name_raw IN ('断么九', '三色同順', '一気通貫', '混全帯么九', '純全帯么九', '混一色', '清一色', '対々和', '三暗刻', '混老頭', '小三元', '三色同刻') THEN 'その他'
                ELSE 'その他'
            END AS yaku_category
            ,han
            -- 門前/副露の判定（副露で翻数が下がる役）
            ,CASE
                WHEN yaku_name_raw IN ('三色同順', '一気通貫', '混全帯么九', '純全帯么九', '混一色', '清一色')
                    THEN CASE WHEN is_naki THEN '副露' ELSE '門前' END
                ELSE NULL
            END AS menzen_furo
        FROM
            yaku_split
        WHERE
            yaku_name_raw IS NOT NULL
    )

SELECT
    player_name
    ,is_me
    ,yaku_name
    ,yaku_category
    ,menzen_furo
    ,COUNT(*) AS yaku_count
    ,ROUND(AVG(han), 1) AS avg_han
    ,MIN(han) AS min_han
    ,MAX(han) AS max_han
FROM
    yaku_normalized
WHERE
    yaku_category != 'ドラ系'
GROUP BY
    player_name
    ,is_me
    ,yaku_name
    ,yaku_category
    ,menzen_furo
ORDER BY
    player_name
    ,yaku_count DESC
