-- 各プレイヤーが各局で副露したかどうかのフラグ
-- 暗槓(ankan)は門前扱いなので副露にカウントしない
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
            action_type IN ('chi', 'pon', 'daiminkan', 'kakan')
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
