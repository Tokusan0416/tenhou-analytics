-- ゲーム種別ディメンション
WITH
    game_types AS (
        SELECT DISTINCT
            is_sanma
            ,is_tonnansen
            ,is_soku
            ,is_no_red
            ,lobby
        FROM
            {{ ref('stg_games') }}
    )

SELECT
    {{ dbt_utils.generate_surrogate_key(['is_sanma', 'is_tonnansen', 'is_soku', 'is_no_red', 'lobby']) }} AS game_type_key
    ,is_sanma
    ,is_tonnansen
    ,is_soku
    ,is_no_red
    ,lobby
    ,CASE
        WHEN is_sanma THEN '三麻'
        ELSE '四麻'
    END AS player_count_label
    ,CASE
        WHEN is_tonnansen THEN '東南戦'
        ELSE '東風戦'
    END AS round_type_label
FROM
    game_types
