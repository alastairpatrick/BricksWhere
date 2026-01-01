"""Simple local static file server used in developer mode.

Provides a tiny HTTP server serving files from a directory on localhost on a
random available port. The server runs in a background thread and can be
stopped cleanly from tests.
"""
import http.server
import socketserver
import threading
import socket
from functools import partial
from typing import Optional


class DevHTTPServer:
    def __init__(self, directory: str, host: str = '127.0.0.1', port: int = 0):
        self.directory = directory
        self.host = host
        self.port = port
        self._server: Optional[socketserver.TCPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self):
        handler = partial(http.server.SimpleHTTPRequestHandler, directory=self.directory)

        # Use TCPServer directly to allow binding to port 0 (auto-assign)
        class _TCPServer(socketserver.TCPServer):
            allow_reuse_address = True

        # bind to host and port 0 to choose a free port
        self._server = _TCPServer((self.host, self.port), handler)
        addr, port = self._server.server_address
        self.port = port

        def serve():
            try:
                self._server.serve_forever()
            except Exception:
                pass

        self._thread = threading.Thread(target=serve, daemon=True)
        self._thread.start()

    def stop(self):
        if self._server:
            try:
                self._server.shutdown()
            except Exception:
                pass
            try:
                self._server.server_close()
            except Exception:
                pass
            self._server = None
        if self._thread:
            try:
                self._thread.join(timeout=1.0)
            except Exception:
                pass
            self._thread = None

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}/"
