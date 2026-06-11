import os
import sys
import types
import time

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
    flask_stub.redirect = lambda *args, **kwargs: ''
    flask_stub.url_for = lambda *args, **kwargs: ''
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

        def start_background_task(self, task, *args, **kwargs):
            pass

        def sleep(self, seconds):
            pass

    socketio_stub = types.ModuleType('flask_socketio')
    socketio_stub.SocketIO = SocketIOStub
    socketio_stub.emit = lambda *args, **kwargs: None
    socketio_stub.join_room = lambda *args, **kwargs: None
    sys.modules['flask_socketio'] = socketio_stub

from app import FamilyBlackjackEngine, BOT_NAME


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
        {'suit': 'Clubs', 'value': '3'},   # Bob 1st card
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
        {'suit': 'Hearts', 'value': '2'},    # Bob counter-card
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
        {'suit': 'Clubs', 'value': '4'},
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
        {'suit': 'Clubs', 'value': 'Jack'},   # Bob counter-card
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
        {'suit': 'Clubs', 'value': '7'},
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
    game.hands = {'Alice': [{'suit': 'Hearts', 'value': '5'}], 'Bob': [{'suit': 'Spades', 'value': 'King'}]}
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

def test_validate_and_play_move_queen_suit_chain_with_user_example():
    game = FamilyBlackjackEngine()
    game.players = ['Alice', 'Bob']
    game.discard_pile = [{'suit': 'Hearts', 'value': '5'}] # Starting card
    game.hands = {'Alice': [
        {'suit': 'Hearts', 'value': 'Queen'},
        {'suit': 'Hearts', 'value': '3'},
        {'suit': 'Hearts', 'value': '4'},
        {'suit': 'Spades', 'value': '4'}
    ]}
    game.current_turn_index = 0 # Alice's turn

    selected_cards = [
        {'suit': 'Hearts', 'value': 'Queen'},
        {'suit': 'Hearts', 'value': '3'},
        {'suit': 'Hearts', 'value': '4'},
        {'suit': 'Spades', 'value': '4'}
    ]

    success, msg, skips = game.validate_and_play_move('Alice', selected_cards)

    assert success is True, f"Move failed: {msg}"
    assert msg == 'Success'
    assert skips == 0
    assert len(game.hands['Alice']) == 0 # All cards played
    assert game.discard_pile[-1] == {'suit': 'Spades', 'value': '4'} # Last card played
    assert game.discard_pile == [
        {'suit': 'Hearts', 'value': '5'}, # Original top card
        {'suit': 'Hearts', 'value': 'Queen'},
        {'suit': 'Hearts', 'value': '3'},
        {'suit': 'Hearts', 'value': '4'},
        {'suit': 'Spades', 'value': '4'}
    ]

def test_validate_and_play_move_chain_on_existing_table_queen():
    game = FamilyBlackjackEngine()
    game.players = ['Alice', 'Bob']
    game.discard_pile = [{'suit': 'Diamonds', 'value': 'Queen'}]
    game.hands = {'Alice': [
        {'suit': 'Diamonds', 'value': '5'},
        {'suit': 'Diamonds', 'value': '8'},
        {'suit': 'Diamonds', 'value': 'Jack'}
    ]}
    game.current_turn_index = 0

    # Verifies that manual chain dumping works when the Queen was the last card played to the table
    success, msg, skips = game.validate_and_play_move('Alice', [
        {'suit': 'Diamonds', 'value': '5'},
        {'suit': 'Diamonds', 'value': '8'},
        {'suit': 'Diamonds', 'value': 'Jack'}
    ])

    assert success is True
    assert len(game.hands['Alice']) == 0

