import os
import sys
import types

from pytest_bdd import parsers, scenario, given, when, then

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
    flask_stub.redirect = lambda *args, **kwargs: ''
    flask_stub.url_for = lambda *args, **kwargs: ''
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

FEATURE_FILE = os.path.join(os.path.dirname(__file__), '..', 'features', 'alternate_dealers.feature')

@scenario(FEATURE_FILE, 'Game 1 selects the next player after the Dealer as starting player')
def test_game_one_rotates_dealer_and_first_player():
    pass


@scenario(FEATURE_FILE, 'Game 2 rotates dealer to the other player')
def test_game_two_rotates_dealer_to_other_player():
    pass


@scenario(FEATURE_FILE, 'Game 1 selects the next player after the Dealer in a 3-player lobby')
def test_game_one_rotates_dealer_in_three_player_lobby():
    pass


@scenario(FEATURE_FILE, 'Game 2 rotates dealer to the next player in a 3-player lobby')
def test_game_two_rotates_dealer_in_three_player_lobby():
    pass


@scenario(FEATURE_FILE, 'Game 3 cycles dealer back to first player in a 2-player lobby')
def test_game_three_cycles_dealer_in_two_player_lobby():
    pass


@scenario(FEATURE_FILE, 'Game 3 cycles dealer back to first player in a 3-player lobby')
def test_game_three_cycles_dealer_in_three_player_lobby():
    pass


@given(parsers.parse('a lobby has 2 players "{player1}" and "{player2}"'), target_fixture='lobby')
@given(parsers.parse('a lobby has 3 players "{player1}", "{player2}", and "{player3}"'), target_fixture='lobby')
def lobby(player1, player2, player3=None):
    engine = FamilyBlackjackEngine()
    if player3 is None:
        engine.players = [player1, player2]
    else:
        engine.players = [player1, player2, player3]
    return engine


@when('the game starts', target_fixture='start_game')
def start_game(lobby, monkeypatch):
    engine = lobby

    def build_deck_override(self):
        ordered_deck = [
            {'suit': suit, 'value': value}
            for suit in ['Hearts', 'Diamonds', 'Clubs', 'Spades']
            for value in ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'Jack', 'Queen', 'King', 'Ace']
        ]
        return ordered_deck

    monkeypatch.setattr(FamilyBlackjackEngine, 'build_deck', build_deck_override)
    engine.start_game()
    return engine


@when('the next game starts', target_fixture='start_second_game')
def start_second_game(start_game, monkeypatch):
    engine = start_game

    def build_deck_override(self):
        ordered_deck = [
            {'suit': suit, 'value': value}
            for suit in ['Hearts', 'Diamonds', 'Clubs', 'Spades']
            for value in ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'Jack', 'Queen', 'King', 'Ace']
        ]
        return ordered_deck

    monkeypatch.setattr(FamilyBlackjackEngine, 'build_deck', build_deck_override)
    engine.start_game()
    return engine


@when('the third game starts', target_fixture='start_third_game')
def start_third_game(start_second_game, monkeypatch):
    engine = start_second_game

    def build_deck_override(self):
        ordered_deck = [
            {'suit': suit, 'value': value}
            for suit in ['Hearts', 'Diamonds', 'Clubs', 'Spades']
            for value in ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'Jack', 'Queen', 'King', 'Ace']
        ]
        return ordered_deck

    monkeypatch.setattr(FamilyBlackjackEngine, 'build_deck', build_deck_override)
    engine.start_game()
    return engine


@then(parsers.parse('{dealer} is selected as Dealer'))
def assert_selected_dealer(start_game, dealer):
    engine = start_game
    assert engine.players[engine.match_dealer_index] == dealer


@then(parsers.parse('{first_player} is selected as first player'))
def assert_selected_first_player(start_game, first_player):
    engine = start_game
    assert engine.current_turn_index == (engine.match_dealer_index + 1) % len(engine.players)
    assert engine.players[engine.current_turn_index] == first_player


@then(parsers.parse('{dealer} is selected as Dealer after the second game'))
def assert_selected_dealer_second_game(start_second_game, dealer):
    engine = start_second_game
    assert engine.players[engine.match_dealer_index] == dealer


@then(parsers.parse('{first_player} is selected as first player after the second game'))
def assert_selected_first_player_second_game(start_second_game, first_player):
    engine = start_second_game
    assert engine.current_turn_index == (engine.match_dealer_index + 1) % len(engine.players)
    assert engine.players[engine.current_turn_index] == first_player


@then(parsers.parse('{dealer} is selected as Dealer after the third game'))
def assert_selected_dealer_third_game(start_third_game, dealer):
    engine = start_third_game
    assert engine.players[engine.match_dealer_index] == dealer


@then(parsers.parse('{first_player} is selected as first player after the third game'))
def assert_selected_first_player_third_game(start_third_game, first_player):
    engine = start_third_game
    assert engine.current_turn_index == (engine.match_dealer_index + 1) % len(engine.players)
    assert engine.players[engine.current_turn_index] == first_player
