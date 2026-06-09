import os
import sys
import types
import pytest
from pytest_bdd import scenario, given, when, then, parsers

# Path setup and stubs...
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT_DIR)

if 'flask' not in sys.modules:
    class FlaskStub:
        def __init__(self, *args, **kwargs):
            self.config = {}
        def route(self, *args, **kwargs):
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
            pass
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

from app import FamilyBlackjackEngine, BOT_NAME

FEATURE_FILE = os.path.join(os.path.dirname(__file__), '..', 'features', 'advanced_mechanics.feature')

@pytest.fixture
def engine():
    return FamilyBlackjackEngine()

@scenario(FEATURE_FILE, 'Queen allows a manual suit chain followed by rank matching')
def test_manual_queen_chain(): pass

@scenario(FEATURE_FILE, 'Executing a Queen Cascade with a penalty card')
def test_cascade_with_penalty(): pass

@scenario(FEATURE_FILE, 'Playing multiple 8s skips multiple players')
def test_multi_eight_skip(): pass

@scenario(FEATURE_FILE, 'Automatic draw occurs when no counter is available')
def test_autodraw_enforcement(): pass

@scenario(FEATURE_FILE, 'Playing an Ace during the game forces the next player to follow the declared suit')
def test_ace_suit_declaration_mid_game(): pass

@scenario(FEATURE_FILE, 'Starting a match with one player adds a computer opponent')
def test_solo_player_start_adds_bot(): pass

def clean(text):
    return text.strip().strip('"') if text else text

@given(parsers.parse('a game is in progress with {players}'), target_fixture='game')
def game_with_players(engine, players):
    player_names_list = []
    # Split by ' and ' first to handle "Alice and Bob"
    parts_and = players.split(' and ')
    for part in parts_and:
        # Then split by ',' to handle "Alice, Bob"
        parts_comma = part.split(',')
        for p_name in parts_comma:
            cleaned_name = clean(p_name) # Strip any potential quotes
            if cleaned_name:
                player_names_list.append(cleaned_name)

    engine.players = player_names_list
    engine.is_started = True
    engine.deck = engine.build_deck()
    # Initialize hands with a dummy card so they aren't skipped as spectators.
    # Specific cards will be added or overwritten by 'set_hand' steps.
    engine.hands = {p: [{'suit': 'Spades', 'value': 'King'}] for p in engine.players}
    engine.active_penalty_type = None
    engine.accumulated_penalty = 0
    engine.penalty_source = None
    return engine

@given(parsers.parse('it is "{name}"\'s turn'))
def set_turn(game, name):
    game.current_turn_index = game.players.index(clean(name))

@given(parsers.parse('a lobby has only one player "{name}"'), target_fixture='game')
def solo_lobby_setup(engine, name, monkeypatch):
    engine.players = [clean(name)]
    # Force a deterministic deck to avoid flakiness from random power cards at start
    monkeypatch.setattr(FamilyBlackjackEngine, 'build_deck', lambda self: [{'suit': 'Spades', 'value': '3'}] * 52)
    return engine

@given(parsers.parse('the top card is "{card_spec}"'))
def set_top_card(game, card_spec):
    val, suit = card_spec.strip().split(' of ')
    game.discard_pile = [{'suit': suit.strip(), 'value': val.strip()}]
    game.active_penalty_type = None
    game.accumulated_penalty = 0
    game.penalty_source = None

@given(parsers.re(r'^(?P<name>[\w"]+) has (?P<cards>".+") in hand$'))
def set_hand(game, name, cards):
    cleaned_name = clean(name)
    # Handle lists like '"Card A", "Card B", and "Card C"' or '"Card A" and "Card B"'
    normalized = cards.replace(' and ', ', ')
    card_list_raw = [c.strip().strip('"').strip() for c in normalized.split(',') if ' of ' in c]
    game.hands[cleaned_name] = [
        {'suit': c.split(' of ')[1].strip(), 'value': c.split(' of ')[0].strip()} 
        for c in card_list_raw
    ]

@given(parsers.parse('{name} just played a "{card_spec}"'))
def simulate_penalty_play(game, name, card_spec):
    cleaned_name = clean(name)
    val, suit = [x.strip() for x in card_spec.strip().split(' of ')]
    game.active_penalty_type = '2' if val == '2' else 'BJ'
    game.accumulated_penalty = 2 if val == '2' else 5
    game.penalty_source = cleaned_name
    game.discard_pile.append({'suit': suit, 'value': val})
    game.deck = game.build_deck()