def test_validate_and_play_move_rejects_invalid_chain():
    game = FamilyBlackjackEngine()
    game.players = ['Alice', 'Bob']
    game.discard_pile = [{'suit': 'Hearts', 'value': '10'}]
    game.hands = {'Alice': [
        {'suit': 'Hearts', 'value': '6'},
        {'suit': 'Spades', 'value': '9'}  # Invalid match to Hearts 6
    ]}
    game.current_turn_index = 0
    
    success, msg, skips = game.validate_and_play_move('Alice', [
        {'suit': 'Hearts', 'value': '6'},
        {'suit': 'Spades', 'value': '9'}
    ])
    
    assert success is False
    assert 'Chain invalid' in msg

def test_start_game_adds_bot_for_solo_player(monkeypatch):
    game = FamilyBlackjackEngine()
    game.players = ['Alice']
    
    # Mock deck with enough cards for 2 players (7 each + 1 starter = 15 minimum)
    mock_deck = [{'suit': 'Spades', 'value': 'Ace'}] * 52
    monkeypatch.setattr(FamilyBlackjackEngine, 'build_deck', lambda self: mock_deck)

    success = game.start_game()

    assert success is True
    assert BOT_NAME in game.players
    assert len(game.players) == 2
    assert len(game.hands['Alice']) == 7
    assert len(game.hands[BOT_NAME]) == 7

def test_add_player_yields_bot_when_lobby_idle():
    game = FamilyBlackjackEngine()
    game.players = ['Alice', BOT_NAME]
    game.hands = {'Alice': [], BOT_NAME: []}
    
    # Alice and Bot are in. Bob joins.
    # add_player should remove bot as lobby is idle.
    yielded = game.add_player('Bob')
    
    assert yielded is True
    assert BOT_NAME not in game.players
    assert 'Bob' in game.players
    assert len(game.players) == 2

def test_start_game_yields_bot_when_observers_waiting(monkeypatch):
    game = FamilyBlackjackEngine()
    game.players = ['Alice', BOT_NAME, 'Bob']
    # Mock deck
    monkeypatch.setattr(FamilyBlackjackEngine, 'build_deck', lambda self: [{'suit': 'Spades', 'value': '3'}] * 52)
    
    # start_game should remove bot because human_players >= 2
    success = game.start_game()
    
    assert success is True
    assert BOT_NAME not in game.players
    assert len(game.players) == 2

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

def test_calculate_awards_logic():
    game = FamilyBlackjackEngine()
    game.players = ['Alice', 'Bob']
    game.start_game()
    
    # Override stats manually to verify the exact logic
    game.match_stats = {
        'Alice': {'cards_played': 12, 'turn_time_total': 30.0, 'turn_count': 10, 'nudges_sent': 1, 'penalties_received': 4, 'power_cards_played': 5},
        'Bob': {'cards_played': 5, 'turn_time_total': 10.0, 'turn_count': 10, 'nudges_sent': 6, 'penalties_received': 0, 'power_cards_played': 2}
    }
    
    awards = game.calculate_awards()
    assert awards['least_cards']['name'] == 'Bob'
    assert awards['quickest']['name'] == 'Bob'
    assert awards['most_nudges']['name'] == 'Bob'
    assert awards['most_penalties']['name'] == 'Alice'
    assert awards['most_power']['name'] == 'Alice'

def test_bot_logic_plays_chain_of_cards():
    import app
    
    game = FamilyBlackjackEngine()
    game.players = ['Alice', BOT_NAME]
    game.is_started = True
    game.hands = {
        'Alice': [{'suit': 'Spades', 'value': 'King'}],
        BOT_NAME: [
            {'suit': 'Spades', 'value': '5'},
            {'suit': 'Hearts', 'value': '5'},
            {'suit': 'Diamonds', 'value': '5'},
            {'suit': 'Clubs', 'value': '8'}
        ]
    }
    game.discard_pile = [{'suit': 'Spades', 'value': '10'}]
    game.current_turn_index = 1
    
    app.game = game
    app.run_bot_logic(BOT_NAME)
    
    assert len(game.hands[BOT_NAME]) == 1
    assert game.hands[BOT_NAME][0]['value'] == '8'
    assert game.current_turn_index == 0 # Turn advanced to Alice

