import os
import sys
import pytest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT_DIR)

from rule_engine import RuleEngine

def test_has_valid_penalty_counter():
    # Test no active penalty returns True
    assert RuleEngine.has_valid_penalty_counter([], None, 0) == True
    
    # Test '2' penalty defense
    hand_with_2 = [{'suit': 'Hearts', 'value': '2'}]
    hand_without_2 = [{'suit': 'Spades', 'value': '3'}]
    assert RuleEngine.has_valid_penalty_counter(hand_with_2, '2', 2) == True
    assert RuleEngine.has_valid_penalty_counter(hand_without_2, '2', 2) == False
    
    # Test 'Jack' penalty defense
    hand_with_jack = [{'suit': 'Clubs', 'value': 'Jack'}]
    hand_without_jack = [{'suit': 'Hearts', 'value': '10'}]
    assert RuleEngine.has_valid_penalty_counter(hand_with_jack, 'BJ', 5) == True
    assert RuleEngine.has_valid_penalty_counter(hand_without_jack, 'BJ', 5) == False

def test_calculate_penalty_update():
    card_2 = {'suit': 'Hearts', 'value': '2'}
    card_bj = {'suit': 'Spades', 'value': 'Jack'}
    card_rj = {'suit': 'Hearts', 'value': 'Jack'}
    card_other = {'suit': 'Diamonds', 'value': '5'}

    # 1. Initiating a 2 penalty
    p_type, acc, src = RuleEngine.calculate_penalty_update(card_2, None, 0, 'Alice', None)
    assert p_type == '2' and acc == 2 and src == 'Alice'
    
    # 2. Stacking an existing 2 penalty
    p_type, acc, src = RuleEngine.calculate_penalty_update(card_2, '2', 2, 'Bob', 'Alice')
    assert p_type == '2' and acc == 4 and src == 'Bob'
    
    # 3. Initiating a Black Jack penalty
    p_type, acc, src = RuleEngine.calculate_penalty_update(card_bj, None, 0, 'Alice', None)
    assert p_type == 'BJ' and acc == 5 and src == 'Alice'

    # 4. Canceling a Black Jack penalty with a Red Jack
    p_type, acc, src = RuleEngine.calculate_penalty_update(card_rj, 'BJ', 5, 'Bob', 'Alice')
    assert p_type is None and acc == 0 and src is None

    # 5. Other cards do not affect the active penalty state
    p_type, acc, src = RuleEngine.calculate_penalty_update(card_other, '2', 4, 'Bob', 'Alice')
    assert p_type == '2' and acc == 4 and src == 'Alice'

def test_validate_move_standard():
    matched_cards = [{'suit': 'Hearts', 'value': '5'}]
    top_card = {'suit': 'Hearts', 'value': '10'}
    
    res = RuleEngine.validate_move(matched_cards, top_card, 'Hearts', None, 0, None, 'Alice')
    assert res['success'] == True
    assert res['eight_skips'] == 0

    # Test Mismatch failure
    matched_cards_bad = [{'suit': 'Diamonds', 'value': '6'}]
    res_bad = RuleEngine.validate_move(matched_cards_bad, top_card, 'Hearts', None, 0, None, 'Alice')
    assert res_bad['success'] == False
    assert "First card must be a" in res_bad['msg']

def test_validate_move_chain_and_skips():
    matched_cards = [
        {'suit': 'Spades', 'value': '8'},
        {'suit': 'Hearts', 'value': '8'}
    ]
    top_card = {'suit': 'Spades', 'value': '2'}
    
    res = RuleEngine.validate_move(matched_cards, top_card, 'Spades', None, 0, None, 'Alice')
    assert res['success'] == True
    assert res['eight_skips'] == 2
    
def test_validate_move_penalty_enforcement():
    matched_cards_bad = [{'suit': 'Hearts', 'value': '5'}]
    res_bad = RuleEngine.validate_move(matched_cards_bad, {'suit': 'Hearts', 'value': '2'}, 'Hearts', '2', 2, 'Bob', 'Alice')
    assert res_bad['success'] == False
    assert "Your last card must be a 2" in res_bad['msg']