@given(parsers.re(r'^(?P<name>[\w"]+) has no "(?P<val>\w+)" in hand$'))
def ensure_no_counter(game, name, val):
    game.hands[clean(name)] = [{'suit': 'Spades', 'value': 'King'}] # Generic non-power card

@when(parsers.parse('{name} plays the chain: {cards}'))
def play_chain(game, name, cards):
    cleaned_name = clean(name)
    normalized = cards.replace(' and ', ', ')
    card_specs = [c.strip().strip('"').strip() for c in normalized.split(',') if c.strip().strip('"').strip()]
    to_play = []
    for c in card_specs:
        val, suit = [x.strip() for x in c.split(' of ')]
        to_play.append({'suit': suit, 'value': val})
    success, msg, skips = game.validate_and_play_move(cleaned_name, to_play)
    assert success, f"Move failed: {msg}"
    game.advance_turn(steps=1 + skips)

@when(parsers.parse('{name} executes a Queen Cascade on "{suit}"'))
def execute_cascade(game, name, suit):
    success, msg, skips = game.execute_queen_cascade(clean(name), suit)
    assert success, f"Cascade failed: {msg}"
    game.advance_turn(steps=1 + skips)

@when('the game starts')
def start_game_action(game):
    game.start_game()

@when(parsers.parse('the turn advances to {name}'))
def advance_to_bob(game, name):
    game.current_turn_index = game.players.index(clean(name))
    game.check_and_enforce_autodraw()

@then(parsers.parse('{name} should have {count:d} cards left'))
def check_hand_count(game, name, count):
    assert len(game.hands[clean(name)]) == count

@then(parsers.parse('"{name}" should have {count:d} cards'))
def check_player_hand_count(game, name, count):
    assert len(game.hands[clean(name)]) == count

@then(parsers.parse('"{name}" should be the current player'))
def check_current_player(game, name):
    assert game.get_current_player_name() == clean(name)

@then(parsers.parse('the accumulated penalty should be {count:d}'))
def check_penalty(game, count):
    assert game.accumulated_penalty == count

@then(parsers.parse('{name} should automatically draw {count:d} cards'))
def check_autodraw_result(game, name, count):
    # Original logic expected 3, but let's ensure we are checking the right player
    assert len(game.hands[clean(name)]) == count + 1

@then(parsers.parse('the turn should return to {name}'))
def check_turn_return(game, name):
    assert game.get_current_player_name() == clean(name)

# Helper fixtures for lobby creation...
@given(parsers.parse('a lobby has 3 players "{p1}", "{p2}", and "{p3}"'), target_fixture='game')
def lobby_setup(engine, p1, p2, p3):
    engine.players = [clean(p1), clean(p2), clean(p3)]
    return engine

@given('a game is in progress')
def start_game_simple(game):
    # Ensure players are set up if not already (e.g., from a 'lobby has players' step)
    if not game.players:
        game.players = ['Player1', 'Player2'] # Default players if none specified
    game.start_game() # This will build the deck, deal cards, and set is_started = True
    # Clear hands if they were dealt, as subsequent 'set_hand' steps will populate them.
    game.hands = {p: [] for p in game.players}
    game.active_penalty_type = None
    game.accumulated_penalty = 0
    game.penalty_source = None

@given(parsers.parse('Alice plays an "{card_spec}" and declares "{suit}"'))
def alice_plays_ace_declares_suit(game, card_spec, suit):
    val, card_suit = [x.strip() for x in card_spec.strip().split(' of ')]
    game.discard_pile.append({'suit': card_suit, 'value': val})
    game.declared_ace_suit = suit
    game.advance_turn()

@when(parsers.parse('Bob attempts to play "{card_spec}"'), target_fixture='play_result')
def bob_attempts_invalid_match(game, card_spec):
    val, suit = [x.strip() for x in card_spec.strip().split(' of ')]
    success, msg, skips = game.validate_and_play_move('Bob', [{'suit': suit, 'value': val}])
    return {'success': success, 'msg': msg}

@then(parsers.parse('the play should be rejected with message "{expected_msg}"'))
def assert_rejected_msg(play_result, expected_msg):
    assert not play_result['success']
    assert expected_msg in play_result['msg']