def test_bot_logic_plays_penalty_chain():
    import app
    
    game = FamilyBlackjackEngine()
    game.players = ['Alice', BOT_NAME]
    game.is_started = True
    game.active_penalty_type = '2'
    game.accumulated_penalty = 2
    game.hands = {
        'Alice': [{'suit': 'Diamonds', 'value': '2'}],
        BOT_NAME: [
            {'suit': 'Spades', 'value': '2'},
            {'suit': 'Hearts', 'value': '2'},
            {'suit': 'Diamonds', 'value': '5'}
        ]
    }
    game.discard_pile = [{'suit': 'Clubs', 'value': '2'}]
    game.current_turn_index = 1
    
    app.game = game
    app.run_bot_logic(BOT_NAME)
    
    # Played two 2s
    assert len(game.hands[BOT_NAME]) == 1
    assert game.accumulated_penalty == 6
    assert game.active_penalty_type == '2'

def test_play_joker_reverses_direction_and_sets_cooldown(monkeypatch):
    game = FamilyBlackjackEngine()
    game.players = ['Alice', 'Bob', 'Charlie']
    monkeypatch.setattr(FamilyBlackjackEngine, 'build_deck', lambda self: [{'suit': 'Spades', 'value': '3'}] * 52)
    game.start_game()
    game.current_turn_index = 0  # Alice
    
    assert game.direction == 1
    
    success, msg = game.play_joker('Alice')
    assert success is True
    assert game.direction == -1
    assert game.joker_cooldown == 3
    assert game.jokers_available['Alice'] is False

    # Alice plays a card to advance turn
    game.advance_turn(1)
    assert game.joker_cooldown == 2
    # Turn is now Charlie (since direction is -1: 0 - 1 = -1 -> index 2)
    assert game.players[game.current_turn_index] == 'Charlie'

    success, msg = game.play_joker('Charlie')
    assert success is False
    assert 'cooldown' in msg

def test_play_joker_fails_with_two_players():
    game = FamilyBlackjackEngine()
    game.players = ['Alice', 'Bob']
    game.start_game()
    game.current_turn_index = 0
    success, msg = game.play_joker('Alice')
    assert success is False
    assert '2-player' in msg

def test_play_joker_fails_with_two_active_players_and_spectator():
    game = FamilyBlackjackEngine()
    game.players = ['Alice', 'Bob']
    game.start_game()
    game.current_turn_index = 0
    game.add_player('Charlie')  # Joins mid-game as spectator (0 cards)
    success, msg = game.play_joker('Alice')
    assert success is False
    assert '2-player' in msg

def test_enforce_turn_timer_auto_draws_after_30_seconds():
    game = FamilyBlackjackEngine()
    game.players = ['Alice', 'Bob']
    game.start_game()
    game.current_turn_index = 0
    game.hands = {'Alice': [{'suit': 'Spades', 'value': 'King'}], 'Bob': [{'suit': 'Spades', 'value': 'Queen'}]}
    game.current_turn_start_time = time.time() - 31  # 31 seconds ago
    
    result = game.enforce_turn_timer()
    
    assert result is not None
    assert result['player'] == 'Alice'
    assert result['was_penalty'] is False
    assert len(game.hands['Alice']) == 2
    assert game.current_turn_index == 1

def test_enforce_turn_timer_with_penalty():
    game = FamilyBlackjackEngine()
    game.players = ['Alice', 'Bob']
    game.start_game()
    game.current_turn_index = 0
    game.hands = {'Alice': [{'suit': 'Hearts', 'value': 'Jack'}], 'Bob': [{'suit': 'Spades', 'value': 'Queen'}]}
    game.accumulated_penalty = 5
    game.active_penalty_type = 'BJ'
    game.current_turn_start_time = time.time() - 31
    
    result = game.enforce_turn_timer()
    
    assert result is not None
    assert result['was_penalty'] is True
    assert len(game.hands['Alice']) == 7
    assert game.accumulated_penalty == 0

