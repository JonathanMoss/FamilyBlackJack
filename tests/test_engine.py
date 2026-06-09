import os
import sys
import types

import pytest

# Add the parent project directory to sys.path so pytest can import app.py directly.
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT_DIR)

# If the project environment does not have Flask or Flask-SocketIO installed,
# provide tiny stubs so the app module can still be imported for engine tests.
if 'flask' not in sys.modules:
    # Create a tiny Flask replacement for import-time behavior only.
    class FlaskStub:
        def __init__(self, *args, **kwargs):
            self.config = {}

        def route(self, *args, **kwargs):
            # Return a decorator that simply returns the wrapped function.
            def decorator(fn):
                return fn
            return decorator

    flask_stub = types.ModuleType('flask')
    flask_stub.Flask = FlaskStub
    flask_stub.render_template = lambda *args, **kwargs: ''
    flask_stub.request = types.SimpleNamespace(sid=None)
    flask_stub.session = {}
    sys.modules['flask'] = flask_stub

if 'flask_socketio' not in sys.modules:
    class SocketIOStub:
        def __init__(self, *args, **kwargs):
            self._handlers = {}

        def emit(self, *args, **kwargs):
            return None

        def run(self, *args, **kwargs):
            return None

        def on(self, *args, **kwargs):
            def decorator(fn):
                return fn
            return decorator

    socketio_stub = types.ModuleType('flask_socketio')
    socketio_stub.SocketIO = SocketIOStub
    socketio_stub.emit = lambda *args, **kwargs: None
    socketio_stub.join_room = lambda *args, **kwargs: None
    sys.modules['flask_socketio'] = socketio_stub

from app import FamilyBlackjackEngine


def build_fixed_deck(card_order):
    """Return a deterministic deck list using the provided card order.

    The engine deals cards with deck.pop() in seven rounds, then uses a final
    deck.pop() for the starter discard card. That means the first element in
    this fixed list is preserved through the deal and becomes the top discard.
    """
    return list(card_order)


def test_start_game_with_ace_first_card_sets_no_penalty_and_deals_hands(monkeypatch):
    game = FamilyBlackjackEngine()
    game.players = ['Alice', 'Bob']

    # Build a deterministic deck so we know exactly which card becomes the starting discard.
    # The first card in this fixed list is preserved and becomes the starter after dealing.
    fixed_deck = build_fixed_deck([
        {'suit': 'Spades', 'value': 'Ace'}, # Starter card on the discard pile
        {'suit': 'Clubs', 'value': '3'},   # Bob 7th card
        {'suit': 'Hearts', 'value': '4'},  # Alice 7th card
        {'suit': 'Spades', 'value': '5'},  # Bob 6th card
        {'suit': 'Hearts', 'value': '6'},  # Alice 6th card
        {'suit': 'Clubs', 'value': '7'},  # Bob 5th card
        {'suit': 'Diamonds', 'value': '8'}, # Alice 5th card
        {'suit': 'Spades', 'value': '9'},  # Bob 4th card
        {'suit': 'Hearts', 'value': '10'}, # Alice 4th card
        {'suit': 'Clubs', 'value': 'Jack'}, # Bob 3rd card
        {'suit': 'Diamonds', 'value': 'Queen'}, # Alice 3rd card
        {'suit': 'Spades', 'value': 'King'}, # Bob 2nd card
        {'suit': 'Hearts', 'value': 'Ace'}, # Alice 2nd card
        {'suit': 'Clubs', 'value': '2'},   # Bob 1st card
        {'suit': 'Diamonds', 'value': '3'}, # Alice 1st card
    ])

    # Force the deck builder to return our deterministic deck.
    monkeypatch.setattr(FamilyBlackjackEngine, 'build_deck', lambda self: fixed_deck)

    success = game.start_game()

    assert success is True
    assert game.is_started is True
    assert len(game.hands['Alice']) == 7
    assert len(game.hands['Bob']) == 7

    # The starter card must be the last element of our fixed deck.
    assert game.discard_pile[-1] == {'suit': 'Spades', 'value': 'Ace'}

    # When the first card is an Ace, the engine should not set a penalty type.
    assert game.active_penalty_type is None
    assert game.accumulated_penalty == 0

    # The dealer rotates, and the current player should be the next player after the dealer.
    assert game.current_turn_index == (game.match_dealer_index + 1) % len(game.players)


