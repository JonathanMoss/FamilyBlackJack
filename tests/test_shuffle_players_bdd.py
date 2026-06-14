import os
import sys
import types
import pytest
from pytest_bdd import scenario, given, when, then, parsers

# Path setup and stubs...
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT_DIR)

from game_engine import FamilyBlackjackEngine
import app

FEATURE_FILE = os.path.join(os.path.dirname(__file__), '..', 'features', 'shuffle_players.feature')

@scenario(FEATURE_FILE, 'A player shuffles the lobby successfully')
def test_shuffle_success():
    pass

@scenario(FEATURE_FILE, 'A player cannot shuffle an active game')
def test_shuffle_active_game():
    pass

@pytest.fixture
def event_catcher(monkeypatch):
    """Fixture to intercept and record emitted SocketIO events."""
    events = []
    def catch_emit(event, data, **kwargs):
        events.append((event, data))
    monkeypatch.setattr(app, 'emit', catch_emit)
    monkeypatch.setattr(app.socketio, 'emit', catch_emit)
    return events

@given(parsers.parse('a lobby has players "{p1}", "{p2}", and "{p3}"'), target_fixture='game_setup')
def setup_lobby(p1, p2, p3):
    game = FamilyBlackjackEngine()
    game.add_player(p1)
    game.add_player(p2)
    game.add_player(p3)
    game.sid_to_name = {'sid_1': p1, 'sid_2': p2, 'sid_3': p3}
    app.game = game
    return game

@given('the game has started')
def start_game(game_setup):
    game_setup.is_started = True

@when(parsers.parse('"{name}" requests to shuffle the players'))
def request_shuffle(game_setup, name, monkeypatch, event_catcher):
    sid = next(s for s, n in game_setup.sid_to_name.items() if n == name)
    monkeypatch.setattr(app.request, 'sid', sid)
    # Mock random.shuffle to simply reverse the list so it is deterministic for assertions
    monkeypatch.setattr(app.random, 'shuffle', lambda lst: lst.reverse())
    app.handle_shuffle_players()

@then('the player order should be randomized')
def verify_shuffled(game_setup):
    assert game_setup.players == ["Charlie", "Bob", "Alice"]

@then('a game log message should announce the shuffle')
def verify_success_log(event_catcher):
    logs = [data['msg'] for event, data in event_catcher if event == 'game_log']
    assert any("shuffled the player order" in msg for msg in logs)

@then('the shuffle should be rejected with an error message')
def verify_error_msg(event_catcher):
    errors = [data['msg'] for event, data in event_catcher if event == 'error']
    assert any("Cannot shuffle players while a match is in progress" in msg for msg in errors)