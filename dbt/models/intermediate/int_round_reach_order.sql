-- 各局のリーチ順序を特定し、先制リーチかどうかを判定
WITH
    reach_actions AS (
        SELECT
            game_id
            ,round_index
            ,player
            ,action_index
            ,ROW_NUMBER() OVER (
                PARTITION BY game_id, round_index
                ORDER BY action_index
            ) AS reach_order
        FROM
            {{ ref('stg_actions') }} AS a
        WHERE
            action_type = 'reach'
    )

SELECT
    game_id
    ,round_index
    ,player
    ,reach_order
    ,reach_order = 1 AS is_first_reach
FROM
    reach_actions