def test_start_game_with_first_card_two_applies_initial_two_penalty(monkeypatch):
    game = FamilyBlackjackEngine()
    game.players = ['Alice', 'Bob']

    fixed_deck = build_fixed_deck([
        {'suit': 'Diamonds', 'value': '2'},  # Starter card should be 2
        {'suit': 'Clubs', 'value': '3'},
        {'suit': 'Hearts', 'value': '4'},
        {'suit': 'Spades', 'value': '5'},
        {'suit': 'Hearts', 'value': '6'},
        {'suit': 'Clubs', 'value': '7'},
        {'suit': 'Diamonds', 'value': '8'},
        {'suit': 'Spades', 'value': '9'},
        {'suit': 'Hearts', 'value': '10'},
        {'suit': 'Clubs', 'value': 'Jack'},
        {'suit': 'Diamonds', 'value': 'Queen'},
        {'suit': 'Spades', 'value': 'King'},
        {'suit': 'Hearts', 'value': 'Ace'},
        {'suit': 'Clubs', 'value': '3'},
        {'suit': 'Diamonds', 'value': '4'},
    ])
    monkeypatch.setattr(FamilyBlackjackEngine, 'build_deck', lambda self: fixed_deck)

    success = game.start_game()

    assert success is True
    assert game.discard_pile[-1] == {'suit': 'Diamonds', 'value': '2'}

    # If the first card is a 2, the engine should initialize a 2-penalty.
    assert game.active_penalty_type == '2'
    assert game.accumulated_penalty == 2


def test_start_game_with_first_card_black_jack_applies_initial_bj_penalty(monkeypatch):
    game = FamilyBlackjackEngine()
    game.players = ['Alice', 'Bob']

    fixed_deck = build_fixed_deck([
        {'suit': 'Spades', 'value': 'Jack'},  # Starter card should be a black Jack
        {'suit': 'Clubs', 'value': '3'},
        {'suit': 'Hearts', 'value': '4'},
        {'suit': 'Spades', 'value': '5'},
        {'suit': 'Hearts', 'value': '6'},
        {'suit': 'Clubs', 'value': '7'},
        {'suit': 'Diamonds', 'value': '8'},
        {'suit': 'Spades', 'value': '9'},
        {'suit': 'Hearts', 'value': '10'},
        {'suit': 'Clubs', 'value': '2'},
        {'suit': 'Diamonds', 'value': '3'},
        {'suit': 'Spades', 'value': '4'},
        {'suit': 'Hearts', 'value': '5'},
        {'suit': 'Clubs', 'value': '6'},
        {'suit': 'Diamonds', 'value': '7'},
    ])
    monkeypatch.setattr(FamilyBlackjackEngine, 'build_deck', lambda self: fixed_deck)

    success = game.start_game()

    assert success is True
    assert game.discard_pile[-1] == {'suit': 'Spades', 'value': 'Jack'}
    assert game.active_penalty_type == 'BJ'
    assert game.accumulated_penalty == 5


def test_validate_and_play_move_allows_ace_as_first_card(monkeypatch):
    game = FamilyBlackjackEngine()
    game.players = ['Alice']
    game.hands = {'Alice': [{'suit': 'Spades', 'value': 'Ace'}]}
    game.discard_pile = [{'suit': 'Hearts', 'value': '5'}]
    game.current_turn_index = 0

    # The first card in the chain is an Ace, which should always be valid as a match.
    success, msg, skips = game.validate_and_play_move('Alice', [{'suit': 'Spades', 'value': 'Ace'}])

    assert success is True
    assert msg == 'Success'
    assert skips == 0
    assert game.hands['Alice'] == []
    assert game.discard_pile[-1] == {'suit': 'Spades', 'value': 'Ace'}


def test_validate_and_play_move_accumulates_penalty_for_two_and_black_jack(monkeypatch):
    game = FamilyBlackjackEngine()
    game.players = ['Alice']
    game.hands = {
        'Alice': [
            {'suit': 'Hearts', 'value': '2'},
            {'suit': 'Spades', 'value': 'Jack'},
        ]
    }
    game.discard_pile = [{'suit': 'Hearts', 'value': '5'}]
    game.current_turn_index = 0

    # First play a 2 and verify the engine records a 2-penalty.
    success, msg, skips = game.validate_and_play_move('Alice', [{'suit': 'Hearts', 'value': '2'}])
    assert success is True
    assert msg == 'Success'
    assert game.active_penalty_type == '2'
    assert game.accumulated_penalty == 2

    # Reset state and play a black Jack; this should create a BJ penalty stack.
    game.hands['Alice'] = [{'suit': 'Spades', 'value': 'Jack'}]
    # The top card must share suit or value with the first played card.
    game.discard_pile = [{'suit': 'Spades', 'value': '5'}]
    game.active_penalty_type = None
    game.accumulated_penalty = 0

    success, msg, skips = game.validate_and_play_move('Alice', [{'suit': 'Spades', 'value': 'Jack'}])
    assert success is True
    assert game.active_penalty_type == 'BJ'
    assert game.accumulated_penalty == 5


