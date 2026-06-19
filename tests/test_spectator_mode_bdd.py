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
        def app_context(self):
            class AppContextStub:
                def __enter__(self): return self
                def __exit__(self, *args): pass
            return AppContextStub()

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
        def start_background_task(self, task, *args, **kwargs):
            pass
        def sleep(self, seconds):
            pass

    socketio_stub = types.ModuleType('flask_socketio')
    socketio_stub.SocketIO = SocketIOStub
    socketio_stub.emit = lambda *args, **kwargs: None
    socketio_stub.join_room = lambda *args, **kwargs: None
    sys.modules['flask_socketio'] = socketio_stub

from game_engine import FamilyBlackjackEngine
import app

FEATURE_FILE = os.path.join(os.path.dirname(__file__), '..', 'features', 'spectator_mode.feature')

@scenario(FEATURE_FILE, 'Human players remain as spectators when a Demo Game starts')
def test_human_spectator_demo():
    pass

@scenario(FEATURE_FILE, 'Spectators do not receive a loss when a match ends')
def test_spectator_no_loss():
    pass

@given(parsers.parse('a lobby has a human player "{name}"'), target_fixture='game_demo')
def setup_lobby_human(name, monkeypatch):
    game = FamilyBlackjackEngine()
    game.add_player(name)
    game.sid_to_name = {'fake_sid': name}
    app.game = game
    monkeypatch.setattr(app.request, 'sid', 'fake_sid')
    return game

@when('a Demo Game is started')
def start_demo_game(game_demo):
    app.handle_start_demo()

@then(parsers.parse('"{name}" should still be in the lobby'))
def check_player_in_lobby(game_demo, name):
    assert name in game_demo.players

@then(parsers.parse('"{name}" should have 0 cards'))
def check_player_zero_cards(game_demo, name):
    assert len(game_demo.hands.get(name, [])) == 0

@then('the lobby should contain 3 bots')
def check_three_bots(game_demo):
    bots = [p for p in game_demo.players if game_demo.is_bot(p)]
    assert len(bots) == 3

@given(parsers.parse('a lobby has active players "{p1}" and "{p2}"'), target_fixture='game_active')
def setup_active_players(p1, p2):
    game = FamilyBlackjackEngine()
    game.players = [p1, p2]
    game.hands = {p1: [], p2: []}
    return game

@given('the game has started')
def start_match(game_active):
    game_active.start_game()

@when(parsers.parse('"{name}" joins as a spectator'))
def join_spectator(game_active, name):
    game_active.add_player(name)

@when(parsers.parse('the game calculates league results with winner "{winner}"'))
def calc_results(game_active, winner):
    game_active.update_league_results(winner)

@then(parsers.parse('"{name}" should have {count:d} win'))
def check_wins(game_active, name, count):
    assert game_active.league_wins.get(name, 0) == count

@then(parsers.parse('"{name}" should have {count:d} loss'))
def check_loss(game_active, name, count):
    assert game_active.league_losses.get(name, 0) == count

@then(parsers.parse('"{name}" should have {count:d} losses'))
def check_losses(game_active, name, count):
    assert game_active.league_losses.get(name, 0) == count