WITH
    source AS (
        SELECT
            *
        FROM
            {{ source('tenhou_raw', 'raw_actions') }}
    )

SELECT
    game_id
    ,round_index
    ,action_index
    ,action_type
    ,player
    ,tile
    ,turn
FROM
    source
