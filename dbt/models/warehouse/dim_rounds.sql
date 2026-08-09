-- 局ディメンション
-- round_number(0-7) を局ラベル・東場南場・オーラス等に展開
WITH
    round_numbers AS (
        SELECT round_number
        FROM UNNEST(GENERATE_ARRAY(0, 7)) AS round_number
    )

SELECT
    round_number
    ,CASE round_number
        WHEN 0 THEN '東1局'
        WHEN 1 THEN '東2局'
        WHEN 2 THEN '東3局'
        WHEN 3 THEN '東4局'
        WHEN 4 THEN '南1局'
        WHEN 5 THEN '南2局'
        WHEN 6 THEN '南3局'
        WHEN 7 THEN '南4局'
    END AS round_label
    ,CASE
        WHEN round_number <= 3 THEN '東場'
        ELSE '南場'
    END AS wind
    ,MOD(round_number, 4) + 1 AS wind_index
    ,round_number = 7 AS is_ouras
FROM
    round_numbers
