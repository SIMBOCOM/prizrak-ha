"""Prizrak monitoring client for Home Assistant."""
import asyncio
import websockets
from websockets.exceptions import ConnectionClosed
import json
import aiohttp
import urllib.parse
import logging
from typing import Optional, Dict, Any, Callable
import time
import hashlib
import base64

from .const import SECURITY_FIELDS

_LOGGER = logging.getLogger(__name__)
# websockets traces the request URI, headers, and frames. Keep wire logging
# disabled for this client even when HA enables debug logging on all libraries.
_WIRE_LOGGER = logging.Logger(__name__ + ".wire")
_WIRE_LOGGER.disabled = True


def _http_session(timeout: int = 10) -> aiohttp.ClientSession:
    """Create a short-lived HTTP client for token-bearing requests."""
    return aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=timeout),
        trust_env=True,
        cookie_jar=aiohttp.DummyCookieJar(),
    )


class PrizrakClient:
    """Client for Prizrak monitoring system."""

    def __init__(
        self,
        email: str,
        password: str,
        state_callback: Callable[[int, Dict[str, Any]], None]
    ):
        """Initialize the client.

        Args:
            email: User email for authentication
            password: User password
            state_callback: Callback function for device state updates
        """
        self.login = email
        self.password = password
        self._state_callback = state_callback

        self.base_url = "https://monitoring.tecel.ru"
        self.passport_url = f"{self.base_url}/passport/api"
        self.ws_url = "wss://monitoring.tecel.ru"

        self.auth_token: Optional[str] = None
        self.connection_id: Optional[str] = None
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.running = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 999999
        self.reconnect_delay = 5
        self.invocation_counter = 0
        self.devices = []
        self.device_states = {}
        self._last_device_event: dict[int, float] = {}
        self._stream_closed = False
        self.last_auth_time = 0
        self.auth_validity_hours = 12
        self.last_message_time = 0
        self.last_event_time = 0
        self.message_timeout = 60
        self.event_timeout = 120  # Если нет EventObject 2 минуты - переподключение
        self.ping_interval = 15
        self.last_ping_time = 0

        # Event to signal when devices are ready
        self.devices_ready = asyncio.Event()

        # Track pending command invocations
        self.pending_invocations: Dict[str, asyncio.Future] = {}

        # Track GetDevices invocation id to detect its response
        self.get_devices_invocation_id: Optional[str] = None

        # App version (fetched once at startup)
        self.app_version: Optional[str] = None
        # Frontend web version (from passport.js?v=X.X.XXX)
        self.frontend_version: Optional[str] = None

    async def _fetch_app_version(self, session: aiohttp.ClientSession) -> str:
        """Fetch the passport version used in the fingerprint."""
        try:
            async with session.get(f"{self.base_url}/passport/version_data") as response:
                response.raise_for_status()
                data = await response.json(content_type=None)
                if version := data.get("app_version"):
                    return version
        except (aiohttp.ClientError, TimeoutError, ValueError, AttributeError) as exc:
            _LOGGER.warning("Version lookup failed (%s), using fallback", type(exc).__name__)
        return "296.0.0.0"

    def _get_fingerprint_token(self) -> str:
        """Generate fingerprint token for vtoken."""
        data = {
            "VTokenKey": "x-vtoken",
            "FingerPrint": hashlib.md5("browser_fingerprint".encode()).hexdigest(),
            "UniqId": "mit9hov5mit9hov6mit9hov7mit9hov8",
            "AppVersion": self.app_version,
            "Service": ""
        }
        return base64.b64encode(json.dumps(data).encode()).decode()

    async def authenticate(self) -> bool:
        """Authenticate without logging credentials or the server's response body."""
        _LOGGER.info("Authenticating with Prizrak")
        try:
            async with _http_session() as session:
                if not self.app_version:
                    self.app_version = await self._fetch_app_version(session)
                headers = {
                    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "x-vtoken": self._get_fingerprint_token(),
                }
                check_payload = {
                    "jsonrpc": "2.0",
                    "id": int(time.time() * 1000),
                    "method": "CheckLogin",
                    "params": {"login": self.login, "language_code": "EN"},
                }
                async with session.post(self.passport_url, json=check_payload, headers=headers) as response:
                    if response.status != 200:
                        _LOGGER.error("CheckLogin failed (HTTP %d)", response.status)
                        return False
                    await response.json(content_type=None)

                auth_payload = {
                    "jsonrpc": "2.0",
                    "id": int(time.time() * 1000),
                    "method": "Authorization",
                    "params": {
                        "login": self.login,
                        "password": self.password,
                        "forever": True,
                        "language_code": "EN",
                    },
                }
                async with session.post(self.passport_url, json=auth_payload, headers=headers) as response:
                    if response.status != 200:
                        _LOGGER.error("Authorization failed (HTTP %d)", response.status)
                        return False
                    auth_result = await response.json(content_type=None)
                    token = response.headers.get("x-atoken")

            if not token:
                result = auth_result.get("result") or {}
                token = result.get("atoken") or result.get("session_id")
            if not token:
                if (auth_result.get("error") or {}).get("message") == "versionError":
                    self.app_version = None
                    _LOGGER.warning("Passport version rejected, will fetch it again")
                else:
                    _LOGGER.error("Authorization returned no credentials")
                return False

            self.auth_token = token
            self.last_auth_time = time.time()
            _LOGGER.info("Authentication succeeded")
            return True
        except Exception as exc:
            _LOGGER.error("Authentication failed (%s)", type(exc).__name__)
            return False

    def check_auth_validity(self) -> bool:
        """Check if we need to re-authenticate."""
        if not self.auth_token:
            return False

        hours_since_auth = (time.time() - self.last_auth_time) / 3600
        if hours_since_auth > self.auth_validity_hours:
            _LOGGER.info("Refreshing authentication")
            return False

        return True

    def _create_auth_payload(self) -> Dict[str, Any]:
        frontend_ver = self.frontend_version or "1.0.174"
        return {
            "Type": 2154785295,
            "Atoken": self.auth_token,
            "ClientData": {
                "AppName": "Monitoring Web",
                "AppVersion": frontend_ver,
                "AppHost": "monitoring.tecel.ru",
                "UniqueId": hashlib.md5("browser_fingerprint".encode()).hexdigest(),
                "OsVersion": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
            "Lang": "ru"
        }

    def _get_headers(self) -> Dict[str, str]:
        auth_payload = json.dumps(self._create_auth_payload())
        return {
            'accept': '*/*',
            'authorization': f'Bearer {auth_payload}',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'x-signalr-user-agent': 'Microsoft SignalR/7.0'
        }

    async def negotiate_connection(self) -> Optional[str]:
        """Negotiate a SignalR connection."""
        negotiate_url = f"{self.base_url}/api/Control/negotiate?negotiateVersion=1"
        try:
            async with _http_session() as session:
                async with session.post(negotiate_url, headers=self._get_headers()) as response:
                    if response.status != 200:
                        _LOGGER.error("Negotiation failed (HTTP %d)", response.status)
                        return None
                    data = await response.json(content_type=None)
                    return data.get("connectionToken")
        except Exception as exc:
            _LOGGER.error("Negotiation failed (%s)", type(exc).__name__)
            return None

    async def delete_connection(self, connection_id: str) -> bool:
        """Close a stale connection without tracing its token-bearing URL."""
        try:
            async with _http_session(timeout=5) as session:
                async with session.delete(
                    f"{self.base_url}/api/Control",
                    params={"id": connection_id},
                    headers=self._get_headers(),
                ) as response:
                    if response.status in (200, 204, 404):
                        return True
                    _LOGGER.warning("Connection cleanup failed (HTTP %d)", response.status)
                    return False
        except Exception as exc:
            _LOGGER.warning("Connection cleanup failed (%s)", type(exc).__name__)
            return False

    def _cleanup_pending_invocations(self):
        """Cancel all pending invocations (called on disconnect/reconnect)."""
        if self.pending_invocations:
            _LOGGER.warning(f"Cleaning up {len(self.pending_invocations)} pending invocations")
            for invocation_id, future in self.pending_invocations.items():
                if not future.done():
                    future.set_result({
                        "success": False,
                        "error": "Connection lost"
                    })
            self.pending_invocations.clear()

    async def connect_websocket(self) -> bool:
        # Cleanup any pending commands from previous connection
        self._cleanup_pending_invocations()

        if not self.connection_id:
            self.connection_id = await self.negotiate_connection()
            if not self.connection_id:
                return False

        query = urllib.parse.urlencode({"id": self.connection_id})
        ws_url = f"{self.ws_url}/api/Control?{query}"

        ws_headers = {
            'Origin': self.base_url,
            'Authorization': self._get_headers()['authorization'],
        }

        try:
            _LOGGER.info("Connecting to WebSocket...")
            self.websocket = await websockets.connect(
                ws_url, additional_headers=ws_headers, compression=None, logger=_WIRE_LOGGER
            )
            self._stream_closed = False
            _LOGGER.info("WebSocket connected!")
            self.reconnect_attempts = 0
            return True
        except Exception as e:
            # Check for status code in both old and new websockets exception formats
            status_code = None
            if hasattr(e, "status_code"):
                # Old format: InvalidStatusCode with direct status_code attribute
                status_code = e.status_code
            elif hasattr(e, "response") and hasattr(e.response, "status_code"):
                # New format: InvalidStatus with response.status_code attribute
                status_code = e.response.status_code

            if status_code:
                _LOGGER.error(f"WebSocket rejected: HTTP {status_code}")
                if status_code == 404:
                    _LOGGER.warning(f"HTTP 404 - connection_id invalid, forcing re-negotiation...")
                    self.connection_id = None
                    self.auth_token = None
                elif status_code == 401:
                    _LOGGER.warning(f"HTTP 401 - auth failed, forcing re-authentication...")
                    self.auth_token = None
                elif status_code == 409:
                    _LOGGER.warning(f"HTTP 409 - connection exists, deleting old connection...")
                    # Try to delete the existing connection
                    old_conn_id = self.connection_id
                    # Run delete in a new task to avoid blocking the reconnect loop
                    asyncio.create_task(self.delete_connection(old_conn_id))
                    # Force new negotiation immediately
                    self.connection_id = None
                    await asyncio.sleep(2)  # Give server time to process delete
                elif status_code >= 500:
                    _LOGGER.warning(f"HTTP {status_code} - server error, will retry...")
                    self.connection_id = None
                else:
                    _LOGGER.error(f"Unhandled HTTP code: {status_code}")
                    self.connection_id = None
            else:
                # Not an HTTP status error, log as a generic WebSocket error
                _LOGGER.error("WebSocket connection failed (%s)", type(e).__name__)
                # Reset connection_id for any connection error to force fresh negotiation
                self.connection_id = None

            return False

    async def send_handshake(self):
        handshake = {"protocol": "json", "version": 1}
        await self.websocket.send(json.dumps(handshake) + '\x1e')
        _LOGGER.info("Handshake sent")

    async def receive_handshake_response(self) -> bool:
        """Read and verify SignalR handshake response from server."""
        try:
            response = await asyncio.wait_for(self.websocket.recv(), timeout=10.0)
            if isinstance(response, bytes):
                response = response.decode('utf-8')

            # Response may contain multiple \x1e-separated messages
            for part in response.split('\x1e'):
                part = part.strip()
                if not part:
                    continue
                try:
                    data = json.loads(part)
                    if data.get('error') or data.get('type') == 7:
                        _LOGGER.error("SignalR handshake rejected by server")
                        return False
                except json.JSONDecodeError:
                    pass

            _LOGGER.info("Handshake response OK")
            return True

        except asyncio.TimeoutError:
            _LOGGER.error("Timeout waiting for handshake response from server")
            return False
        except ConnectionClosed:
            _LOGGER.error("Connection closed before handshake response")
            return False
        except Exception as e:
            _LOGGER.error(f"Error reading handshake response ({type(e).__name__})")
            return False

    async def send_ping(self):
        ping_msg = {"type": 6}
        await self.websocket.send(json.dumps(ping_msg) + '\x1e')
        _LOGGER.debug("Ping sent")

    async def get_devices(self):
        self.invocation_counter += 1
        self.get_devices_invocation_id = str(self.invocation_counter)
        request = {
            "type": 1,
            "invocationId": self.get_devices_invocation_id,
            "target": "GetDevices",
            "arguments": [{"registrations": True, "custom_fields": True, "possible_commands": True}]
        }
        await self.websocket.send(json.dumps(request, ensure_ascii=False) + '\x1e')
        _LOGGER.info(f"GetDevices request sent (invocationId={self.get_devices_invocation_id})")

    async def watch_devices(self, device_ids):
        self.invocation_counter += 1
        request = {
            "type": 1,
            "invocationId": str(self.invocation_counter),
            "target": "WatchDevice",
            "arguments": [{"device_ids": device_ids}]
        }
        await self.websocket.send(json.dumps(request, ensure_ascii=False) + '\x1e')
        _LOGGER.info("Subscribed to %d device(s)", len(device_ids))

    async def send_command(self, device_id: int, command: str, timeout: float = 10.0):
        """Send command to device via WebSocket and wait for response.

        Args:
            device_id: Device ID to send command to
            command: Command name (GuardOn, GuardOff, AutolaunchOn, AutolaunchOff)
            timeout: Maximum time to wait for response (default 10s)

        Returns:
            True if command was sent and server confirmed success
            False if command failed or timed out
        """
        if not self.websocket:
            _LOGGER.error("WebSocket not connected")
            return False

        self.invocation_counter += 1
        invocation_id = str(self.invocation_counter)

        request = {
            "type": 1,
            "invocationId": invocation_id,
            "target": command,
            "arguments": [{"device_id": device_id}]
        }

        # Create Future for waiting response
        future = asyncio.Future()
        self.pending_invocations[invocation_id] = future

        try:
            # Send command with timeout
            await asyncio.wait_for(
                self.websocket.send(json.dumps(request, ensure_ascii=False) + '\x1e'),
                timeout=5.0
            )
            _LOGGER.info(f"Sent command {command} (invocationId={invocation_id})")

            # Wait for server response
            result = await asyncio.wait_for(future, timeout=timeout)

            if result.get("success", False):
                _LOGGER.info(f"Command {command} confirmed successful by server (invocationId={invocation_id})")
                return True
            else:
                _LOGGER.error(f"Command {command} was rejected (invocationId={invocation_id})")
                return False

        except asyncio.TimeoutError:
            _LOGGER.error(f"Command {command} timeout - no response from server (invocationId={invocation_id})")
            return False
        except Exception as e:
            _LOGGER.error(f"Failed to send command {command} ({type(e).__name__}) (invocationId={invocation_id})")
            return False
        finally:
            # Cleanup pending invocation
            self.pending_invocations.pop(invocation_id, None)

    def _expire_security_state(self, device_id: int) -> None:
        """Forget security readings while keeping unrelated telemetry."""
        state = self.device_states.get(device_id, {})
        if any(key in state for key in SECURITY_FIELDS):
            for key in SECURITY_FIELDS:
                state.pop(key, None)
            # An empty delta notifies HA without advancing the telemetry timestamp.
            self._state_callback(device_id, {})

    def _invalidate_stream(self) -> None:
        self._stream_closed = True
        self._last_device_event.clear()
        for device_id in self.device_states:
            self._expire_security_state(device_id)

    async def close_stream(self) -> None:
        """Publish the loss of availability before waiting for the socket to close."""
        self._invalidate_stream()
        if self.websocket:
            await self.websocket.close()

    def handle_event_object(self, arguments):
        """Merge partial telemetry from the current stream."""
        if self._stream_closed or not arguments:
            return

        event_data = arguments[0]
        device_id = event_data.get("device_id")
        if not device_id:
            return

        self.last_event_time = time.monotonic()
        # A GPS-only update is still evidence of a live device.
        self._last_device_event[device_id] = self.last_event_time
        delta = {
            key: value for key, value in event_data.get("device_state", {}).items()
            if key not in ("geo", "geo_ext")
        }
        if not delta:
            return

        state = self.device_states.setdefault(device_id, {})
        state.update(delta)
        # An offline event may also carry the last known guard and alarm values.
        # Ignore those fields until this device reports that it is connected again.
        if state.get("connection_state", "Connected") != "Connected":
            for key in SECURITY_FIELDS:
                state.pop(key, None)

        self._state_callback(device_id, delta)
        _LOGGER.debug("Device state updated")
        alarm = state.get("alarm") if "alarm" in delta else None
        if alarm and alarm not in ("Unknown", "None", "Off"):
            _LOGGER.warning("Device reported an alarm")

    async def receive_messages(self):
        """Receive and process WebSocket messages."""
        try:
            self.last_message_time = self.last_event_time = time.monotonic()
            message_count = 0
            _LOGGER.debug("receive_messages: starting loop")

            async for message in self.websocket:
                if self._stream_closed:
                    return
                message_count += 1
                self.last_message_time = time.monotonic()
                if isinstance(message, bytes):
                    message = message.decode('utf-8')
                for frame in message.split('\x1e'):
                    if not frame:
                        continue
                    try:
                        data = json.loads(frame)
                    except json.JSONDecodeError:
                        _LOGGER.debug("Non-JSON message")
                        continue
                    if not isinstance(data, dict):
                        continue
                    if data.get("type") == 7:  # SignalR Close
                        await self.close_stream()
                        return
                    try:
                        await self._handle_signalr_message(data)
                    except Exception as e:
                        _LOGGER.error(f"Error processing message ({type(e).__name__})")

            # async for exhausted = server closed connection cleanly
            close = self.websocket.close_code
            _LOGGER.warning(
                f"receive_messages: loop ended after {message_count} messages "
                f"(server closed cleanly, code={close})"
            )

        except ConnectionClosed as e:
            _LOGGER.warning(f"Connection closed unexpectedly (code={e.code})")
            raise
        except asyncio.TimeoutError:
            _LOGGER.warning("Connection timeout - no messages received")
            raise

        finally:
            self._invalidate_stream()

    async def _handle_signalr_message(self, data: dict) -> None:
        msg_type = data.get("type")
        if msg_type == 6:
            _LOGGER.debug("Ping received, sending pong")
            await self.send_ping()

        elif msg_type == 1:
            target = data.get('target')
            arguments = data.get('arguments', [])

            if target == "EventObject":
                self.handle_event_object(arguments)
            else:
                _LOGGER.debug("Ignoring unsupported invocation")

        elif msg_type == 3:
            # Type 3 = Completion (response to invocation)
            invocation_id = data.get('invocationId')
            result = data.get('result')
            error = data.get('error')

            _LOGGER.debug("Invocation response received")

            # Check if this is a pending command waiting for response
            if invocation_id in self.pending_invocations:
                future = self.pending_invocations[invocation_id]
                if not future.done():
                    if error:
                        # Server returned error
                        future.set_result({
                            "success": False,
                            "error": error
                        })
                    else:
                        # Command successful
                        future.set_result({
                            "success": True,
                            "result": result
                        })

            # Handle GetDevices response
            if invocation_id == self.get_devices_invocation_id:
                if error:
                    _LOGGER.error("Server rejected the device list request")
                elif result and isinstance(result, dict):
                    devices_data = result.get('data', {}).get('devices', [])
                    if devices_data:
                        self.devices = [
                            {key: dev[key] for key in ('device_id', 'name', 'model') if key in dev}
                            for dev in devices_data
                        ]
                        _LOGGER.info(f"Found {len(devices_data)} device(s):")
                        device_ids = [d['device_id'] for d in devices_data]
                        await self.watch_devices(device_ids)
                    else:
                        _LOGGER.warning("GetDevices returned an empty device list")
                else:
                    _LOGGER.warning("GetDevices returned an unexpected response")
                # Signal ready regardless — HA won't hang forever
                if not self.devices_ready.is_set():
                    self.devices_ready.set()
                    _LOGGER.info("Devices ready event set")

    async def send_proactive_pings(self):
        """Send ping to server every 15 seconds to keep connection alive."""
        while self.running:
            await asyncio.sleep(self.ping_interval)

            if self.websocket:
                try:
                    await self.send_ping()
                    self.last_ping_time = time.time()
                    _LOGGER.debug(f"Proactive ping sent (keep-alive)")
                except Exception as e:
                    _LOGGER.error(f"Failed to send proactive ping ({type(e).__name__})")
                    await self.close_stream()
                    break

    async def check_connection_health(self):
        """Monitor connection health and reconnect if needed."""
        while self.running:
            await asyncio.sleep(10)

            if not self.websocket or self._stream_closed:
                return

            now = time.monotonic()
            if (
                now - self.last_message_time > self.message_timeout
                or now - self.last_event_time > self.event_timeout
            ):
                _LOGGER.warning("Stream timed out, reconnecting")
                await self.close_stream()
                return

            # Other vehicles and SignalR pings can keep a silent vehicle's socket alive.
            for device_id, last_seen in list(self._last_device_event.items()):
                if now - last_seen > self.event_timeout:
                    del self._last_device_event[device_id]
                    self._expire_security_state(device_id)

    async def run(self):
        """Main run loop with auto-recovery."""
        self.running = True

        # Initial authentication
        if not await self.authenticate():
            _LOGGER.error("Initial authentication failed!")
            return

        while self.running:
            try:
                # Check if token is still valid
                if not self.check_auth_validity():
                    if not await self.authenticate():
                        _LOGGER.error("Re-authentication failed, retrying in 30s...")
                        await asyncio.sleep(30)
                        continue

                # Connect to WebSocket
                if await self.connect_websocket():
                    await self.send_handshake()
                    if not await self.receive_handshake_response():
                        await self.close_stream()
                        self.connection_id = None
                        await asyncio.sleep(self.reconnect_delay)
                        continue
                    await self.send_ping()
                    await self.get_devices()

                    # Start background tasks
                    ping_task = asyncio.create_task(self.send_proactive_pings())
                    health_task = asyncio.create_task(self.check_connection_health())

                    try:
                        await self.receive_messages()
                        # receive_messages() returned normally = server closed cleanly
                        # Reset and reconnect after a delay
                        self.reconnect_attempts += 1
                        self.connection_id = None
                        await asyncio.sleep(self.reconnect_delay)
                    finally:
                        # Cancel background tasks when receive_messages exits
                        ping_task.cancel()
                        health_task.cancel()
                        try:
                            await ping_task
                        except asyncio.CancelledError:
                            pass
                        try:
                            await health_task
                        except asyncio.CancelledError:
                            pass
                else:
                    # Connection failed, wait before retry with exponential backoff
                    delay = min(self.reconnect_delay * (2 ** min(self.reconnect_attempts, 5)), 60)
                    _LOGGER.warning(f"WebSocket connection failed, retrying in {delay}s (attempt {self.reconnect_attempts + 1})...")
                    self.reconnect_attempts += 1
                    await asyncio.sleep(delay)
                    continue

            except ConnectionClosed as e:
                _LOGGER.warning(f"Connection closed (code={e.code}), reconnecting in {self.reconnect_delay}s...")
                self.reconnect_attempts += 1
                await asyncio.sleep(self.reconnect_delay)
                self.connection_id = None

            except asyncio.TimeoutError:
                _LOGGER.warning(f"Connection timeout, reconnecting in {self.reconnect_delay}s...")
                self.reconnect_attempts += 1
                await asyncio.sleep(self.reconnect_delay)
                self.connection_id = None

            except asyncio.CancelledError:
                _LOGGER.info("Client task cancelled")
                self.running = False
                break

            except Exception as e:
                _LOGGER.error(f"Error ({type(e).__name__})")
                self.reconnect_attempts += 1
                await asyncio.sleep(self.reconnect_delay)
                self.connection_id = None

        await self.close_stream()
        _LOGGER.info("Client stopped")

    def stop(self):
        """Stop the client."""
        self._invalidate_stream()
        self.running = False
