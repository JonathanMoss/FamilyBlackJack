import os
import sys
import pytest
from pytest_bdd import scenario, given, when, then, parsers

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT_DIR)

from game_engine import FamilyBlackjackEngine
import app

FEATURE_FILE = os.path.join(os.path.dirname(__file__), '..', 'features', 'bot_dialogue.feature')

@scenario(FEATURE_FILE, 'A bot plays a card and logs a play dialogue')
def test_bot_play_dialogue():
    pass

@scenario(FEATURE_FILE, 'A player nudges a bot and the bot responds')
def test_bot_nudge_dialogue():
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

@given(parsers.parse('a lobby has players "{p1}" and "{p2}"'), target_fixture='game_setup')
def setup_lobby(p1, p2):
    game = FamilyBlackjackEngine()
    game.reset_lobby()
    game.add_player(p1)
    game.add_player(p2)
    game.sid_to_name = {'sid_1': p1, 'sid_2': p2}
    game.name_to_sid = {p1: 'sid_1', p2: 'sid_2'}
    app.game = game
    return game

@given(parsers.parse('"{bot_name}" is registered as a bot'))
def register_bot(game_setup, bot_name):
    game_setup.bots.add(bot_name)

@given('the game has started')
def start_game(game_setup):
    game_setup.is_started = True

@given(parsers.parse('it is "{player_name}"\'s turn'))
def set_turn(game_setup, player_name):
    idx = game_setup.players.index(player_name)
    game_setup.current_turn_index = idx

@when(parsers.parse('the bot "{bot_name}" plays a valid card'))
def bot_plays_card(game_setup, bot_name, monkeypatch, event_catcher):
    # Mock to make bot execution run synchronously and cleanly
    monkeypatch.setattr(game_setup, 'validate_and_play_move', lambda name, play: (True, "success", 0))
    game_setup.hands = {bot_name: [{'value': '8', 'suit': 'Clubs'}]}
    game_setup.discard_pile = [{'value': '8', 'suit': 'Hearts'}]
    
    # Run the bot logic loop for playing cards
    app.run_bot_logic(bot_name)

@when(parsers.parse('"{sender}" nudges "{target}"'))
def nudge_player(game_setup, sender, target, monkeypatch, event_catcher):
    sid = next(s for s, n in game_setup.sid_to_name.items() if n == sender)
    monkeypatch.setattr(app.request, 'sid', sid)
    app.handle_nudge({'target': target, 'emoji': '⏰'})

@then(parsers.parse('the game log should contain a dialogue message from "{bot_name}"'))
def verify_bot_dialogue(event_catcher, bot_name):
    logs = [data['msg'] for event, data in event_catcher if event == 'game_log']
    prefix = f"💬 <b>{bot_name}</b>:"
    assert any(prefix in msg for msg in logs), f"Expected bot dialogue prefix '{prefix}' not found in logs: {logs}"

@then(parsers.parse('the game log should contain a nudge dialogue message from "{bot_name}"'))
def verify_bot_nudge_dialogue(event_catcher, bot_name):
    logs = [data['msg'] for event, data in event_catcher if event == 'game_log']
    prefix = f"💬 <b>{bot_name}</b>:"
    assert any(prefix in msg for msg in logs), f"Expected nudge dialogue prefix '{prefix}' not found in logs: {logs}"
