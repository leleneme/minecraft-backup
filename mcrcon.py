# Taken and modified from https://github.com/barneygale/MCRcon by Barnaby Gale. Licensed under MIT

import struct
from typing import Tuple, NamedTuple
import socket


class Packet(NamedTuple):
    ident: any
    kind: any
    payload: any


class IncompletePacket(Exception):
    def __init__(self, minimum):
        self.minimum = minimum


class MCRcon:
    def __init__(self) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(10)
        self.connected = False
        self.logged_in = False

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()
        pass

    def connect(self, host: str, port: int) -> bool:
        if not self.connected:
            self.sock.connect((host, port))
            self.connected = True

        return self.connected

    def login(self, password: str) -> bool:
        if self.logged_in:
            return True

        if not self.connect:
            return False

        self.logged_in = self.__raw_login(password)
        return self.logged_in

    def __raw_login(self, password: str) -> bool:
        self.__send_packet(Packet(0, 3, password.encode("utf8")))
        packet = self.__receive_packet()

        return packet.ident == 0

    def __decode_packet(self, data: str) -> Tuple[Packet, str]:
        """
        Decodes a packet from the beginning of the given byte string. Returns a
        2-tuple, where the first element is a ``Packet`` instance and the second
        element is a byte string containing any remaining data after the packet.
        """

        if len(data) < 14:
            raise IncompletePacket(14)

        length = struct.unpack("<i", data[:4])[0] + 4
        if len(data) < length:
            raise IncompletePacket(length)

        ident, kind = struct.unpack("<ii", data[4:12])
        payload, padding = data[12:length-2], data[length-2:length]

        assert padding == b"\x00\x00"
        return Packet(ident, kind, payload), data[length:]

    def __encode_packet(self, packet: Packet) -> bytes:
        data = struct.pack("<ii", packet.ident, packet.kind) + \
            packet.payload + b"\x00\x00"
        return struct.pack("<i", len(data)) + data

    def __receive_packet(self):
        data = b""
        while True:
            try:
                return self.__decode_packet(data)[0]
            except IncompletePacket as exc:
                while len(data) < exc.minimum:
                    data += self.sock.recv(exc.minimum - len(data))

    def __send_packet(self, packet: Packet):
        self.sock.sendall(self.__encode_packet(packet))

    def send_command(self, text: str) -> str:
        self.__send_packet(Packet(0, 2, text.encode("utf8")))
        self.__send_packet(Packet(1, 0, b""))

        response = b""
        while True:
            packet = self.__receive_packet()
            if packet.ident != 0:
                break
            response += packet.payload

        decoded = response.decode("utf8")

        if len(decoded) > 1:
            print(f"[RCON] {decoded}")

        return decoded

    def close(self):
        if self.connect:
            self.sock.close()
            self.connected = False
            self.logged_in = False
