"""Start the mock SaaS API on an ephemeral localhost port for tests."""

import threading

from werkzeug.serving import make_server

from connectors.mock_server import create_app


class MockServer:
    def __init__(self, **kwargs):
        self.app = create_app(**kwargs)
        self.server = make_server("127.0.0.1", 0, self.app)
        self.port = self.server.server_port
        self.thread = threading.Thread(
            target=self.server.serve_forever, daemon=True
        )

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.thread.join(timeout=5)
        return False

    @property
    def base_url(self):
        return f"http://127.0.0.1:{self.port}"
