"""Pytest configuration and fixtures for Family Blackjack integration and browser tests."""

import multiprocessing
import sys
import time
import types
import pytest

# Provide minimal Flask stubs if the environment does not have Flask installed.
if 'flask' not in sys.modules:
    class FlaskStub:
        """Stub for Flask class."""
        def __init__(self, *args, **kwargs):
            self.config = {}

        def route(self, *args, **kwargs):
            """Stub for route decorator."""
            def decorator(fn):
                return fn
            return decorator

        def app_context(self):
            """Stub for app context manager."""
            class AppContextStub:
                def __enter__(self):
                    return self
                def __exit__(self, *args):
                    pass
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
        """Stub for SocketIO class."""
        def __init__(self, *args, **kwargs):
            pass

        def emit(self, *args, **kwargs):
            """Stub for emit method."""
            return None

        def run(self, *args, **kwargs):
            """Stub for run method."""
            return None

        def on(self, *args, **kwargs):
            """Stub for on decorator."""
            def decorator(fn):
                return fn
            return decorator

        def start_background_task(self, task, *args, **kwargs):
            """Stub for start_background_task method."""
            pass

        def sleep(self, seconds):
            """Stub for sleep method."""
            pass

    socketio_stub = types.ModuleType('flask_socketio')
    socketio_stub.SocketIO = SocketIOStub
    socketio_stub.emit = lambda *args, **kwargs: None
    socketio_stub.join_room = lambda *args, **kwargs: None
    sys.modules['flask_socketio'] = socketio_stub


def run_server():
    """Start the Flask-SocketIO live server in a background process.

    We clean mock/stub modules from sys.modules first so the background process
    loads the real Flask and Flask-SocketIO modules instead of test stubs.
    """
    for mod in ['flask', 'flask_socketio', 'app']:
        if mod in sys.modules:
            del sys.modules[mod]
    # pylint: disable=import-outside-toplevel
    from app import app, socketio
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    socketio.run(app, host='127.0.0.1', port=5001, debug=False, use_reloader=False)


@pytest.fixture(scope="session")
def live_server():
    """Session-scoped fixture to launch and clean up the live test server."""
    proc = multiprocessing.Process(target=run_server)
    proc.start()
    time.sleep(2)  # Give the server a moment to start up
    yield "http://127.0.0.1:5001"
    proc.terminate()
    proc.join()