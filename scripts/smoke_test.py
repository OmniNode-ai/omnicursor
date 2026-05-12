#!/usr/bin/env python3
"""Level 2 smoke test: fire a test event at the sidecar socket and print the response."""
import json
import pathlib
import socket

sock_path = str(pathlib.Path.home() / ".omnicursor" / "emit.sock")
msg = {
    "event_type": "session.outcome",
    "payload": {
        "session_id": "test-1",
        "outcome": "success",
        "matched_agent": "debugging-agent",
    },
}

s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.connect(sock_path)
s.sendall((json.dumps(msg) + "\n").encode())
print(s.recv(256).decode())
s.close()