def test_enforce_turn_timer_draws_all_cards_in_single_call(monkeypatch):
    game = FamilyBlackjackEngine()
    game.players = ['Alice', 'Bob']
    game.start_game()
    game.current_turn_index = 0
    game.hands = {'Alice': [{'suit': 'Hearts', 'value': 'Jack'}], 'Bob': [{'suit': 'Spades', 'value': 'Queen'}]}
    game.accumulated_penalty = 5
    game.active_penalty_type = 'BJ'
    game.current_turn_start_time = time.time() - 31

    draws = []
    original_draw = game.draw_card
    def mock_draw(name, count, reason=None):
        draws.append((name, count, reason))
        return original_draw(name, count, reason)
    monkeypatch.setattr(game, 'draw_card', mock_draw)
    
    game.enforce_turn_timer()
    
    assert len(draws) == 1
    assert draws[0] == ('Alice', 6, 'penalty_timeout')

def test_enforce_turn_timer_with_pending_ace_declaration():
    game = FamilyBlackjackEngine()
    game.players = ['Alice', 'Bob']
    game.start_game()
    game.current_turn_index = 0
    game.hands = {'Alice': [{'suit': 'Spades', 'value': 'King'}], 'Bob': [{'suit': 'Spades', 'value': 'Queen'}]}
    game.discard_pile = [{'suit': 'Diamonds', 'value': 'Ace'}]
    game.declared_ace_suit = None
    game.current_turn_start_time = time.time() - 31
    
    result = game.enforce_turn_timer()
    
    assert result is not None
    assert game.declared_ace_suit == 'Diamonds'


def test_bot_logic_plays_ace_and_declares_suit():
    import app
    
    game = FamilyBlackjackEngine()
    game.players = ['Alice', '🤖 Bot 1']
    game.is_started = True
    game.hands = {
        'Alice': [{'suit': 'Spades', 'value': 'King'}],
        '🤖 Bot 1': [
            {'suit': 'Hearts', 'value': 'Ace'},
            {'suit': 'Clubs', 'value': '2'},
            {'suit': 'Clubs', 'value': '4'}
        ]
    }
    game.discard_pile = [{'suit': 'Diamonds', 'value': '10'}]
    game.current_turn_index = 1
    
    app.game = game
    app.run_bot_logic('🤖 Bot 1')
    
    # Bot should have played the Ace
    assert len(game.hands['🤖 Bot 1']) == 2
    # It should have declared the most common suit in hand (Clubs)
    assert game.declared_ace_suit == 'Clubs'
    assert game.current_turn_index == 0


def test_handle_add_bot_generates_unique_names(monkeypatch):
    import app
    
    game = FamilyBlackjackEngine()
    game.players = ['Alice']
    game.sid_to_name = {'fake_sid': 'Alice'}
    
    app.game = game
    monkeypatch.setattr(app.request, 'sid', 'fake_sid')
    
    app.handle_add_bot()
    assert sum(1 for p in game.players if p.startswith('🤖')) == 1
    
    app.handle_add_bot()
    assert sum(1 for p in game.players if p.startswith('🤖')) == 2
    assert len(game.players) == 3
    
    app.handle_add_bot()
    assert sum(1 for p in game.players if p.startswith('🤖')) == 3
    assert len(game.players) == 4

    emitted = []
    monkeypatch.setattr(app, 'emit', lambda event, data: emitted.append((event, data)))
    
    app.handle_add_bot()
    assert len(emitted) == 1
    assert emitted[0][0] == 'error'
    assert 'Maximum of 3 bots allowed.' in emitted[0][1]['msg']
    assert len(game.players) == 4


