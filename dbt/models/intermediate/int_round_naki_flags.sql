-- 各プレイヤーが各局で副露したかどうかのフラグ
WITH
    naki_actions AS (
        SELECT
            game_id
            ,round_index
            ,player
            ,COUNT(*) AS naki_count
        FROM
            {{ ref('stg_actions') }} AS a
        WHERE
            action_type IN ('chi', 'pon', 'kan', 'kakan')
        GROUP BY
            game_id
            ,round_index
            ,player
    )

SELECT
    game_id
    ,round_index
    ,player
    ,TRUE AS is_naki
    ,naki_count
FROM
    naki_actions
