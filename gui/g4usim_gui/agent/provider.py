"""Bounded, cancellable text-JSON chat/completions transport for worker threads.

No retries, redirects, proxy inheritance, tools, project writes or Qt ownership.
HTTP is restricted to literal loopback/localhost. Cloud endpoints require TLS.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import errno
import http.client
import io
import ipaddress
import json
import math
import queue
import re
import select
import socket
import ssl
import sys
import threading
import time
from urllib.parse import unquote, urlsplit

from .credentials import CredentialError, CredentialStore

_RESOLVERS = threading.BoundedSemaphore(4)
_CREDENTIAL_READS = threading.BoundedSemaphore(4)
_HEADER_LIMIT = 32768


class ProviderError(Exception):
    """Safe stable first-observed failure; never include upstream error text."""
    def __init__(self, code: str, phase: str = "validation", status_code: int | None = None):
        self.code, self.phase, self.status_code = code, phase, status_code
        super().__init__(code)

    def to_record(self) -> dict:
        return {"code": self.code, "phase": self.phase, "status_code": self.status_code}


def _endpoint(value):
    try:
        if not isinstance(value, str) or not value or len(value) > 2048:
            raise ValueError
        if any(ord(c) <= 32 or ord(c) == 127 for c in value):
            raise ValueError
        url = urlsplit(value)
        if url.scheme not in {"http", "https"} or not url.hostname or url.username is not None or url.password is not None:
            raise ValueError
        if url.query or url.fragment or "?" in value or "#" in value:
            raise ValueError
        host = url.hostname.encode("idna").decode("ascii").lower()
        port = url.port
        if port is None:
            port = 443 if url.scheme == "https" else 80
        if not 1 <= port <= 65535:
            raise ValueError
        try:
            address = ipaddress.ip_address(host)
            loopback = address.is_loopback
        except ValueError:
            if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", host) or ".." in host:
                raise ValueError
            loopback = host == "localhost"
        if url.scheme == "http" and not loopback:
            raise ProviderError("provider.insecure_remote_url")
        decoded = unquote(url.path)
        if any(ord(c) < 32 or ord(c) == 127 for c in decoded) or "\\" in decoded or any(p in {".", ".."} for p in decoded.split("/")):
            raise ValueError
        path = url.path.rstrip("/")
        if not path.endswith("/chat/completions"):
            path += "/chat/completions"
        path.encode("ascii")
        return url.scheme, host, port, path, loopback
    except ProviderError:
        raise
    except (ValueError, UnicodeError):
        raise ProviderError("provider.invalid_url") from None


@dataclass(frozen=True)
class ProviderConfig:
    base_url: str
    model: str
    auth_mode: str = "none"
    credential_id: str = ""
    timeout_s: float = 60.0
    connect_timeout_s: float = 10.0
    max_request_bytes: int = 2 * 1024 * 1024
    max_response_bytes: int = 1024 * 1024
    json_mode: bool = False
    max_output_tokens: int | None = None

    def __post_init__(self):
        _endpoint(self.base_url)
        if not isinstance(self.model, str) or not self.model.strip() or len(self.model) > 256 or any(ord(c) < 32 or ord(c) == 127 for c in self.model):
            raise ProviderError("provider.invalid_model")
        if not isinstance(self.auth_mode, str) or self.auth_mode not in {"none", "system", "session"}:
            raise ProviderError("provider.invalid_auth_mode")
        if not isinstance(self.credential_id, str):
            raise ProviderError("provider.invalid_credential_id")
        if self.auth_mode == "none":
            if self.credential_id:
                raise ProviderError("provider.invalid_credential_id")
        elif not isinstance(self.credential_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", self.credential_id):
            raise ProviderError("provider.invalid_credential_id")
        for value in (self.timeout_s, self.connect_timeout_s):
            if type(value) not in (int, float) or not 0.05 <= value <= 600 or not math.isfinite(value):
                raise ProviderError("provider.invalid_timeout")
        if self.connect_timeout_s > self.timeout_s:
            raise ProviderError("provider.invalid_timeout")
        for value in (self.max_request_bytes, self.max_response_bytes):
            if type(value) is not int or not 64 <= value <= 8 * 1024 * 1024:
                raise ProviderError("provider.invalid_size_limit")
        if type(self.json_mode) is not bool or (self.max_output_tokens is not None and
                (type(self.max_output_tokens) is not int or not 1 <= self.max_output_tokens <= 32768)):
            raise ProviderError("provider.invalid_options")


@dataclass(frozen=True)
class ProviderReply:
    text: str = field(repr=False)
    json_object: dict = field(repr=False)
    model: str = ""
    usage: dict[str, int] = field(default_factory=dict)


class _Budget:
    def __init__(self, config, cancel):
        self.cancel = cancel
        start = time.monotonic()
        self.total = start + config.timeout_s
        self.connect = min(self.total, start + config.connect_timeout_s)
        self.phase = "connect"

    def check(self):
        # The first failure observed by this call is raised once; no retry or
        # cancellation handler can replace an already observed HTTP/JSON error.
        if self.cancel is not None and self.cancel.is_set():
            raise ProviderError("provider.cancelled", self.phase)
        limit = self.connect if self.phase in {"dns", "connect", "tls"} else self.total
        if time.monotonic() >= limit:
            raise ProviderError("provider.timeout", self.phase)

    def wait(self, sock, *, writing=False):
        while True:
            self.check()
            ready = select.select([] if writing else [sock], [sock] if writing else [], [], 0.05)
            if ready[0] or ready[1]:
                self.check()
                return


def _addresses(host, port, budget):
    if host == "localhost":
        # No DNS/proxy can turn localhost into a non-loopback destination.
        return [(socket.AF_INET, ("127.0.0.1", port)), (socket.AF_INET6, ("::1", port, 0, 0))]
    try:
        address = ipaddress.ip_address(host)
        return [(socket.AF_INET6, (host, port, 0, 0))] if address.version == 6 else [(socket.AF_INET, (host, port))]
    except ValueError:
        pass
    budget.phase = "dns"
    budget.check()
    if not _RESOLVERS.acquire(blocking=False):
        raise ProviderError("provider.resolver_busy", "dns")
    result = queue.Queue(maxsize=1)

    def resolve():
        # OS getaddrinfo cannot be interrupted portably. Abandoned resolution
        # is daemon-only, contains no credentials, and is globally bounded at 4.
        try:
            rows = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
            result.put([(r[0], r[4]) for r in rows if r[0] in {socket.AF_INET, socket.AF_INET6}])
        except Exception:
            result.put(None)
        finally:
            _RESOLVERS.release()

    try:
        threading.Thread(target=resolve, name="agent-provider-dns", daemon=True).start()
    except RuntimeError:
        _RESOLVERS.release()
        raise ProviderError("provider.resolver_busy", "dns") from None
    while True:
        budget.check()
        try:
            rows = result.get(timeout=0.05)
            if not rows:
                raise ProviderError("provider.dns_failed", "dns")
            return rows
        except queue.Empty:
            continue


def _credential(store, config, budget):
    budget.phase = "credentials"
    if store is None:
        raise ProviderError("credential.not_found", "credentials")
    if config.auth_mode == "session":
        return store.get(config.credential_id, storage="session")
    # A stalled OS/DBus read must not prevent cancellation/close of the caller.
    # No write/fallback is performed; abandoned OS reads are bounded at four.
    budget.check()
    if not _CREDENTIAL_READS.acquire(blocking=False):
        raise ProviderError("provider.credential_busy", "credentials")
    result = queue.Queue(maxsize=1)
    def read():
        try:
            result.put((True, store.get(config.credential_id, storage="system")))
        except CredentialError as error:
            result.put((False, error.code))
        except Exception:
            result.put((False, "credential.system_operation_failed"))
        finally:
            _CREDENTIAL_READS.release()
    try:
        threading.Thread(target=read, name="agent-provider-credential", daemon=True).start()
    except RuntimeError:
        _CREDENTIAL_READS.release()
        raise ProviderError("provider.credential_busy", "credentials") from None
    while True:
        budget.check()
        try:
            success, value = result.get(timeout=.05)
            if not success:
                raise ProviderError(value, "credentials")
            return value
        except queue.Empty:
            continue


def _connect(scheme, host, port, budget):
    addresses = _addresses(host, port, budget)
    budget.phase = "connect"
    transport = None
    for family, address in addresses:
        budget.check()
        sock = socket.socket(family, socket.SOCK_STREAM)
        try:
            sock.setblocking(False)
            status = sock.connect_ex(address)
            if status not in {0, errno.EISCONN}:
                if status not in {errno.EINPROGRESS, errno.EWOULDBLOCK, errno.EALREADY, 10035, 10036, 10037}:
                    raise OSError
                budget.wait(sock, writing=True)
                if sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR):
                    raise OSError
            transport = sock
            break
        except ProviderError:
            _close(sock)
            raise
        except OSError:
            _close(sock)
    if transport is None:
        raise ProviderError("provider.connect_failed", "connect")
    try:
        if scheme == "https":
            budget.phase = "tls"
            transport = ssl.create_default_context().wrap_socket(transport, server_hostname=host, do_handshake_on_connect=False)
            while True:
                budget.check()
                try:
                    transport.do_handshake()
                    break
                except ssl.SSLWantReadError:
                    budget.wait(transport)
                except ssl.SSLWantWriteError:
                    budget.wait(transport, writing=True)
        return transport
    except ProviderError:
        _close(transport)
        raise
    except (ssl.SSLError, OSError):
        _close(transport)
        raise ProviderError("provider.tls_failed", "tls") from None


def _close(value):
    try:
        value.close()
        return True
    except Exception:
        return False


class _Reader(io.RawIOBase):
    def __init__(self, sock, budget, limit):
        super().__init__()
        self.sock, self.budget, self.limit, self.received = sock, budget, limit, 0

    def readable(self):
        return True

    def readinto(self, buffer):
        while True:
            self.budget.check()
            try:
                size = self.sock.recv_into(buffer)
                self.received += size
                if self.received > self.limit:
                    raise ProviderError("provider.response_too_large", self.budget.phase)
                return size
            except (BlockingIOError, ssl.SSLWantReadError):
                self.budget.wait(self.sock)
            except ssl.SSLWantWriteError:
                self.budget.wait(self.sock, writing=True)


class _ResponseSocket:
    def __init__(self, sock, budget, limit):
        self.reader = io.BufferedReader(_Reader(sock, budget, limit))

    def makefile(self, mode):
        return self.reader


def _send(sock, data, budget):
    remaining = memoryview(data)
    while remaining:
        budget.check()
        try:
            count = sock.send(remaining)
            if not count:
                raise OSError
            remaining = remaining[count:]
        except (BlockingIOError, ssl.SSLWantWriteError):
            budget.wait(sock, writing=True)
        except ssl.SSLWantReadError:
            budget.wait(sock)


def _json(text, code):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError
            result[key] = value
        return result
    def finite_float(value):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError
        return number
    try:
        value = json.loads(text, object_pairs_hook=pairs, parse_float=finite_float,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError()))
        pending = [value]
        while pending:
            item = pending.pop()
            if isinstance(item, str):
                item.encode("utf-8")
            elif isinstance(item, dict):
                pending.extend(item.keys()); pending.extend(item.values())
            elif isinstance(item, list):
                pending.extend(item)
        return value
    except (ValueError, TypeError, RecursionError):
        raise ProviderError(code, "response") from None


def _echoes(value, secret):
    if not secret:
        return False
    pending = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, str) and secret in item:
            return True
        if isinstance(item, dict):
            pending.extend(item.keys())
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
    return False


class ProviderClient:
    def __init__(self, config: ProviderConfig, *, credentials: CredentialStore | None = None):
        if type(config) is not ProviderConfig:
            raise ProviderError("provider.invalid_config")
        if credentials is not None and not isinstance(credentials, CredentialStore):
            raise ProviderError("provider.invalid_credentials")
        self.config = config
        self._credentials = credentials

    def complete(self, messages, cancel_event=None) -> ProviderReply:
        qt = sys.modules.get("PySide6.QtCore")
        if qt is not None and qt.QCoreApplication.instance() is not None and qt.QThread.currentThread() == qt.QCoreApplication.instance().thread():
            raise ProviderError("provider.ui_thread_forbidden")
        if cancel_event is not None and not isinstance(cancel_event, threading.Event):
            raise ProviderError("provider.invalid_cancel_event")
        budget = _Budget(self.config, cancel_event)
        budget.check()
        if not isinstance(messages, (list, tuple)) or not 1 <= len(messages) <= 256:
            raise ProviderError("provider.invalid_messages")
        prepared = []
        for item in messages:
            if type(item) is not dict or set(item) != {"role", "content"} or not isinstance(item["role"], str) or item["role"] not in {"system", "user", "assistant", "developer"} or not isinstance(item["content"], str):
                raise ProviderError("provider.invalid_messages")
            prepared.append(dict(item))
        payload = {"model": self.config.model, "messages": prepared, "stream": False}
        if self.config.json_mode:
            payload["response_format"] = {"type": "json_object"}
        if self.config.max_output_tokens is not None:
            payload["max_tokens"] = self.config.max_output_tokens
        try:
            body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (ValueError, UnicodeError):
            raise ProviderError("provider.invalid_messages") from None
        if len(body) > self.config.max_request_bytes:
            raise ProviderError("provider.request_too_large")
        secret = None
        if self.config.auth_mode != "none":
            try:
                secret = _credential(self._credentials, self.config, budget)
                if not secret:
                    raise CredentialError("credential.not_found")
                if any(ord(c) < 33 or ord(c) > 126 for c in secret):
                    raise CredentialError("credential.invalid_header_value")
            except CredentialError as error:
                raise ProviderError(error.code, "credentials") from None
        if _echoes(prepared, secret):
            raise ProviderError("provider.secret_in_messages", "credentials")
        scheme, host, port, path, _ = _endpoint(self.config.base_url)
        authority = ("[" + host + "]") if ":" in host else host
        authority += ":" + str(port)
        headers = (f"POST {path} HTTP/1.1\r\nHost: {authority}\r\n"
                   "Content-Type: application/json\r\nAccept: application/json\r\n"
                   "Accept-Encoding: identity\r\nConnection: close\r\n"
                   f"Content-Length: {len(body)}\r\n")
        if secret:
            headers += "Authorization: Bearer " + secret + "\r\n"
        sock, response = None, None
        try:
            budget.connect = min(budget.total, time.monotonic() + self.config.connect_timeout_s)
            sock = _connect(scheme, host, port, budget)
            budget.phase = "request"
            _send(sock, headers.encode("ascii") + b"\r\n" + body, budget)
            budget.phase = "response"
            response = http.client.HTTPResponse(_ResponseSocket(sock, budget, self.config.max_response_bytes + _HEADER_LIMIT))
            response.begin()
            if 300 <= response.status <= 399:
                raise ProviderError("provider.redirect_forbidden", "response", response.status)
            if not 200 <= response.status <= 299:
                raise ProviderError("provider.http_error", "response", response.status)
            if sum(len(k) + len(v) + 4 for k, v in response.getheaders()) > _HEADER_LIMIT:
                raise ProviderError("provider.headers_too_large", "response")
            lengths = response.headers.get_all("Content-Length", [])
            transfer = response.getheader("Transfer-Encoding", "").lower()
            if len(lengths) > 1 or transfer not in {"", "chunked"} or (transfer and lengths):
                raise ProviderError("provider.invalid_framing", "response")
            if lengths:
                if not re.fullmatch(r"[0-9]+", lengths[0]):
                    raise ProviderError("provider.invalid_framing", "response")
                if int(lengths[0]) > self.config.max_response_bytes:
                    raise ProviderError("provider.response_too_large", "response")
            if response.getheader("Content-Encoding", "identity").lower() not in {"identity", ""}:
                raise ProviderError("provider.unsupported_encoding", "response")
            mime = response.getheader("Content-Type", "").split(";", 1)[0].strip().lower()
            if mime != "application/json" and not (mime.startswith("application/") and mime.endswith("+json")):
                raise ProviderError("provider.invalid_content_type", "response")
            raw = response.read(self.config.max_response_bytes + 1)
            if len(raw) > self.config.max_response_bytes:
                raise ProviderError("provider.response_too_large", "response")
            if lengths and len(raw) != int(lengths[0]):
                raise ProviderError("provider.incomplete_response", "response")
            try:
                decoded = raw.decode("utf-8")
            except UnicodeError:
                raise ProviderError("provider.invalid_response_json", "response") from None
            envelope = _json(decoded, "provider.invalid_response_json")
            if _echoes(envelope, secret):
                raise ProviderError("provider.secret_echo_rejected", "response")
            if type(envelope) is not dict or type(envelope.get("choices")) is not list or len(envelope["choices"]) != 1:
                raise ProviderError("provider.invalid_reply", "response")
            choice = envelope["choices"][0]
            message = choice.get("message") if isinstance(choice, dict) else None
            if type(message) is not dict or not isinstance(message.get("content"), str) or message.get("tool_calls") or message.get("function_call") or message.get("refusal"):
                raise ProviderError("provider.unsupported_reply", "response")
            if choice.get("finish_reason") != "stop":
                raise ProviderError("provider.incomplete_reply", "response")
            document = _json(message["content"], "provider.invalid_reply_json")
            if type(document) is not dict:
                raise ProviderError("provider.invalid_reply_json", "response")
            if _echoes(document, secret):
                raise ProviderError("provider.secret_echo_rejected", "response")
            model = envelope.get("model", self.config.model)
            if not isinstance(model, str) or len(model) > 256 or any(ord(c) < 32 for c in model):
                raise ProviderError("provider.invalid_reply", "response")
            usage = envelope.get("usage") or {}
            if not isinstance(usage, dict):
                raise ProviderError("provider.invalid_reply", "response")
            safe_usage = {}
            for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                if key in usage:
                    if type(usage[key]) is not int or usage[key] < 0:
                        raise ProviderError("provider.invalid_reply", "response")
                    safe_usage[key] = usage[key]
            budget.check()
            return ProviderReply(message["content"], document, model, safe_usage)
        except ProviderError:
            raise
        except (OSError, http.client.HTTPException, ValueError, OverflowError):
            raise ProviderError("provider.transport_failed", budget.phase) from None
        finally:
            failing = sys.exc_info()[0] is not None
            cleanup_ok = True
            if response is not None:
                cleanup_ok = _close(response) and cleanup_ok
            if sock is not None:
                cleanup_ok = _close(sock) and cleanup_ok
            if not cleanup_ok and not failing:
                raise ProviderError("provider.cleanup_failed", budget.phase) from None
