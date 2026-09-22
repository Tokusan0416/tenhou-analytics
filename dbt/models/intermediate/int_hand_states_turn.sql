-- 手牌状態に巡目（turn）を付与
-- discardアクションのROW_NUMBERでプレイヤーごとの打牌巡目を算出
SELECT
    hs.game_id
    ,hs.round_index
    ,hs.action_index
    ,hs.player
    ,hs.action_type
    ,hs.shanten
    ,hs.is_tenpai
    ,hs.wait_tiles
    ,hs.wait_count
    ,hs.wait_count_visible
    ,ROW_NUMBER() OVER (
        PARTITION BY hs.game_id, hs.round_index, hs.player
        ORDER BY hs.action_index
    ) AS turn
FROM
    {{ ref('stg_hand_states') }} AS hs
WHERE
    hs.action_type = 'discard'
