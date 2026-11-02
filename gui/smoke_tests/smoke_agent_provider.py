"""Real loopback transport/OS vault evidence; no GUI, cloud or Geant4 runs."""
from __future__ import annotations

from dataclasses import asdict, replace
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import socket
import socketserver
import sys
import threading
import time
import traceback
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "gui"))
from g4usim_gui.agent import CredentialError, CredentialStore, ProviderClient, ProviderConfig, ProviderError
from g4usim_gui.agent import credentials as credential_module, provider as provider_module

MESSAGES = [{"role": "user", "content": '请返回一个 JSON planning object for an empty context.'}]
RESULTS = {}


def envelope(content='{"plan":[]}', **changes):
    value = {"model": "fixture-model", "choices": [{"index": 0, "finish_reason": "stop",
        "message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5}}
    value.update(changes)
    return value


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def do_POST(self):
        server = self.server
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        authorization = self.headers.get("Authorization", "")
        server.seen.append({"path": self.path, "auth_present": bool(authorization),
            "auth_matches": authorization == "Bearer " + server.secret,
            "payload": json.loads(body)})
        mode = server.mode
        data = envelope()
        if mode == "bad_content":
            data = envelope("broken JSON")
        elif mode == "duplicate_content":
            data = envelope('{"plan":[],"plan":[]}')
        elif mode == "nonfinite":
            data = envelope('{"number":NaN}')
        elif mode == "overflow":
            data = envelope('{"number":1e999}')
        elif mode == "surrogate":
            data = envelope('{"bad":"\\ud800"}')
        elif mode == "array":
            data = envelope("[]")
        elif mode == "truncated":
            data["choices"][0]["finish_reason"] = "length"
        elif mode == "tools":
            data["choices"][0]["message"]["tool_calls"] = [{"type": "function"}]
        elif mode == "secret_echo":
            data = envelope(json.dumps({"echo": server.secret}))
        elif mode == "escaped_secret_echo":
            escaped = "".join("\\u%04x" % ord(c) for c in server.secret)
            data = envelope('{"echo":"' + escaped + '"}')
        raw = json.dumps(data).encode("utf-8")
        if mode == "bad_envelope":
            raw = b"not JSON"
        elif mode == "duplicate_envelope":
            raw = b'{"choices":[],"choices":[]}'
        elif mode == "bad_utf8":
            raw = b"\xff"
        elif mode == "oversize_actual":
            raw = b" " * 4096
        if mode != "slow_body":
            server.entered.set()
        try:
            if mode == "slow_headers":
                server.release.wait(5)
                self.connection.settimeout(1)
                try:
                    server.disconnected = not self.connection.recv(1)
                except OSError:
                    server.disconnected = True
                return
            if mode == "redirect":
                self.send_response(307)
                self.send_header("Location", server.redirect + "?key=" + server.secret)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self.send_response(401 if mode == "unauthorized" else 200)
            if mode == "unauthorized":
                raw = server.secret.encode()
            self.send_header("Content-Type", "text/plain" if mode == "wrong_mime" else "application/json")
            self.send_header("Connection", "close")
            if mode == "gzip":
                self.send_header("Content-Encoding", "gzip")
            if mode in {"chunked", "bad_chunk"}:
                self.send_header("Transfer-Encoding", "chunked")
            elif mode != "oversize_actual":
                self.send_header("Content-Length", "4096" if mode == "oversize_length" else str(len(raw)))
                if mode == "duplicate_length":
                    self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            if mode == "oversize_length":
                return
            if mode == "bad_chunk":
                self.wfile.write(b"nothex\r\ninvalid\r\n")
            elif mode == "chunked":
                self.wfile.write(("%x\r\n" % len(raw)).encode() + raw + b"\r\n0\r\n\r\n")
            elif mode == "slow_body":
                self.wfile.write(raw[:1]); self.wfile.flush()
                server.entered.set()
                server.release.wait(5)
                self.connection.settimeout(1)
                try:
                    server.disconnected = not self.connection.recv(1)
                except OSError:
                    server.disconnected = True
            elif mode == "trickle":
                for byte in raw:
                    if server.release.is_set():
                        break
                    self.wfile.write(bytes([byte])); self.wfile.flush()
                    time.sleep(.04)
            else:
                self.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            self.close_connection = True


class Server(ThreadingHTTPServer):
    daemon_threads = False
    def __init__(self, mode="ok", secret="", redirect=""):
        super().__init__(("127.0.0.1", 0), Handler)
        self.mode, self.secret, self.redirect = mode, secret, redirect
        self.entered, self.release = threading.Event(), threading.Event()
        self.seen, self.disconnected = [], False
        self.thread = threading.Thread(target=self.serve_forever, kwargs={"poll_interval": .01})

    @property
    def url(self):
        return "http://127.0.0.1:%d/v1" % self.server_port

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.release.set()
        self.shutdown(); self.server_close(); self.thread.join(2)
        assert not self.thread.is_alive()

    def handle_error(self, request, address):
        # Tests intentionally close a real peer during HTTP/TLS reads.
        pass


def rejected(code, call, *, secret=""):
    try:
        call()
    except (ProviderError, CredentialError) as error:
        assert error.code == code, error.to_record()
        record = json.dumps(error.to_record()) + str(error) + repr(error) + traceback.format_exc()
        assert not secret or secret not in record
        return error.to_record()
    assert False, "Expected controlled failure: " + code


def credential_cases(secret):
    store = CredentialStore()
    name = "smoke-" + uuid4().hex
    assert store.get(name, storage="session") is None
    store.put(name, secret, storage="session")
    assert store.get(name, storage="session") == secret
    assert CredentialStore().get(name, storage="session") is None
    assert secret not in repr(store)
    rejected("credential.invalid_storage", lambda: store.get(name, storage="plaintext"), secret=secret)
    rejected("credential.invalid_id", lambda: store.put("bad/id", secret), secret=secret)
    rejected("credential.invalid_id", lambda: store.put(secret, secret), secret=secret)
    if sys.platform == "win32":
        try:
            assert store.get(name) is None
            store.put(name, secret)
            assert CredentialStore().get(name) == secret
            store.put(name, secret + "中文")
            assert store.get(name) == secret + "中文"
        finally:
            store.delete(name)
        assert store.get(name) is None
        RESULTS["real_system_vault"] = "Windows CredWriteW/CredReadW/CredDeleteW passed"
    else:
        try:
            store.put(name, secret)
        except CredentialError as error:
            assert error.code in {"credential.system_unavailable", "credential.system_operation_failed"}
            RESULTS["real_system_vault"] = "controlled unavailability: " + error.code
        else:
            try:
                assert CredentialStore().get(name) == secret
                RESULTS["real_system_vault"] = "Linux SecretService roundtrip passed"
            finally:
                store.delete(name)
    with patch.object(credential_module.sys, "platform", "linux"), patch.object(
            credential_module, "_SecretServiceVault", side_effect=RuntimeError(secret)):
        rejected("credential.system_unavailable", lambda: store.get(name), secret=secret)
        assert store.get(name, storage="session") == secret
    store.delete(name, storage="session")
    assert store.get(name, storage="session") is None
    store.put(name, secret, storage="session"); store.clear_session()
    assert store.get(name, storage="session") is None


def transport_cases(secret):
    store = CredentialStore(); store.put("loopback", secret, storage="session")
    with Server(secret=secret) as server:
        config = ProviderConfig(server.url, "fixture-model", auth_mode="session", credential_id="loopback", json_mode=True)
        client = ProviderClient(config, credentials=store)
        with patch.dict(os.environ, {"HTTP_PROXY": "http://127.0.0.1:1", "HTTPS_PROXY": "http://127.0.0.1:1", "ALL_PROXY": "http://127.0.0.1:1"}):
            reply = client.complete(MESSAGES)
        assert reply.json_object == {"plan": []} and json.loads(reply.text) == reply.json_object
        assert reply.usage == {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5}
        assert reply.model == "fixture-model" and "plan" not in repr(reply)
        assert server.seen[0]["path"] == "/v1/chat/completions"
        assert server.seen[0]["auth_matches"] is True
        assert server.seen[0]["payload"]["messages"] == MESSAGES
        assert server.seen[0]["payload"]["response_format"] == {"type": "json_object"}
        assert "tools" not in server.seen[0]["payload"]
        assert secret not in json.dumps(asdict(config))
        assert secret not in json.dumps(server.seen)
        pre = threading.Event(); pre.set()
        rejected("provider.cancelled", lambda: client.complete(MESSAGES, cancel_event=pre), secret=secret)
        rejected("provider.secret_in_messages", lambda: client.complete([{"role": "user", "content": secret}]), secret=secret)
        assert len(server.seen) == 1
        local = replace(config, base_url=server.url.replace("127.0.0.1", "localhost") + "/chat/completions", auth_mode="none", credential_id="")
        with patch.object(socket, "getaddrinfo", side_effect=AssertionError("localhost must not use DNS")):
            assert ProviderClient(local).complete(MESSAGES).json_object == {"plan": []}
        assert not server.seen[-1]["auth_present"]
    cases = {"bad_envelope": "provider.invalid_response_json", "duplicate_envelope": "provider.invalid_response_json",
        "bad_utf8": "provider.invalid_response_json", "bad_content": "provider.invalid_reply_json",
        "duplicate_content": "provider.invalid_reply_json", "nonfinite": "provider.invalid_reply_json", "array": "provider.invalid_reply_json",
        "overflow": "provider.invalid_reply_json", "surrogate": "provider.invalid_reply_json",
        "truncated": "provider.incomplete_reply", "tools": "provider.unsupported_reply",
        "unauthorized": "provider.http_error", "secret_echo": "provider.secret_echo_rejected",
        "escaped_secret_echo": "provider.secret_echo_rejected", "oversize_length": "provider.response_too_large",
        "oversize_actual": "provider.response_too_large", "duplicate_length": "provider.invalid_framing",
        "wrong_mime": "provider.invalid_content_type", "gzip": "provider.unsupported_encoding", "bad_chunk": "provider.transport_failed"}
    records = []
    for mode, code in cases.items():
        with Server(mode, secret=secret) as server:
            config = ProviderConfig(server.url, "fixture-model", auth_mode="session", credential_id="loopback", max_response_bytes=1024)
            row = rejected(code, lambda: ProviderClient(config, credentials=store).complete(MESSAGES), secret=secret)
            if mode == "unauthorized":
                assert row["status_code"] == 401
            records.append(row)
            assert len(server.seen) == 1
    with Server("chunked") as server:
        assert ProviderClient(ProviderConfig(server.url, "fixture")).complete(MESSAGES).json_object == {"plan": []}
    with Server(secret=secret) as destination, Server("redirect", secret=secret) as source:
        source.redirect = destination.url
        config = ProviderConfig(source.url, "fixture", auth_mode="session", credential_id="loopback")
        row = rejected("provider.redirect_forbidden", lambda: ProviderClient(config, credentials=store).complete(MESSAGES), secret=secret)
        assert row["status_code"] == 307 and source.seen[0]["auth_matches"]
        assert destination.seen == []
        records.append(row)
    RESULTS["negative_records"] = records


def cancel_timeout_cases():
    measured = {}
    for mode in ("slow_headers", "slow_body"):
        with Server(mode) as server:
            cancelled = threading.Event(); caught = []
            waiting = threading.Event()
            config = ProviderConfig(server.url, "fixture", timeout_s=4, connect_timeout_s=1)
            def work():
                caught.append(rejected("provider.cancelled", lambda: ProviderClient(config).complete(MESSAGES, cancel_event=cancelled)))
            original_select = provider_module.select.select
            original_read = provider_module._Reader.readinto
            captured = bytearray()
            def observe_bytes(reader, buffer):
                count = original_read(reader, buffer)
                captured.extend(buffer[:count])
                return count
            def observe_read(readable, writable, exceptional, timeout):
                body_seen = bool(bytes(captured).partition(b"\r\n\r\n")[2])
                if threading.current_thread() is thread and readable and server.entered.is_set() and (mode == "slow_headers" or body_seen):
                    waiting.set()
                return original_select(readable, writable, exceptional, timeout)
            with patch.object(provider_module.select, "select", observe_read), patch.object(provider_module._Reader, "readinto", observe_bytes):
                thread = threading.Thread(target=work); thread.start()
                try:
                    assert server.entered.wait(2)
                    assert waiting.wait(2), "Cancel only after the actual response-read wait is reached"
                    started = time.monotonic(); cancelled.set(); thread.join(1)
                    elapsed = time.monotonic() - started
                    assert not thread.is_alive() and caught and elapsed < 1
                finally:
                    cancelled.set(); thread.join(1)
            server.release.set()
            deadline = time.monotonic() + 1.5
            while not server.disconnected and time.monotonic() < deadline:
                time.sleep(.005)
            assert server.disconnected, "Cancelled call must actually close the peer socket"
            measured[mode] = round(elapsed, 4)
    for mode in ("slow_headers", "trickle"):
        with Server(mode) as server:
            config = ProviderConfig(server.url, "fixture", timeout_s=.2, connect_timeout_s=.1)
            started = time.monotonic()
            rejected("provider.timeout", lambda: ProviderClient(config).complete(MESSAGES))
            assert time.monotonic() - started < 1
    # Real TCP connection with a peer that never completes the TLS handshake.
    class StalledTLS(socketserver.BaseRequestHandler):
        def handle(self):
            self.request.recv(8192); entered.set(); release.wait(3)
    entered, release, cancel = threading.Event(), threading.Event(), threading.Event()
    with socketserver.ThreadingTCPServer(("127.0.0.1", 0), StalledTLS) as server:
        host = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .01}); host.start()
        caught = []
        config = ProviderConfig("https://127.0.0.1:%d/v1" % server.server_address[1], "fixture", timeout_s=3, connect_timeout_s=2)
        caller = threading.Thread(target=lambda: caught.append(rejected("provider.cancelled", lambda: ProviderClient(config).complete(MESSAGES, cancel_event=cancel))))
        caller.start()
        try:
            assert entered.wait(2)
            start = time.monotonic(); cancel.set(); caller.join(1)
            assert not caller.is_alive() and caught[0]["phase"] == "tls"
            measured["tls"] = round(time.monotonic()-start, 4)
            timeout_config = replace(config, timeout_s=1, connect_timeout_s=.1)
            started = time.monotonic()
            row = rejected("provider.timeout", lambda: ProviderClient(timeout_config).complete(MESSAGES))
            assert row["phase"] == "tls" and time.monotonic()-started < 1
        finally:
            release.set(); server.shutdown(); caller.join(2); host.join(2)
    # Bounded caller cancellation during the non-interruptible OS DNS primitive.
    entered, release, cancel = threading.Event(), threading.Event(), threading.Event()
    def blocked_dns(*args, **kwargs):
        entered.set(); release.wait(3)
        return []
    caught = []
    with patch.object(socket, "getaddrinfo", side_effect=blocked_dns):
        caller = threading.Thread(target=lambda: caught.append(rejected("provider.cancelled", lambda: ProviderClient(
            ProviderConfig("https://example.invalid/v1", "fixture")).complete(MESSAGES, cancel_event=cancel))))
        caller.start()
        try:
            assert entered.wait(1)
            start = time.monotonic(); cancel.set(); caller.join(1)
            assert not caller.is_alive() and caught[0]["phase"] == "dns"
            measured["dns"] = round(time.monotonic()-start, 4)
        finally:
            release.set(); caller.join(2)
    RESULTS["cancellation_seconds"] = measured


def validation_cases():
    for scheme, default_port in (("http", 80), ("https", 443)):
        base = scheme + "://127.0.0.1"
        rejected("provider.invalid_url", lambda: ProviderConfig(base + ":0/v1", "model"))
        assert provider_module._endpoint(base + "/v1")[2] == default_port
        for explicit in (1, 443, 65535):
            assert provider_module._endpoint(base + ":%d/v1" % explicit)[2] == explicit
        for explicit in (-1, 65536):
            rejected("provider.invalid_url", lambda: ProviderConfig(base + ":%d/v1" % explicit, "model"))
    for field_name in ("timeout_s", "connect_timeout_s"):
        for value in (10**1000, -(10**1000), True, False, float("inf"), float("-inf"), float("nan"), 0):
            rejected("provider.invalid_timeout", lambda: ProviderConfig(
                "http://127.0.0.1/v1", "model", **{field_name: value}))
    assert ProviderConfig("http://127.0.0.1/v1", "model", timeout_s=600, connect_timeout_s=600)
    assert ProviderConfig("http://127.0.0.1/v1", "model", timeout_s=.05, connect_timeout_s=.05)
    for value in ("http://example.com/v1", "http://192.168.1.2/v1", "http://169.254.169.254/v1", "http://2130706433/v1"):
        rejected("provider.insecure_remote_url", lambda: ProviderConfig(value, "model"))
    for value in ("https://key@example.com/v1", "https://example.com/v1?key=bad", "https://example.com/#fragment",
                  "file:///tmp/endpoint", "https://example.com/../v1", "http://127.0.0.1/v1%0d%0aX", " https://example.com/v1"):
        rejected("provider.invalid_url", lambda: ProviderConfig(value, "model"))
    assert ProviderConfig("http://[::1]:1234/v1", "model")
    for options in ({"timeout_s": float("inf")}, {"timeout_s": True}, {"max_response_bytes": True}, {"auth_mode": []}):
        try:
            ProviderConfig("http://127.0.0.1/v1", "model", **options)
        except ProviderError:
            rejected_as_expected = True
        else:
            rejected_as_expected = False
        assert rejected_as_expected
    client = ProviderClient(ProviderConfig("http://127.0.0.1:1/v1", "model"))
    rejected("provider.invalid_messages", lambda: client.complete([{"role": [], "content": "bad"}]))
    rejected("provider.invalid_cancel_event", lambda: client.complete(MESSAGES, cancel_event=object()))
    rejected("provider.request_too_large", lambda: ProviderClient(replace(client.config, max_request_bytes=64)).complete(MESSAGES))
    fake_app = SimpleNamespace(thread=lambda: "owner")
    fake_qt = SimpleNamespace(QCoreApplication=SimpleNamespace(instance=lambda: fake_app), QThread=SimpleNamespace(currentThread=lambda: "owner"))
    with patch.dict(sys.modules, {"PySide6.QtCore": fake_qt}):
        rejected("provider.ui_thread_forbidden", lambda: client.complete(MESSAGES))


def first_cause_cases(secret):
    original_connect = provider_module._connect
    class CloseFailure:
        def __init__(self, sock):
            self.sock = sock
        def __getattr__(self, name):
            return getattr(self.sock, name)
        def close(self):
            self.sock.close()
            raise RuntimeError(secret)
    def failing_close(*args):
        return CloseFailure(original_connect(*args))
    for mode, expected in (("unauthorized", "provider.http_error"), ("ok", "provider.cleanup_failed")):
        with Server(mode, secret=secret) as server, patch.object(provider_module, "_connect", side_effect=failing_close):
            row = rejected(expected, lambda: ProviderClient(ProviderConfig(server.url, "fixture")).complete(MESSAGES), secret=secret)
            assert row["phase"] == "response"
            if mode == "unauthorized":
                assert row["status_code"] == 401
    # Exercise the same bounded polling seam while OS connect is in progress.
    # TLS/header/body tests above independently use real connected sockets.
    entered, cancelled = threading.Event(), threading.Event()
    class PendingConnect:
        closed = False
        def setblocking(self, value):
            pass
        def connect_ex(self, address):
            entered.set()
            return provider_module.errno.EWOULDBLOCK
        def close(self):
            self.closed = True
    pending = PendingConnect()
    def unready(*args):
        time.sleep(.01)
        return [], [], []
    caught = []
    with patch.object(provider_module.socket, "socket", return_value=pending), patch.object(provider_module.select, "select", side_effect=unready):
        caller = threading.Thread(target=lambda: caught.append(rejected("provider.cancelled", lambda: ProviderClient(
            ProviderConfig("http://127.0.0.1:9999/v1", "fixture")).complete(MESSAGES, cancel_event=cancelled))))
        caller.start()
        assert entered.wait(1)
        start = time.monotonic(); cancelled.set(); caller.join(1)
        assert not caller.is_alive() and pending.closed and caught[0]["phase"] == "connect"
        assert time.monotonic() - start < 1
    RESULTS["first_cause_cleanup_and_pending_connect"] = "passed; pending OS connect is an injected seam"


def linux_adapter_cases(secret):
    items, connections = [], []
    state = {"locked": False}
    class Bus:
        closed = False
        def __init__(self):
            connections.append(self)
        def close(self):
            self.closed = True
    class Item:
        def __init__(self, attributes, raw):
            self.attributes, self.raw = attributes, raw
        def ensure_not_locked(self):
            if state["locked"]:
                raise RuntimeError(secret)
        def get_secret(self):
            return self.raw
        def delete(self):
            items.remove(self)
    class Collection:
        def __init__(self, connection):
            self.connection = connection
        def ensure_not_locked(self):
            if state["locked"]:
                raise RuntimeError(secret)
        def search_items(self, attributes):
            return [item for item in items if item.attributes == attributes]
        def create_item(self, label, attributes, raw, *, replace):
            assert replace and isinstance(raw, bytes)
            items[:] = [item for item in items if item.attributes != attributes]
            items.append(Item(attributes, raw))
    fake = SimpleNamespace(dbus_init=Bus, Collection=Collection)
    with patch.object(credential_module.sys, "platform", "linux"), patch.dict(sys.modules, {"secretstorage": fake}):
        store = CredentialStore()
        store.put("linux-fixture", secret)
        assert store.get("linux-fixture") == secret
        assert all(connection.closed for connection in connections)
        assert items[0].attributes == {"application": "G4UniversalSim.Agent", "service": "G4UniversalSim.Agent", "username": "linux-fixture"}
        state["locked"] = True
        rejected("credential.system_operation_failed", lambda: store.get("linux-fixture"), secret=secret)
        assert all(connection.closed for connection in connections)
        state["locked"] = False
        items.append(Item(items[0].attributes, secret.encode()))
        rejected("credential.ambiguous_system_value", lambda: store.get("linux-fixture"), secret=secret)
        store.delete("linux-fixture")
        assert not items and store.get("linux-fixture") is None
        assert all(connection.closed for connection in connections)
    RESULTS["linux_adapter"] = "injected SecretService API roundtrip/locked/duplicate/connection close; real Linux vault not tested here"


def credential_cancel_case(secret):
    entered, release, cancel = threading.Event(), threading.Event(), threading.Event()
    class BlockedVault:
        def get(self, name):
            entered.set(); release.wait(3)
            return secret
    store = CredentialStore(); store.put("memory", secret, storage="session")
    caught = []
    with Server() as server, patch.object(store, "_vault", return_value=BlockedVault()):
        config = ProviderConfig(server.url, "fixture", auth_mode="system", credential_id="blocked", timeout_s=2, connect_timeout_s=1)
        caller = threading.Thread(target=lambda: caught.append(rejected("provider.cancelled", lambda: ProviderClient(
            config, credentials=store).complete(MESSAGES, cancel_event=cancel), secret=secret)))
        caller.start()
        try:
            assert entered.wait(1)
            start = time.monotonic(); store.clear_session()
            assert time.monotonic() - start < .5
            assert store.get("memory", storage="session") is None
            start = time.monotonic(); cancel.set(); caller.join(1)
            assert not caller.is_alive() and caught[0]["phase"] == "credentials"
            assert time.monotonic() - start < 1 and not server.seen
        finally:
            release.set(); caller.join(2)
    RESULTS["stalled_system_read"] = "bounded caller cancellation; explicit memory clear does not wait for system vault"


def run():
    initial_threads = set(threading.enumerate())
    secret = "smoke-only-" + secrets.token_urlsafe(28)
    credential_cases(secret)
    validation_cases()
    transport_cases(secret)
    cancel_timeout_cases()
    first_cause_cases(secret)
    linux_adapter_cases(secret)
    credential_cancel_case(secret)
    deadline = time.monotonic() + 2
    while any(t.name in {"agent-provider-dns", "agent-provider-credential"} for t in threading.enumerate()) and time.monotonic() < deadline:
        time.sleep(.01)
    assert not any(t.name in {"agent-provider-dns", "agent-provider-credential"} for t in threading.enumerate())
    assert not [t for t in threading.enumerate() if t not in initial_threads]
    RESULTS["remaining_owned_threads"] = 0
    encoded = json.dumps(RESULTS, ensure_ascii=False, indent=2)
    assert secret not in encoded
    evidence = ROOT / "out/collab/l1-provider"
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / "smoke-results.json").write_text(encoded + "\n", encoding="utf-8")
    print("agent provider: real loopback, OS credentials, bounded cancellation and secret-safe records PASS")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--configuration-only", action="store_true")
    arguments = parser.parse_args()
    if arguments.configuration_only:
        validation_cases()
        print("agent provider configuration: bounded port and timeout validation PASS")
    else:
        run()
