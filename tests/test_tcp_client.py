import socket
import threading
import time

from teleoperation.models import Pose
from teleoperation.protocol import decode_move, encode_move, encode_telemetry
from teleoperation.tcp_client import TCPClient


def test_threaded_receive_with_local_tcp_peer() -> None:
    ready = threading.Event()
    port_holder: list[int] = []
    received: list[Pose] = []

    def server() -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            port_holder.append(listener.getsockname()[1])
            ready.set()
            connection, _ = listener.accept()
            with connection:
                buffer = b""
                while b"\n" not in buffer:
                    buffer += connection.recv(4096)
                line, _ = buffer.split(b"\n", 1)
                pose = decode_move(line.decode())
                received.append(pose)
                connection.sendall(encode_telemetry(pose).encode())

    thread = threading.Thread(target=server, daemon=True)
    thread.start()
    assert ready.wait(timeout=1)

    client = TCPClient()
    client.connect("127.0.0.1", port_holder[0], timeout=0.2)
    client.send(encode_move(Pose(x=12)))
    deadline = time.monotonic() + 2
    lines: list[str] = []
    while not lines and time.monotonic() < deadline:
        lines = client.drain_received()
        time.sleep(0.01)
    client.disconnect()
    thread.join(timeout=1)

    assert received == [Pose(x=12)]
    assert len(lines) == 1
