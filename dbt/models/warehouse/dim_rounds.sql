-- 局ディメンション
-- round_number を局ラベル・場風・オーラス等に展開
-- 東南戦で全員3万点以下の場合、西場以降に突入するケースに対応（0-15）
WITH
    round_numbers AS (
        SELECT round_number
        FROM UNNEST(GENERATE_ARRAY(0, 15)) AS round_number
    )

    ,wind_names AS (
        SELECT *
        FROM UNNEST([
            STRUCT(0 AS wind_id, '東場' AS wind_name, '東' AS wind_char)
            ,STRUCT(1, '南場', '南')
            ,STRUCT(2, '西場', '西')
            ,STRUCT(3, '北場', '北')
        ])
    )

SELECT
    rn.round_number
    ,w.wind_char || CAST(MOD(rn.round_number, 4) + 1 AS STRING) || '局' AS round_label
    ,w.wind_name AS wind
    ,MOD(rn.round_number, 4) + 1 AS wind_index
    -- 東南戦のオーラスは南4局(7)だが、延長時は最終局がオーラス
    -- ここでは南4局以降をオーラス候補とする
    ,rn.round_number >= 7 AS is_ouras
FROM
    round_numbers AS rn
    INNER JOIN wind_names AS w ON w.wind_id = DIV(rn.round_number, 4)