def test_execute_queen_cascade_discard_same_suit_cards():
    game = FamilyBlackjackEngine()
    game.players = ['Alice']
    game.hands = {
        'Alice': [
            {'suit': 'Hearts', 'value': '2'},
            {'suit': 'Hearts', 'value': '3'},
            {'suit': 'Spades', 'value': '4'},
        ]
    }
    game.discard_pile = [{'suit': 'Diamonds', 'value': 'Queen'}]
    game.current_turn_index = 0

    # With a Queen on top of the discard, the current player can dump cards of a chosen suit.
    success, msg, skips = game.execute_queen_cascade('Alice', 'Hearts')

    assert success is True
    assert 'Dumped' in msg
    # All Hearts cards should have been moved from hand to discard pile.
    assert all(card['suit'] != 'Hearts' for card in game.hands['Alice'])
    assert any(card['suit'] == 'Hearts' for card in game.discard_pile)

def test_check_and_enforce_autodraw_forces_draw_when_no_counter():
    game = FamilyBlackjackEngine()
    game.players = ['Alice', 'Bob']
    game.is_started = True
    game.name_to_sid = {'Alice': 'sid_alice', 'Bob': 'sid_bob'}
    
    # Bob's turn, Alice just played a 2.
    game.current_turn_index = 1 
    game.active_penalty_type = '2'
    game.accumulated_penalty = 2
    
    # Bob has no 2s in hand.
    game.hands = {'Alice': [], 'Bob': [{'suit': 'Spades', 'value': 'King'}]}
    game.deck = [{'suit': 'Clubs', 'value': '5'}, {'suit': 'Clubs', 'value': '6'}]

    game.check_and_enforce_autodraw()

    assert len(game.hands['Bob']) == 3  # Original 1 + 2 penalty cards
    assert game.accumulated_penalty == 0
    assert game.current_turn_index == 0  # Turn should have advanced to Alice

def test_start_game_with_eight_first_card_skips_first_player(monkeypatch):
    game = FamilyBlackjackEngine()
    game.players = ['Alice', 'Bob', 'Charlie']
    
    # Alice is dealer (-1 -> 0). Bob is "First Player" (1).
    # If 8 is flipped, Bob is skipped, and it should be Charlie's turn (2).
    fixed_deck = build_fixed_deck([
        {'suit': 'Spades', 'value': '8'}, # Starter
        {'suit': 'Clubs', 'value': '3'}, {'suit': 'Clubs', 'value': '4'},
        {'suit': 'Clubs', 'value': '5'}, {'suit': 'Clubs', 'value': '6'},
        {'suit': 'Clubs', 'value': '7'}, {'suit': 'Clubs', 'value': '9'},
        {'suit': 'Hearts', 'value': '3'}, {'suit': 'Hearts', 'value': '4'},
        {'suit': 'Hearts', 'value': '5'}, {'suit': 'Hearts', 'value': '6'},
        {'suit': 'Hearts', 'value': '7'}, {'suit': 'Hearts', 'value': '9'},
        {'suit': 'Diamonds', 'value': '3'}, {'suit': 'Diamonds', 'value': '4'},
        {'suit': 'Diamonds', 'value': '5'}, {'suit': 'Diamonds', 'value': '6'},
        {'suit': 'Diamonds', 'value': '7'}, {'suit': 'Diamonds', 'value': '9'},
        {'suit': 'Spades', 'value': '3'}, {'suit': 'Spades', 'value': '4'},
        {'suit': 'Spades', 'value': '5'}, 
    ])
    
    monkeypatch.setattr(FamilyBlackjackEngine, 'build_deck', lambda self: fixed_deck)
    
    game.start_game()
    
    assert game.players[game.match_dealer_index] == 'Alice'
    # Bob (index 1) should be skipped. Charlie (index 2) should be current.
    assert game.current_turn_index == 2
    assert game.get_current_player_name() == 'Charlie'

