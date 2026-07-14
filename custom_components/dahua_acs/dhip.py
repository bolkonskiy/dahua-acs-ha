"""Dahua DHIP event stream client (TCP :5000).

Connects outbound from Home Assistant to the panel and receives
client.notifyEventStream pushes (AlarmLocal, AccessControl, …).
Avoids EventHttpUpload, whose deflate bodies aiohttp cannot decode.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import struct
from collections.abc import Awaitable, Callable
from json import JSONDecoder
from typing import Any

_LOGGER = logging.getLogger(__name__)

DAHUA_GLOBAL_LOGIN = "global.login"
DAHUA_GLOBAL_KEEPALIVE = "global.keepAlive"
DAHUA_EVENT_MANAGER_ATTACH = "eventManager.attach"

EventCallback = Callable[[dict[str, Any]], Awaitable[None] | None]


def hashed_password(random: str, realm: str, username: str, password: str) -> str:
    """Dahua MD5 challenge response."""
    p_hash = hashlib.md5(f"{username}:{realm}:{password}".encode()).hexdigest().upper()
    return hashlib.md5(f"{username}:{random}:{p_hash}".encode()).hexdigest().upper()


def extract_json_objects(
    text: str, decoder: JSONDecoder = JSONDecoder()
) -> list[dict[str, Any]]:
    """Extract one or more JSON objects from a DHIP payload string."""
    result: list[dict[str, Any]] = []
    pos = 0
    while pos < len(text):
        match = text.find("{", pos)
        if match < 0:
            break
        try:
            obj, end = decoder.raw_decode(text, match)
            if isinstance(obj, dict):
                result.append(obj)
            pos = end
        except ValueError:
            pos = match + 1
    return result


class DahuaDhipClient(asyncio.Protocol):
    """Asyncio protocol for Dahua DHIP event subscription."""

    def __init__(
        self,
        username: str,
        password: str,
        loop: asyncio.AbstractEventLoop,
        on_event: EventCallback,
        on_ready: asyncio.Future[bool] | None = None,
    ) -> None:
        self.username = username
        self.password = password
        self.loop = loop
        self.on_event = on_event
        self.on_ready = on_ready
        self.transport: asyncio.Transport | None = None
        self.buffer = bytearray()
        self.request_id = 0
        self.session_id = 0
        self.keep_alive_interval = 25
        self.realm: str | None = None
        self.random: str | None = None
        self.handlers: dict[int, Any] = {}
        self._keep_alive_handle: asyncio.TimerHandle | None = None
        self._closed = False

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport  # type: ignore[assignment]
        _LOGGER.debug("DHIP connected")
        self.pre_login()

    def connection_lost(self, exc: Exception | None) -> None:
        _LOGGER.warning("DHIP disconnected: %s", exc)
        self._cancel_keepalive()
        if self.on_ready and not self.on_ready.done():
            self.on_ready.set_exception(
                ConnectionError(f"DHIP disconnected before ready: {exc}")
            )

    def data_received(self, data: bytes) -> None:
        self.buffer += data
        while b"\n" in self.buffer:
            idx = self.buffer.find(b"\n") + 1
            packet = self.buffer[:idx]
            self.buffer = self.buffer[idx:]
            for message in extract_json_objects(
                packet.decode("utf-8", errors="replace")
            ):
                self.handle_message(message)

    def send(self, method: str, handler, params: dict | None = None) -> None:
        if self.transport is None or self.transport.is_closing():
            return
        if params is None:
            params = {}
        self.request_id += 1
        msg_id = self.request_id
        payload = {
            "id": msg_id,
            "session": self.session_id,
            "magic": "0x1234",
            "method": method,
            "params": params,
        }
        self.handlers[msg_id] = handler
        body = json.dumps(payload, indent=4).encode("utf-8")
        header = struct.pack(">L", 0x20000000)
        header += struct.pack(">L", 0x44484950)  # DHIP
        header += struct.pack(">d", 0)
        header += struct.pack("<L", len(body))
        header += struct.pack("<L", 0)
        header += struct.pack("<L", len(body))
        header += struct.pack("<L", 0)
        self.transport.write(header + body)

    def handle_message(self, message: dict[str, Any]) -> None:
        msg_id = message.get("id")
        if isinstance(msg_id, int) and msg_id in self.handlers:
            handler = self.handlers.pop(msg_id)
            handler(message)
            return

        if message.get("method") == "client.notifyEventStream":
            params = message.get("params") or {}
            for event in params.get("eventList") or []:
                if not isinstance(event, dict):
                    continue
                try:
                    result = self.on_event(event)
                    if asyncio.iscoroutine(result):
                        self.loop.create_task(result)
                except Exception:  # noqa: BLE001
                    _LOGGER.exception("DHIP event callback failed")

    def pre_login(self) -> None:
        def handle_pre_login(message: dict[str, Any]) -> None:
            error = message.get("error") or {}
            if error.get("message") == "Component error: login challenge!":
                params = message.get("params") or {}
                self.random = params.get("random")
                self.realm = params.get("realm")
                self.session_id = message.get("session", 0)
                self.login()
            elif self.on_ready and not self.on_ready.done():
                self.on_ready.set_exception(
                    ConnectionError(f"DHIP pre-login failed: {error}")
                )

        self.send(
            DAHUA_GLOBAL_LOGIN,
            handle_pre_login,
            {
                "clientType": "",
                "ipAddr": "(null)",
                "loginType": "Direct",
                "userName": self.username,
                "password": "",
            },
        )

    def login(self) -> None:
        assert self.random and self.realm

        def handle_login(message: dict[str, Any]) -> None:
            if message.get("error"):
                if self.on_ready and not self.on_ready.done():
                    self.on_ready.set_exception(
                        ConnectionError(f"DHIP login failed: {message['error']}")
                    )
                return
            params = message.get("params") or {}
            if params.get("keepAliveInterval"):
                self.keep_alive_interval = max(
                    5, int(params["keepAliveInterval"]) - 5
                )
            self.session_id = message.get("session", self.session_id)
            _LOGGER.info("DHIP login OK host session=%s", self.session_id)
            self.attach_events()
            if self.on_ready and not self.on_ready.done():
                self.on_ready.set_result(True)
            self.schedule_keepalive()

        self.send(
            DAHUA_GLOBAL_LOGIN,
            handle_login,
            {
                "clientType": "",
                "ipAddr": "(null)",
                "loginType": "Direct",
                "userName": self.username,
                "password": hashed_password(
                    self.random, self.realm, self.username, self.password
                ),
                "authorityType": "Default",
            },
        )

    def attach_events(self) -> None:
        def handle_attach(message: dict[str, Any]) -> None:
            if message.get("error"):
                _LOGGER.error("DHIP attach error: %s", message["error"])
            else:
                _LOGGER.info("DHIP event stream attached")

        self.send(
            DAHUA_EVENT_MANAGER_ATTACH,
            handle_attach,
            {"codes": ["All"]},
        )

    def schedule_keepalive(self) -> None:
        self._cancel_keepalive()
        if self._closed:
            return

        def handle_keepalive(_: dict[str, Any]) -> None:
            self.schedule_keepalive()

        self._keep_alive_handle = self.loop.call_later(
            self.keep_alive_interval,
            lambda: self.send(
                DAHUA_GLOBAL_KEEPALIVE,
                handle_keepalive,
                {"timeout": self.keep_alive_interval, "action": True},
            ),
        )

    def _cancel_keepalive(self) -> None:
        if self._keep_alive_handle:
            self._keep_alive_handle.cancel()
            self._keep_alive_handle = None

    def close(self) -> None:
        self._closed = True
        self._cancel_keepalive()
        if self.transport and not self.transport.is_closing():
            self.transport.close()


async def run_dhip_listener(
    host: str,
    username: str,
    password: str,
    on_event: EventCallback,
    *,
    port: int = 5000,
    stop_event: asyncio.Event,
) -> None:
    """Connect and reconnect until stop_event is set."""
    loop = asyncio.get_running_loop()
    backoff = 2.0
    while not stop_event.is_set():
        ready: asyncio.Future[bool] = loop.create_future()
        client = DahuaDhipClient(username, password, loop, on_event, ready)
        transport = None
        try:
            transport, _proto = await loop.create_connection(
                lambda: client, host, port
            )
            await asyncio.wait_for(ready, timeout=20)
            backoff = 2.0
            _LOGGER.info("DHIP listening on %s:%s", host, port)
            await stop_event.wait()
        except asyncio.CancelledError:
            raise
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("DHIP listener error: %s; retry in %.0fs", err, backoff)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=backoff)
            except asyncio.TimeoutError:
                pass
            backoff = min(backoff * 2, 60.0)
        finally:
            client.close()
            if transport and not transport.is_closing():
                transport.close()
