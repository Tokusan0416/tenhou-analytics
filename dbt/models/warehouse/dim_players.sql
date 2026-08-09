-- プレイヤーディメンション
-- 全対局に登場したプレイヤーをユニークに集約
WITH
    players_unpivot AS (
        SELECT game_id, 0 AS seat, player0_name AS player_name, player0_dan AS dan, player0_rate AS rate FROM {{ ref('stg_games') }}
        UNION ALL
        SELECT game_id, 1 AS seat, player1_name AS player_name, player1_dan AS dan, player1_rate AS rate FROM {{ ref('stg_games') }}
        UNION ALL
        SELECT game_id, 2 AS seat, player2_name AS player_name, player2_dan AS dan, player2_rate AS rate FROM {{ ref('stg_games') }}
        UNION ALL
        SELECT game_id, 3 AS seat, player3_name AS player_name, player3_dan AS dan, player3_rate AS rate FROM {{ ref('stg_games') }}
    )

    ,player_stats AS (
        SELECT
            player_name
            ,MAX(dan) AS max_dan
            ,MAX(rate) AS max_rate
            ,COUNT(DISTINCT game_id) AS game_count
        FROM
            players_unpivot
        GROUP BY
            player_name
    )

SELECT
    player_name
    ,max_dan
    ,max_rate
    ,game_count
FROM
    player_stats
