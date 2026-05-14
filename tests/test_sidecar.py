"""Tests for the Option C sidecar: socket_listener, daemon, kafka_publisher."""

from __future__ import annotations

import json
import socket
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock


from omnicursor.drainer.loop import drain_loop, drain_once
from omnicursor.drainer.publisher import CountingPublisher, NoopPublisher, PublishCounter
from omnicursor.drainer.kafka_publisher import KafkaPublisher, topics_for
from omnicursor.sidecar.socket_listener import start as start_listener
from omnicursor.sidecar.status_server import start_status_server


# ---------------------------------------------------------------------------
# KafkaPublisher — unit tests (confluent-kafka mocked)
# ---------------------------------------------------------------------------

class TestKafkaPublisher:
    def _make_mock_producer(self):
        p = mock.MagicMock()
        p.produce = mock.MagicMock()
        p.poll = mock.MagicMock()
        p.flush = mock.MagicMock()
        return p

    def test_topics_for_known_event(self):
        topics = topics_for("session.outcome")
        assert "onex.cmd.omniintelligence.session-outcome.v1" in topics
        assert "onex.evt.omnicursor.session-outcome.v1" in topics

    def test_topics_for_utilization(self):
        topics = topics_for("utilization.scoring.requested")
        assert "onex.cmd.omniintelligence.utilization-scoring.v1" in topics

    def test_topics_for_unknown_returns_empty(self):
        assert topics_for("unknown.event") == []

    def test_publish_unknown_event_returns_false(self):
        pub = KafkaPublisher.__new__(KafkaPublisher)
        pub._bootstrap = "localhost:29092"
        pub._log = mock.MagicMock()
        pub._producer = self._make_mock_producer()
        pub._available = True
        result = pub.publish("unknown.event", {"session_id": "s1"})
        assert result is False

    def test_publish_produces_to_all_topics(self):
        pub = KafkaPublisher.__new__(KafkaPublisher)
        pub._bootstrap = "localhost:29092"
        pub._log = mock.MagicMock()
        mock_producer = self._make_mock_producer()
        pub._producer = mock_producer
        pub._available = True

        result = pub.publish("session.outcome", {"session_id": "s1", "outcome": "success"})
        assert result is True
        assert mock_producer.produce.call_count == 2  # two topics for session.outcome
        topics_called = [call.args[0] for call in mock_producer.produce.call_args_list]
        assert "onex.cmd.omniintelligence.session-outcome.v1" in topics_called
        assert "onex.evt.omnicursor.session-outcome.v1" in topics_called

    def test_publish_missing_confluent_kafka_returns_false(self):
        pub = KafkaPublisher(bootstrap_servers="localhost:29092")
        with mock.patch.dict("sys.modules", {"confluent_kafka": None}):
            # Reset so _get_producer retries import
            pub._producer = None
            pub._available = None
            with mock.patch("builtins.__import__", side_effect=ImportError("no module")):
                result = pub.publish("session.outcome", {"session_id": "s1"})
        assert result is False

    def test_flush_calls_producer_flush(self):
        pub = KafkaPublisher.__new__(KafkaPublisher)
        pub._log = mock.MagicMock()
        mock_producer = self._make_mock_producer()
        pub._producer = mock_producer
        pub.flush(timeout_s=1.0)
        mock_producer.flush.assert_called_once_with(timeout=1.0)

    def test_flush_no_producer_is_noop(self):
        pub = KafkaPublisher.__new__(KafkaPublisher)
        pub._log = mock.MagicMock()
        pub._producer = None
        pub.flush()  # should not raise


# ---------------------------------------------------------------------------
# socket_listener — integration tests
# ---------------------------------------------------------------------------

