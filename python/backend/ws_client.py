"""
ws_client.py — WebSocket gateway client for agent gateway protocols (e.g. OpenClaw-style).
No SSH. Direct protocol connection.

Security design:
  - Stable ed25519 device keypair stored at ~/.config/clawtty/device_key (chmod 600).
  - device.id = SHA-256 of public key (hex).
  - Challenge/response handshake: sign nonce + metadata with private key.
  - WS tokens NEVER stored in this module — caller passes them in.
  - TLS (wss://) fully supported. Non-localhost ws:// triggers a warning.
  - All connection attempts and errors written to audit log.
  - Fail closed: any handshake error → refuse to connect, log reason.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import os
import stat
import threading
import time
import uuid
from enum import Enum
from pathlib import Path
from typing import Any, Callable

# ── Optional cryptography import ─────────────────────────────────────────────
try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        NoEncryption,
        PrivateFormat,
        PublicFormat,
    )
    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False

# ── Optional websockets import ────────────────────────────────────────────────
try:
    import websockets  # type: ignore
    import websockets.exceptions  # type: ignore
    _WS_AVAILABLE = True
except ImportError:
    _WS_AVAILABLE = False

from . import audit

_logger = logging.getLogger("clawtty.ws_client")

_KEY_DIR  = Path.home() / ".config" / "clawtty"
_KEY_FILE = _KEY_DIR / "device_key"

CLIENT_ID      = "webchat"
CLIENT_VERSION = "3.0.0"
PLATFORM       = "linux"
MIN_PROTOCOL   = 3
MAX_PROTOCOL   = 3


# ── Connection state ──────────────────────────────────────────────────────────

class ConnState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING   = "connecting"
    CONNECTED    = "connected"
    ERROR        = "error"


# ── Dependency guard ──────────────────────────────────────────────────────────

class GatewayClientError(RuntimeError):
    """Raised for configuration or dependency errors."""


def _require_deps() -> None:
    missing: list[str] = []
    if not _CRYPTO_AVAILABLE:
        missing.append("cryptography>=41.0")
    if not _WS_AVAILABLE:
        missing.append("websockets>=12.0")
    if missing:
        raise GatewayClientError(
            "Missing dependencies for WebSocket mode:\n"
            + "\n".join(f"  pip install {m}" for m in missing)
        )


# ── Device keypair ────────────────────────────────────────────────────────────

def _ensure_key_dir() -> None:
    _KEY_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(_KEY_DIR, stat.S_IRWXU)  # 0o700


def load_or_generate_device_key() -> tuple[Ed25519PrivateKey, str]:
    """
    Load the device ed25519 private key from disk, generating if absent.
    Returns (private_key, device_id_hex).

    device_id = SHA-256 of the raw 32-byte public key (lowercase hex).
    File permissions are enforced to 0o600.
    """
    _require_deps()
    _ensure_key_dir()

    if _KEY_FILE.exists():
        os.chmod(_KEY_FILE, stat.S_IRUSR | stat.S_IWUSR)  # enforce 0o600
        raw = _KEY_FILE.read_bytes()
        private_key: Ed25519PrivateKey = Ed25519PrivateKey.from_private_bytes(raw)
    else:
        private_key = Ed25519PrivateKey.generate()
        raw_bytes = private_key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
        _KEY_FILE.write_bytes(raw_bytes)
        os.chmod(_KEY_FILE, stat.S_IRUSR | stat.S_IWUSR)  # 0o600

    pub_raw: bytes = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    device_id = hashlib.sha256(pub_raw).hexdigest()
    return private_key, device_id


def _public_key_b64(private_key: Ed25519PrivateKey) -> str:
    """Return base64-encoded raw public key bytes."""
    pub_raw = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return base64.urlsafe_b64encode(pub_raw).rstrip(b"=").decode()


def _sign_payload(private_key: Ed25519PrivateKey, payload: str) -> str:
    """Sign a UTF-8 string payload, return base64 of the signature."""
    sig_bytes = private_key.sign(payload.encode("utf-8"))
    return base64.urlsafe_b64encode(sig_bytes).rstrip(b"=").decode()


def _build_signature_payload(
    device_id: str,
    client_id: str,
    client_mode: str,
    role: str,
    scopes: list[str],
    token: str,
    nonce: str,
    signed_at: int,
) -> str:
    """
    Canonical v2 signature payload — must match gateway's Vm() function exactly.
    Format: v2|deviceId|clientId|clientMode|role|scopes|signedAtMs|token|nonce
    Source: function Vm(e){ return ["v2",e.deviceId,e.clientId,e.clientMode,e.role,
                                    e.scopes.join(","),String(e.signedAtMs),
                                    e.token??"",e.nonce].join("|") }
    """
    scopes_str = ",".join(scopes)  # DO NOT sort — must match request order
    return "|".join([
        "v2",
        device_id,
        client_id,
        client_mode,
        role,
        scopes_str,
        str(signed_at),
        token or "",
        nonce,
    ])


# ── Pending request tracker ───────────────────────────────────────────────────

class _PendingRequest:
    def __init__(self) -> None:
        self.event = threading.Event()
        self.response: dict[str, Any] | None = None


# ── Main client class ─────────────────────────────────────────────────────────

class GatewayClient:
    """
    Async WebSocket client for the agent gateway WebSocket protocol.

    The asyncio event loop runs in a dedicated background thread.
    All public methods are thread-safe and callable from the CTk UI thread.
    """

    def __init__(self) -> None:
        _require_deps()

        self._state = ConnState.DISCONNECTED
        self._state_callbacks: list[Callable[[ConnState], None]] = []
        self._event_handlers: dict[str, list[Callable[[dict], None]]] = {}

        # Pending RPC requests keyed by request id
        self._pending: dict[str, _PendingRequest] = {}
        self._pending_lock = threading.Lock()

        # Async internals
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ws: Any | None = None                      # websockets connection
        self._thread: threading.Thread | None = None
        self._stop_event: asyncio.Event | None = None

        # Device identity (loaded on first connect)
        self._private_key: Ed25519PrivateKey | None = None
        self._device_id: str = ""
        self._public_key_b64: str = ""

        # Current URL for reconnect
        self._url: str = ""
        self._token: str = ""

    # ── Public: event registration ────────────────────────────────────────────

    def on_event(self, event_type: str, callback: Callable[[dict], None]) -> None:
        """Register a callback for a gateway event type, e.g. 'chat.message'."""
        self._event_handlers.setdefault(event_type, []).append(callback)

    def on_state_change(self, callback: Callable[[ConnState], None]) -> None:
        """Register a callback that fires whenever connection state changes."""
        self._state_callbacks.append(callback)

    @property
    def state(self) -> ConnState:
        return self._state

    @property
    def is_connected(self) -> bool:
        return self._state == ConnState.CONNECTED

    # ── Public: connect / disconnect ──────────────────────────────────────────

    def connect(self, url: str, token: str, auto_reconnect: bool = True) -> bool:
        """
        Connect to the gateway synchronously from the UI thread.
        Starts the async loop thread, performs handshake, returns True on success.

        Warns (via audit log) if url is ws:// on a non-localhost address.
        """
        _require_deps()

        # SECURITY FIX: Hard-block unencrypted ws:// for remote hosts.
        # Tokens and signatures must never travel over plaintext.
        if url.startswith("ws://"):
            host_part = url[5:].split("/")[0].split(":")[0]
            if host_part not in ("localhost", "127.0.0.1", "::1"):
                reason = (
                    f"Blocked: unencrypted ws:// refused for remote host '{host_part}'. "
                    "Use wss:// to protect your gateway token and auth signature."
                )
                audit.log("WS_SECURITY_BLOCK", "<none>", host_part, "", "FAILED", reason)
                _logger.error(reason)
                self._set_state(ConnState.ERROR)
                return False

        self._url   = url
        self._token = token

        # Load/generate device keypair
        try:
            self._private_key, self._device_id = load_or_generate_device_key()
            self._public_key_b64 = _public_key_b64(self._private_key)
        except Exception as exc:
            reason = f"Device key load/generate failed: {exc}"
            audit.log("WS_CONNECT", "<none>", url, "", "FAILED", reason)
            self._set_state(ConnState.ERROR)
            return False

        self._set_state(ConnState.CONNECTING)

        # Prepare a fresh event loop in a background thread.
        # _handshake_event is set as soon as the first connect attempt completes
        # (success or failure), so connect() can return promptly.
        handshake_event  = threading.Event()
        result_holder: list[bool] = [False]

        def _thread_main() -> None:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._stop_event = asyncio.Event()
            try:
                self._loop.run_until_complete(
                    self._managed_connect_loop(
                        url, token, handshake_event, result_holder, auto_reconnect
                    )
                )
            except Exception as exc:
                _logger.exception("WebSocket thread error: %s", exc)
                result_holder[0] = False
                handshake_event.set()
            finally:
                self._set_state(ConnState.DISCONNECTED)
                self._loop.close()
                self._loop = None

        # Stop any existing connection before starting a new one
        self._stop_existing()

        self._thread = threading.Thread(target=_thread_main, daemon=True, name="clawtty-ws")
        self._thread.start()

        # Wait up to 15 s for handshake
        handshake_event.wait(timeout=15)
        return result_holder[0]

    def _stop_existing(self) -> None:
        """Signal stop and wait for the old thread to exit (up to 5s)."""
        if self._loop and self._stop_event:
            self._loop.call_soon_threadsafe(self._stop_event.set)
        old_thread = self._thread
        if old_thread and old_thread.is_alive():
            old_thread.join(timeout=5)
        self._thread = None

    def disconnect(self) -> None:
        """Gracefully disconnect from the gateway."""
        if self._loop and self._stop_event:
            self._loop.call_soon_threadsafe(self._stop_event.set)
        self._set_state(ConnState.DISCONNECTED)

    # ── Public: RPC methods ───────────────────────────────────────────────────

    def send_message(self, session_key: str, message: str, timeout: float = 10.0) -> dict | None:
        """Send a chat message to the specified session. Returns the response dict or None."""
        return self._rpc("chat.send", {
            "sessionKey": session_key,
            "message": message,
            "deliver": False,
            "idempotencyKey": str(uuid.uuid4()),
        }, timeout)

    def get_status(self, timeout: float = 10.0) -> dict | None:
        """Fetch gateway system status. Returns response payload or None."""
        return self._rpc("system.status", {}, timeout)

    def list_sessions(self, timeout: float = 10.0) -> dict | None:
        """List active sessions on the gateway. Returns response payload or None."""
        return self._rpc("sessions.list", {}, timeout)

    # ── Internal: state management ────────────────────────────────────────────

    def _set_state(self, state: ConnState) -> None:
        _logger.debug("WS state: %s -> %s", self._state.value, state.value)
        self._state = state
        for cb in self._state_callbacks:
            try:
                cb(state)
            except Exception:
                pass

    # ── Internal: RPC helper ──────────────────────────────────────────────────

    def _rpc(self, method: str, params: dict, timeout: float = 10.0) -> dict | None:
        """
        Send a request and wait for the response.
        Returns the full response dict (including ok/payload), or None on failure.
        """
        if not self.is_connected or self._loop is None:
            return None

        req_id   = str(uuid.uuid4())
        pending  = _PendingRequest()
        with self._pending_lock:
            self._pending[req_id] = pending

        frame = json.dumps({
            "type":   "req",
            "id":     req_id,
            "method": method,
            "params": params,
        })

        async def _send() -> None:
            if self._ws:
                await self._ws.send(frame)

        asyncio.run_coroutine_threadsafe(_send(), self._loop)

        got = pending.event.wait(timeout=timeout)
        with self._pending_lock:
            self._pending.pop(req_id, None)

        if not got:
            _logger.warning("RPC %s timed out", method)
            return None
        return pending.response

    # ── Internal: managed connect + reconnect loop ────────────────────────────

    async def _managed_connect_loop(
        self,
        url: str,
        token: str,
        handshake_event: threading.Event,
        result_holder: list,
        auto_reconnect: bool,
    ) -> None:
        """
        Runs in the background thread's event loop.
        First attempt: performs handshake, signals handshake_event with result.
        If successful, runs the receive loop then reconnects with backoff.
        """
        assert self._stop_event is not None
        first_attempt = True
        backoff = 2.0
        max_backoff = 15.0

        while not self._stop_event.is_set():
            if not first_attempt:
                self._set_state(ConnState.CONNECTING)
            ok = await self._do_connect_once(url, token)

            if first_attempt:
                result_holder[0] = ok
                handshake_event.set()
                first_attempt = False
                if (not ok) and (not auto_reconnect):
                    break

            if self._stop_event.is_set():
                break

            if ok:
                backoff = 1.0  # reset after clean session
                # Session ended cleanly — show disconnected before retry
                if not self._stop_event.is_set():
                    self._set_state(ConnState.DISCONNECTED)
            else:
                # Failed — back off before retry
                _logger.info("Reconnecting in %.1fs…", backoff)
                if not self._stop_event.is_set():
                    self._set_state(ConnState.DISCONNECTED)
                try:
                    await asyncio.wait_for(
                        asyncio.shield(self._stop_event.wait()),
                        timeout=backoff,
                    )
                    break  # stop_event fired during sleep
                except asyncio.TimeoutError:
                    pass
                backoff = min(backoff * 2, max_backoff)

    # ── Internal: single connect attempt ─────────────────────────────────────

    async def _do_connect_once(self, url: str, token: str) -> bool:
        """
        Perform one gateway handshake + receive loop.
        Returns True if the session connected cleanly (even if it later ended),
        False if the handshake itself failed.
        """
        host_part = url.split("//", 1)[-1].split("/")[0].split(":")[0]

        try:
            # Build origin from URL so gateway's controlUi.allowedOrigins check passes
            try:
                from urllib.parse import urlparse
                _p = urlparse(url)
                _scheme = "https" if _p.scheme == "wss" else "http"
                _origin = f"{_scheme}://{_p.netloc}"
            except Exception:
                _origin = "http://localhost:18789"

            async with websockets.connect(
                url,
                open_timeout=10,
                ping_interval=None,   # disable library pings — gateway uses JSON-level pings
                ping_timeout=None,
                close_timeout=5,
                additional_headers={"Origin": _origin},
            ) as ws:
                self._ws = ws

                # 1. Receive challenge
                raw = await asyncio.wait_for(ws.recv(), timeout=10)
                challenge = json.loads(raw)

                if (
                    challenge.get("type") != "event"
                    or challenge.get("event") != "connect.challenge"
                ):
                    reason = f"Expected connect.challenge, got: {challenge.get('event')}"
                    audit.log("WS_CONNECT", "<none>", host_part, "", "FAILED", reason)
                    self._set_state(ConnState.ERROR)
                    return False

                nonce     = challenge["payload"]["nonce"]
                signed_at = int(time.time() * 1000)

                # 2. Build signature
                scopes = ["operator.read", "operator.write", "operator.admin", "operator.approvals", "operator.pairing"]
                sig_payload = _build_signature_payload(
                    device_id=self._device_id,
                    client_id=CLIENT_ID,
                    client_mode="webchat",
                    role="operator",
                    scopes=scopes,
                    token=token,
                    nonce=nonce,
                    signed_at=signed_at,
                )
                signature = _sign_payload(self._private_key, sig_payload)

                # 3. Send connect request
                req_id = str(uuid.uuid4())
                req = {
                    "type":   "req",
                    "id":     req_id,
                    "method": "connect",
                    "params": {
                        "minProtocol": MIN_PROTOCOL,
                        "maxProtocol": MAX_PROTOCOL,
                        "client": {
                            "id":       CLIENT_ID,
                            "version":  CLIENT_VERSION,
                            "platform": PLATFORM,
                            "mode":     "webchat",
                        },
                        "role":        "operator",
                        "scopes":      scopes,
                        "caps":        [],
                        "commands":    [],
                        "permissions": {},
                        "auth":        {"token": token},
                        "locale":      "en-US",
                        "userAgent":   f"{CLIENT_ID}/{CLIENT_VERSION}",
                        "device": {
                            "id":        self._device_id,
                            "publicKey": self._public_key_b64,
                            "signature": signature,
                            "signedAt":  signed_at,
                            "nonce":     nonce,
                        },
                    },
                }
                await ws.send(json.dumps(req))

                # 4. Receive hello-ok
                raw2 = await asyncio.wait_for(ws.recv(), timeout=10)
                resp = json.loads(raw2)

                if resp.get("type") != "res" or not resp.get("ok"):
                    err_msg = resp.get("error", {}).get("message", "unknown error")
                    reason  = f"Handshake rejected: {err_msg}"
                    audit.log("WS_CONNECT", "<none>", host_part, "", "FAILED", reason)
                    self._set_state(ConnState.ERROR)
                    return False

                payload_type = resp.get("payload", {}).get("type", "")
                if payload_type != "hello-ok":
                    reason = f"Expected hello-ok payload, got: {payload_type}"
                    audit.log("WS_CONNECT", "<none>", host_part, "", "FAILED", reason)
                    self._set_state(ConnState.ERROR)
                    return False

                audit.log("WS_CONNECT", "<none>", host_part, "", "OK", "Handshake complete")
                self._set_state(ConnState.CONNECTED)

                # Run receive loop until disconnected or stop requested
                await self._receive_loop_inner(ws)
                return True

        except (OSError, ConnectionRefusedError, asyncio.TimeoutError) as exc:
            reason = f"Connection failed: {exc}"
            audit.log("WS_CONNECT", "<none>", host_part, "", "FAILED", reason)
            self._set_state(ConnState.ERROR)
            return False
        except websockets.exceptions.WebSocketException as exc:
            reason = f"WebSocket error: {exc}"
            audit.log("WS_CONNECT", "<none>", host_part, "", "FAILED", reason)
            self._set_state(ConnState.ERROR)
            return False
        except json.JSONDecodeError as exc:
            reason = f"Malformed JSON from server: {exc}"
            audit.log("WS_CONNECT", "<none>", host_part, "", "FAILED", reason)
            self._set_state(ConnState.ERROR)
            return False
        except Exception as exc:
            reason = f"Unexpected error: {exc}"
            audit.log("WS_CONNECT", "<none>", host_part, "", "FAILED", reason)
            self._set_state(ConnState.ERROR)
            return False

    async def _receive_loop_inner(self, ws: Any) -> None:
        """Inner receive loop — simple and robust."""
        assert self._stop_event is not None
        frame_count = 0
        import time as _time
        start = _time.monotonic()

        try:
            async for raw in ws:
                # Check stop
                if self._stop_event.is_set():
                    _logger.debug(
                        "WS stop after %s frames (%ss)",
                        frame_count,
                        int(_time.monotonic() - start),
                    )
                    break

                frame_count += 1

                # Handle binary frames
                if isinstance(raw, bytes):
                    continue

                try:
                    frame = json.loads(raw)
                except json.JSONDecodeError:
                    _logger.debug("WS non-JSON frame ignored")
                    continue

                try:
                    self._dispatch_frame(frame)
                except Exception as exc:
                    _logger.warning("WS dispatch error (non-fatal): %s", exc)

            # If we get here, the async-for ended normally (server closed)
            _logger.debug(
                "WS receive loop ended after %s frames (%ss)",
                frame_count,
                int(_time.monotonic() - start),
            )

        except websockets.exceptions.ConnectionClosedOK as exc:
            _logger.debug(
                "WS closed OK code=%s reason=%s after %ss",
                exc.code,
                exc.reason,
                int(_time.monotonic() - start),
            )
        except websockets.exceptions.ConnectionClosedError as exc:
            _logger.warning(
                "WS closed ERROR code=%s reason=%s after %ss",
                exc.code,
                exc.reason,
                int(_time.monotonic() - start),
            )
        except websockets.exceptions.ConnectionClosed as exc:
            _logger.debug(
                "WS closed code=%s reason=%s after %ss",
                exc.code,
                exc.reason,
                int(_time.monotonic() - start),
            )
        except Exception as exc:
            _logger.exception(
                "WS receive loop error: %s: %s after %ss",
                type(exc).__name__,
                exc,
                int(_time.monotonic() - start),
            )
        finally:
            _logger.debug("WS receive loop exiting, frames=%s", frame_count)
            self._ws = None

    def _dispatch_frame(self, frame: dict) -> None:
        """Route an incoming JSON frame to response handlers or event handlers."""
        ftype = frame.get("type")

        if ftype == "res":
            req_id = frame.get("id", "")
            with self._pending_lock:
                pending = self._pending.get(req_id)
            if pending:
                pending.response = frame
                pending.event.set()

        elif ftype == "event":
            event_name = frame.get("event", "")
            payload = frame.get("payload", frame.get("data", {}))

            # Debug: log all events so we can see what the gateway sends
            _logger.info("WS event: %s (keys: %s)", event_name, list(payload.keys()) if isinstance(payload, dict) else type(payload).__name__)

            # Direct handlers for this event name
            handlers = self._event_handlers.get(event_name, [])
            for cb in handlers:
                try:
                    cb(payload)
                except Exception as exc:
                    _logger.warning("Event handler for %s raised: %s", event_name, exc)

            # Fire wildcard handlers
            for cb in self._event_handlers.get("*", []):
                try:
                    cb(frame)
                except Exception:
                    pass

        elif ftype == "ping":
            # Respond to server pings to keep connection alive
            if self._ws and self._loop:
                pong = json.dumps({"type": "pong"})
                asyncio.run_coroutine_threadsafe(
                    self._ws.send(pong), self._loop
                )

        elif ftype == "tick" or ftype == "health":
            # Acknowledge ticks/health checks silently
            pass
