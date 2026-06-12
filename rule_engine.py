"""Decoupled Rule Engine for Family Blackjack."""

class RuleEngine:
    """Handles card validation and penalty logic to keep the game engine modular."""

    @staticmethod
    def has_valid_penalty_counter(hand, active_penalty_type, accumulated_penalty):
        """Assess if the hand has counter cards for active penalties."""
        if accumulated_penalty == 0:
            return True
        if active_penalty_type == '2':
            return any(card['value'] == '2' for card in hand)
        if active_penalty_type == 'BJ':
            return any(card['value'] == 'Jack' for card in hand)
        return False

    @staticmethod
    def calculate_penalty_update(card, current_type, current_accumulated, player_name, current_source):
        """Determine the new penalty state after playing a card."""
        new_type = current_type
        new_accumulated = current_accumulated
        new_source = current_source

        if card['value'] == '2':
            new_accumulated = new_accumulated + 2 if current_type == '2' else 2
            new_type = '2'
            new_source = player_name
        elif card['value'] == 'Jack' and card['suit'] in ['Spades', 'Clubs']:
            new_accumulated = new_accumulated + 5 if current_type == 'BJ' else 5
            new_type = 'BJ'
            new_source = player_name
        elif (
            card['value'] == 'Jack' and
            card['suit'] in ['Hearts', 'Diamonds'] and
            current_type == 'BJ'
        ):
            new_type = None
            new_accumulated = 0
            new_source = None

        return new_type, new_accumulated, new_source

    @staticmethod
    def validate_move(matched_cards, top_card, active_suit, active_penalty_type, accumulated_penalty, penalty_source, player_name):
        """
        Validates if the selected matched_cards can be played on top_card.
        Returns a dictionary with result details for state processing.
        """
        last_card = matched_cards[-1]
        last_is_bj = (last_card['value'] == 'Jack' and last_card['suit'] in ['Spades', 'Clubs'])
        last_is_rj = (last_card['value'] == 'Jack' and last_card['suit'] in ['Hearts', 'Diamonds'])
        last_is_two = (last_card['value'] == '2')

        if accumulated_penalty > 0:
            if active_penalty_type == '2' and not last_is_two:
                return {'success': False, 'msg': "Your last card must be a 2!"}
            if active_penalty_type == 'BJ' and not (last_is_bj or last_is_rj):
                return {'success': False, 'msg': "Your last card must be a Jack!"}

        active_val = top_card['value']
        first_card = matched_cards[0]

        is_valid_match = (first_card['suit'] == active_suit or first_card['value'] == active_val or first_card['value'] == 'Ace')
        if not is_valid_match:
            return {'success': False, 'msg': f"First card must be a ({active_suit}) or value ({active_val})."}

        eight_skips = 0
        is_dump_active = first_card['value'] == 'Queen' or top_card['value'] == 'Queen'
        dump_suit = first_card['suit'] if first_card['value'] == 'Queen' else active_suit

        temp_penalty_type = active_penalty_type
        temp_accumulated = accumulated_penalty
        temp_source = penalty_source

        for card_idx, card in enumerate(matched_cards):
            if card_idx > 0:
                prev_card = matched_cards[card_idx - 1]
                is_chain_valid = (card['value'] == prev_card['value'] or card['suit'] == prev_card['suit'] or card['value'] == 'Ace' or (is_dump_active and card['suit'] == dump_suit))
                if not is_chain_valid:
                    return {'success': False, 'msg': "Chain invalid: Cards must match rank, suit, be an Ace, or follow a Queen"}
            if card['value'] == '8': eight_skips += 1
            temp_penalty_type, temp_accumulated, temp_source = RuleEngine.calculate_penalty_update(card, temp_penalty_type, temp_accumulated, player_name, temp_source)

        return {'success': True, 'msg': "Success", 'eight_skips': eight_skips, 'new_penalty_type': temp_penalty_type, 'new_accumulated_penalty': temp_accumulated, 'new_penalty_source': temp_source}