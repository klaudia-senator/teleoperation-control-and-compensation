from __future__ import annotations

import argparse
import socket
import threading

from ..protocol import ProtocolError, decode_move, encode_telemetry


class FakeRobotServer:
    """Echo movement commands back as telemetry over the public demo protocol."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        if host not in {"127.0.0.1", "localhost"}:
            raise ValueError("The portfolio simulator intentionally accepts loopback hosts only")
        self.host = host
        self.port = port
        self._stop = threading.Event()
        self._server: socket.socket | None = None

    def serve_forever(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            self._server = server
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((self.host, self.port))
            server.listen(1)
            server.settimeout(0.5)
            print(f"Synthetic robot simulator listening on {self.host}:{self.port}")
            while not self._stop.is_set():
                try:
                    connection, address = server.accept()
                except TimeoutError:
                    continue
                print(f"Client connected from {address[0]}:{address[1]}")
                with connection:
                    self._serve_client(connection)
                print("Client disconnected")

    def stop(self) -> None:
        self._stop.set()
        if self._server is not None:
            try:
                self._server.close()
            except OSError:
                pass

    def _serve_client(self, connection: socket.socket) -> None:
        buffer = b""
        while not self._stop.is_set():
            try:
                chunk = connection.recv(4096)
            except OSError:
                return
            if not chunk:
                return
            buffer += chunk
            while b"\n" in buffer:
                raw_line, buffer = buffer.split(b"\n", 1)
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    pose = decode_move(line)
                except ProtocolError as exc:
                    print(f"Ignored invalid command: {exc}")
                    continue
                print(f"MOVE {pose}")
                connection.sendall(encode_telemetry(pose).encode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local synthetic robot simulator")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    try:
        FakeRobotServer(args.host, args.port).serve_forever()
    except KeyboardInterrupt:
        print("\nSimulator stopped")


if __name__ == "__main__":
    main()
