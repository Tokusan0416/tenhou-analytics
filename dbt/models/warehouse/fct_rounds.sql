-- 局ファクト
-- 1行 = 1局（局レベルの結果情報）
SELECT
    game_id
    ,round_index
    ,round_number
    ,honba
    ,riichi_sticks
    ,dora_indicator
    ,dealer
    ,starting_score0
    ,starting_score1
    ,starting_score2
    ,starting_score3
    ,result_type
    ,agari_winner
    ,agari_from_who
    ,agari_is_tsumo
    ,agari_ten
    ,agari_fu
    ,agari_han
    ,agari_yaku
    ,agari_winning_tile
    ,agari_dora_count
    ,agari_ura_dora_count
    ,agari_aka_dora_count
    ,score_change0
    ,score_change1
    ,score_change2
    ,score_change3
    ,ryuukyoku_reason
    ,tenpai_players
FROM
    {{ ref('stg_rounds') }}
