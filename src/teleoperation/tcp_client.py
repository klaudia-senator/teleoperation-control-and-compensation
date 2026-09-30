from __future__ import annotations

import queue
import socket
import threading
from collections.abc import Callable


class TCPClient:
    """Small TCP transport with a background line-oriented receive thread."""

    def __init__(self, log: Callable[[str], None] | None = None) -> None:
        self._socket: socket.socket | None = None
        self._timeout = 1.0
        self._rx_queue: queue.Queue[str] = queue.Queue()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._send_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._log = log or (lambda _message: None)

    @property
    def connected(self) -> bool:
        with self._state_lock:
            return self._socket is not None

    def connect(self, host: str, port: int, timeout: float = 1.0) -> None:
        self.disconnect("reconnect")
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.settimeout(timeout)
        with self._state_lock:
            self._socket = sock
            self._timeout = timeout
        self._stop.clear()
        self._thread = threading.Thread(target=self._receive_loop, name="telemetry-rx", daemon=True)
        self._thread.start()
        self._log(f"Connected to {host}:{port}")

    def disconnect(self, reason: str = "") -> None:
        self._stop.set()
        with self._state_lock:
            sock, self._socket = self._socket, None
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass
        thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=max(0.2, self._timeout + 0.1))
        self._thread = None
        if sock is not None:
            suffix = f" ({reason})" if reason else ""
            self._log(f"Disconnected{suffix}")

    def send(self, message: str) -> None:
        data = message.encode("utf-8", errors="strict")
        with self._send_lock:
            with self._state_lock:
                sock = self._socket
            if sock is None:
                raise RuntimeError("Not connected")
            sock.sendall(data)

    def drain_received(self) -> list[str]:
        lines: list[str] = []
        while True:
            try:
                lines.append(self._rx_queue.get_nowait())
            except queue.Empty:
                return lines

    def _receive_loop(self) -> None:
        buffer = b""
        while not self._stop.is_set():
            with self._state_lock:
                sock = self._socket
            if sock is None:
                return
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    self._close_from_receiver("peer closed")
                    return
                buffer += chunk
                while b"\n" in buffer:
                    raw_line, buffer = buffer.split(b"\n", 1)
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if line:
                        self._rx_queue.put(line)
            except TimeoutError:
                continue
            except OSError as exc:
                if not self._stop.is_set():
                    self._log(f"Receive error: {exc}")
                    self._close_from_receiver("receive error")
                return

    def _close_from_receiver(self, reason: str) -> None:
        with self._state_lock:
            sock, self._socket = self._socket, None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
        self._stop.set()
        self._log(f"Disconnected ({reason})")

    def __enter__(self) -> TCPClient:
        return self

    def __exit__(self, *_args: object) -> None:
        self.disconnect()