class TestSocketListener:
    def _send(self, sock_path: Path, msg: dict, timeout: float = 2.0) -> dict:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect(str(sock_path))
        s.sendall((json.dumps(msg) + "\n").encode())
        raw = s.recv(4096)
        s.close()
        return json.loads(raw.decode())

    def test_ping_returns_ok(self, tmp_path: Path) -> None:
        sock_path = tmp_path / "test.sock"
        outbox = tmp_path / "outbox.jsonl"
        stop = threading.Event()
        start_listener(socket_path=sock_path, outbox_path=outbox, stop_event=stop)
        time.sleep(0.05)

        reply = self._send(sock_path, {"command": "ping"})
        assert reply["status"] == "ok"
        stop.set()

    def test_event_appended_to_outbox(self, tmp_path: Path) -> None:
        sock_path = tmp_path / "test.sock"
        outbox = tmp_path / "outbox.jsonl"
        stop = threading.Event()
        start_listener(socket_path=sock_path, outbox_path=outbox, stop_event=stop)
        time.sleep(0.05)

        payload = {"session_id": "s-test", "outcome": "success"}
        reply = self._send(sock_path, {"event_type": "session.outcome", "payload": payload})
        assert reply["status"] == "queued"
        assert "event_id" in reply

        time.sleep(0.05)
        lines = [json.loads(line) for line in outbox.read_text().splitlines() if line]
        assert len(lines) == 1
        assert lines[0]["event_type"] == "session.outcome"
        assert lines[0]["payload"]["session_id"] == "s-test"
        stop.set()

    def test_multiple_events_all_appended(self, tmp_path: Path) -> None:
        sock_path = tmp_path / "test.sock"
        outbox = tmp_path / "outbox.jsonl"
        stop = threading.Event()
        start_listener(socket_path=sock_path, outbox_path=outbox, stop_event=stop)
        time.sleep(0.05)

        for i in range(3):
            self._send(sock_path, {"event_type": "session.outcome", "payload": {"session_id": f"s-{i}"}})

        time.sleep(0.1)
        lines = [json.loads(line) for line in outbox.read_text().splitlines() if line]
        assert len(lines) == 3
        stop.set()

    def test_stale_socket_file_removed_on_start(self, tmp_path: Path) -> None:
        sock_path = tmp_path / "stale.sock"
        sock_path.write_text("stale")  # simulate leftover file
        outbox = tmp_path / "outbox.jsonl"
        stop = threading.Event()
        start_listener(socket_path=sock_path, outbox_path=outbox, stop_event=stop)
        time.sleep(0.05)
        reply = self._send(sock_path, {"command": "ping"})
        assert reply["status"] == "ok"
        stop.set()


# ---------------------------------------------------------------------------
# drain_loop stop_event — ensure it terminates cleanly
# ---------------------------------------------------------------------------

class TestDrainLoopStopEvent:
    def test_stop_event_terminates_loop(self, tmp_path: Path) -> None:
        outbox = tmp_path / "outbox.jsonl"
        cursor = tmp_path / "cursor"
        pub = NoopPublisher()
        stop = threading.Event()

        t = threading.Thread(
            target=drain_loop,
            kwargs={
                "publisher": pub,
                "outbox_path": outbox,
                "cursor_path": cursor,
                "interval_s": 0.1,
                "stop_event": stop,
            },
            daemon=True,
        )
        t.start()
        time.sleep(0.15)
        stop.set()
        t.join(timeout=2.0)
        assert not t.is_alive(), "drain_loop did not terminate after stop_event"


# ---------------------------------------------------------------------------
# GET /status — metrics HTTP
# ---------------------------------------------------------------------------


class TestStatusHTTP:
    def test_get_status_returns_metrics_json(self, tmp_path: Path) -> None:
        cursor = tmp_path / "sidecar.cursor"
        cursor.write_text("42\n")
        counter = PublishCounter()
        counter.record(5)
        server, _thread = start_status_server(
            port=0,
            publisher_mode="noop",
            cursor_path=cursor,
            publish_counter=counter,
        )
        assert server is not None
        bound_port = server.server_address[1]
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{bound_port}/status", timeout=3
            ) as resp:
                assert resp.status == 200
                body = json.loads(resp.read().decode())
        finally:
            server.shutdown()
            server.server_close()

        assert body == {
            "publisher_mode": "noop",
            "outbox_offset": 42,
            "events_published": 5,
        }

    def test_status_unknown_path_is_404(self, tmp_path: Path) -> None:
        counter = PublishCounter()
        server, _thread = start_status_server(
            port=0,
            publisher_mode="kafka",
            cursor_path=tmp_path / "c",
            publish_counter=counter,
        )
        assert server is not None
        bound_port = server.server_address[1]
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{bound_port}/nope", timeout=3
            ):
                pass
            raise AssertionError("expected HTTPError")
        except urllib.error.HTTPError as exc:
            assert exc.code == 404
        finally:
            server.shutdown()
            server.server_close()


class TestCountingPublisher:
    def test_counting_publisher_increments_on_successful_publish(self, tmp_path: Path) -> None:
        outbox = tmp_path / "outbox.jsonl"
        cursor = tmp_path / "cursor"
        row = {
            "schema_version": "omnicursor.session_outcome.v1",
            "session_outcome": "success",
            "session_outcome_reason": "test",
            "conversation_id": "conv-1",
            "correlation_id": "corr-1",
        }
        outbox.write_text(json.dumps(row) + "\n")
        ctr = PublishCounter()
        inner = NoopPublisher()
        pub = CountingPublisher(inner, ctr)
        drain_once(pub, outbox_path=outbox, cursor_path=cursor)
        assert ctr.value() == 1
        assert len(inner.events) == 1