def test_bot_logic_draws_fallback_if_play_fails(monkeypatch):
    import app
    
    game = FamilyBlackjackEngine()
    game.players = ['Alice', '🤖 Bot 1']
    game.is_started = True
    game.hands = {
        'Alice': [{'suit': 'Spades', 'value': 'King'}],
        '🤖 Bot 1': [{'suit': 'Spades', 'value': '5'}]
    }
    game.discard_pile = [{'suit': 'Spades', 'value': '10'}]
    game.current_turn_index = 1
    game.deck = [{'suit': 'Hearts', 'value': '7'}]
    
    original_validate = game.validate_and_play_move
    def mock_validate(*args, **kwargs):
        return False, "Forced failure", 0
    monkeypatch.setattr(game, 'validate_and_play_move', mock_validate)
    
    app.game = game
    app.run_bot_logic('🤖 Bot 1')
    
    # Bot should have drawn a card and advanced turn
    assert len(game.hands['🤖 Bot 1']) == 2
    assert game.current_turn_index == 0


def test_bot_logic_plays_joker_and_reverses_direction(monkeypatch):
    import app
    
    game = FamilyBlackjackEngine()
    game.players = ['Alice', '🤖 Bot 1', 'Charlie']
    game.is_started = True
    game.hands = {
        'Alice': [{'suit': 'Spades', 'value': 'King'}],
        '🤖 Bot 1': [{'suit': 'Spades', 'value': '5'}, {'suit': 'Hearts', 'value': '2'}],
        'Charlie': [{'suit': 'Spades', 'value': '4'}]
    }
    game.discard_pile = [{'suit': 'Spades', 'value': '10'}]
    game.current_turn_index = 1
    game.jokers_available = {'🤖 Bot 1': True}
    game.joker_cooldown = 0
    game.direction = 1
    game.deck = [{'suit': 'Clubs', 'value': '3'}] # Ensure fallback draw has a card
    
    # Force random.random to return 0.1 (always play joker)
    monkeypatch.setattr('random.random', lambda: 0.1)
    
    app.game = game
    app.run_bot_logic('🤖 Bot 1')
    
    assert game.direction == -1
    assert not game.jokers_available['🤖 Bot 1']
    assert game.joker_cooldown == 2
    assert game.current_turn_index == 0


def test_multiple_bots_joker_cooldown_ordering(monkeypatch):
    import app
    
    game = FamilyBlackjackEngine()
    game.players = ['Alice', '🤖 Bot 1', '🤖 Bot 2']
    game.is_started = True
    game.hands = {
        'Alice': [{'suit': 'Spades', 'value': 'King'}],
        '🤖 Bot 1': [{'suit': 'Spades', 'value': '8'}, {'suit': 'Hearts', 'value': '2'}],
        '🤖 Bot 2': [{'suit': 'Clubs', 'value': '7'}, {'suit': 'Clubs', 'value': '2'}]
    }
    game.discard_pile = [{'suit': 'Spades', 'value': '10'}]
    game.current_turn_index = 1
    game.jokers_available = {p: True for p in game.players}
    game.joker_cooldown = 0
    game.direction = 1
    game.deck = [{'suit': 'Clubs', 'value': '3'}, {'suit': 'Diamonds', 'value': '4'}]
    
    monkeypatch.setattr('random.random', lambda: 0.1)
    
    app.game = game
    
    # Turn 1: Bot 1 plays Joker (cooldown 3, dir -1). Then plays 8 (skips 1, steps=2).
    # Current index (1) + 2*(-1) = -1 -> 2 (Bot 2)
    # Cooldown decrements by 2 -> 1
    app.run_bot_logic('🤖 Bot 1')
    
    assert game.direction == -1
    assert game.current_turn_index == 2
    assert game.joker_cooldown == 1
    
    # Turn 2: Bot 2 cannot play Joker due to cooldown=1
    app.run_bot_logic('🤖 Bot 2')
    
    assert game.current_turn_index == 1
    assert game.joker_cooldown == 0
    assert game.jokers_available['🤖 Bot 2'] is True