def test_validate_and_play_move_accumulates_multiple_penalties_in_chain():
    game = FamilyBlackjackEngine()
    game.players = ['Alice', 'Bob']
    game.is_started = True
    game.discard_pile = [{'suit': 'Hearts', 'value': '10'}]
    game.hands = {'Alice': [{'suit': 'Hearts', 'value': '2'}, {'suit': 'Diamonds', 'value': '2'}]}
    game.current_turn_index = 0
    
    success, msg, skips = game.validate_and_play_move('Alice', [
        {'suit': 'Hearts', 'value': '2'},
        {'suit': 'Diamonds', 'value': '2'}
    ])
    
    assert success is True
    assert game.accumulated_penalty == 4
    assert game.active_penalty_type == '2'

def test_queen_cascade_accumulates_penalties_and_skips():
    game = FamilyBlackjackEngine()
    game.players = ['Alice', 'Bob', 'Charlie']
    game.is_started = True
    game.name_to_sid = {'Alice': 's1', 'Bob': 's2', 'Charlie': 's3'}
    game.discard_pile = [{'suit': 'Hearts', 'value': 'Queen'}]
    game.hands = {
        'Alice': [
            {'suit': 'Hearts', 'value': '2'},
            {'suit': 'Hearts', 'value': '8'}
        ]
    }
    game.current_turn_index = 0
    
    success, msg, skips = game.execute_queen_cascade('Alice', 'Hearts')
    
    assert success is True
    assert skips == 1
    assert game.accumulated_penalty == 2
    assert game.active_penalty_type == '2'

def test_validate_and_play_move_queen_chain_with_rank_match_at_end():
    game = FamilyBlackjackEngine()
    game.players = ['Alice', 'Bob']
    game.discard_pile = [{'suit': 'Hearts', 'value': '10'}]
    game.hands = {'Alice': [
        {'suit': 'Hearts', 'value': 'Queen'},
        {'suit': 'Hearts', 'value': '5'},
        {'suit': 'Spades', 'value': '5'}
    ]}
    game.current_turn_index = 0
    
    success, msg, skips = game.validate_and_play_move('Alice', [
        {'suit': 'Hearts', 'value': 'Queen'},
        {'suit': 'Hearts', 'value': '5'},
        {'suit': 'Spades', 'value': '5'}
    ])
    
    assert success is True
    assert len(game.hands['Alice']) == 0

def test_draw_card_reshuffles_when_deck_is_empty():
    game = FamilyBlackjackEngine()
    game.players = ['Alice']
    game.hands = {'Alice': []}
    # Deck is empty, discard pile has 3 cards.
    # Bottom: 2 of Hearts, Middle: 3 of Clubs, Top: Ace of Spades
    game.discard_pile = [
        {'suit': 'Hearts', 'value': '2'},
        {'suit': 'Clubs', 'value': '3'},
        {'suit': 'Spades', 'value': 'Ace'} 
    ]
    game.deck = []

    # Drawing 1 card should move 'Hearts 2' and 'Clubs 3' to the deck,
    # then pop one into Alice's hand.
    game.draw_card('Alice', 1)

    assert len(game.deck) == 1
    assert len(game.hands['Alice']) == 1
    # Discard pile should only contain the previous top card.
    assert game.discard_pile == [{'suit': 'Spades', 'value': 'Ace'}]

def test_update_league_results_increments_stats():
    game = FamilyBlackjackEngine()
    game.players = ['Alice', 'Bob', 'Charlie']
    # Initialize stats
    for p in game.players:
        game.register_league_player(p)

    game.update_league_results('Alice')

    assert game.league_wins['Alice'] == 1
    assert game.league_losses['Alice'] == 0
    assert game.league_wins['Bob'] == 0
    assert game.league_losses['Bob'] == 1
    assert game.league_losses['Charlie'] == 1

def test_reset_match_preserves_roster_but_clears_state():
    game = FamilyBlackjackEngine()
    game.players = ['Alice', 'Bob']
    game.is_started = True
    game.accumulated_penalty = 5
    
    game.reset_match()
    
    assert game.players == ['Alice', 'Bob'] # Preserved
    assert game.is_started is False         # Cleared
    assert game.accumulated_penalty == 0    # Cleared
