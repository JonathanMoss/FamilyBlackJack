import os
import sys
import types

from pytest_bdd import scenario, given, when, then

# Add project root to import path so app.py can be imported.
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT_DIR)

# Provide minimal Flask stubs if the environment does not have Flask installed.
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

from app import FamilyBlackjackEngine

FEATURE_FILE = os.path.join(os.path.dirname(__file__), '..', 'features', 'first_card_start.feature')

# Each scenario is bound to the Gherkin scenarios in the feature file.
@scenario(FEATURE_FILE, 'Ace starter prompts the first player for suit declaration')
def test_ace_starter_prompts_suit():
    pass

@scenario(FEATURE_FILE, 'Two starter applies the +2 penalty to the first player')
def test_two_starter_applies_penalty():
    pass

@scenario(FEATURE_FILE, 'Black Jack starter applies the +5 BJ penalty to the first player')
def test_black_jack_starter_applies_penalty():
    pass

@scenario(FEATURE_FILE, 'Red Jack starter does not apply a BJ penalty')
def test_red_jack_starter_no_penalty():
    pass

@scenario(FEATURE_FILE, 'An 8 card as the starter card applies the miss-turn penalty to the first player')
def test_eight_starter_skips_first_player():
    pass


@given('a lobby has players "Alice" and "Bob"', target_fixture='lobby_with_two_players')
def lobby_with_two_players():
    # Create a fresh engine instance with two players in order.
    engine = FamilyBlackjackEngine()
    engine.players = ['Alice', 'Bob']
    return engine


@given('the first discard card is "Ace of Spades"', target_fixture='first_card')
def first_card_ace():
    return {'suit': 'Spades', 'value': 'Ace'}


@given('the first discard card is "2 of Diamonds"', target_fixture='first_card')
def first_card_two():
    return {'suit': 'Diamonds', 'value': '2'}


@given('the first discard card is "Jack of Spades"', target_fixture='first_card')
def first_card_black_jack():
    return {'suit': 'Spades', 'value': 'Jack'}


@given('the first discard card is "8 of Spades"', target_fixture='first_card')
def first_card_eight():
    return {'suit': 'Spades', 'value': '8'}


@given('the first discard card is "Jack of Hearts"', target_fixture='first_card')
def first_card_red_jack():
    return {'suit': 'Hearts', 'value': 'Jack'}


@when('the game starts', target_fixture='start_game')
def start_game(lobby_with_two_players, first_card, monkeypatch):
    engine = lobby_with_two_players

    # Override the deck builder so the first discard card is the starter card.
    def build_deck_override(self):
        all_cards = [
            {'suit': suit, 'value': value}
            for suit in ['Hearts', 'Diamonds', 'Clubs', 'Spades']
            for value in ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'Jack', 'Queen', 'King', 'Ace']
        ]
        # Remove the card we want to start with from the generated deck.
        available = [card for card in all_cards if card != first_card]
        # Determine the starter position after dealing 7 cards to each player.
        starter_index = len(available) - len(engine.players) * 7
        available.insert(starter_index, first_card)
        return available

    monkeypatch.setattr(FamilyBlackjackEngine, 'build_deck', build_deck_override)
    engine.start_game()
    return engine


@then('the first player should be prompted to declare the active suit')
def assert_prompt_for_suit(start_game):
    engine = start_game
    # In the current design, a starting Ace should leave a blank active penalty and
    # require suit declaration from the first player. The prompt behavior is handled
    # at the socket/event layer, so here we assert the main engine flag state.
    assert engine.discard_pile[-1]['value'] == 'Ace'
    assert engine.active_penalty_type is None


@then('the game should not have an active penalty')
def assert_no_penalty(start_game):
    engine = start_game
    assert engine.active_penalty_type is None
    assert engine.accumulated_penalty == 0


@then('the first player should face a 2-card penalty')
def assert_two_penalty(start_game):
    engine = start_game
    assert engine.active_penalty_type == '2'
    assert engine.accumulated_penalty == 2


@then('the first player should face a 5-card BJ penalty')
def assert_bj_penalty(start_game):
    engine = start_game
    assert engine.active_penalty_type == 'BJ'
    assert engine.accumulated_penalty == 5


@then('the penalty type should be "2"')
def assert_penalty_type_two(start_game):
    engine = start_game
    assert engine.active_penalty_type == '2'


@then('the penalty type should be "BJ"')
def assert_penalty_type_bj(start_game):
    engine = start_game
    assert engine.active_penalty_type == 'BJ'

@then('the first player "Bob" should be skipped')
def assert_bob_skipped(start_game):
    # In this context, Alice is dealer (0), Bob is first (1). 
    # If Bob is skipped, the turn index returns to Alice (0).
    assert start_game.current_turn_index == 0

@then('"Alice" should be the current player')
def assert_alice_current(start_game):
    assert start_game.get_current_player_name() == 'Alice'
