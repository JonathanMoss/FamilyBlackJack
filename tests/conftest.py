import os
import sys
import types

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

import pytest
import app

@pytest.fixture
def lobby_with_two_players():
    game = app.FamilyBlackjackEngine()
    game.add_player("Alice")
    game.add_player("Bob")
    return game