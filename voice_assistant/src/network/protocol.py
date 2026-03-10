"""UDP binary protocol for remote audio streaming.

Packet layout:
    [1 byte type][4 bytes seq (uint32 BE)][4 bytes length (uint32 BE)][<length> bytes data]

Message types
-------------
Client → Server:
    AUDIO_DATA     = 1  – chunk of raw int16 PCM audio
    AUDIO_END      = 2  – signals end of the audio stream

Server → Client:
    RESPONSE_META  = 3  – 4-byte uint32 BE sample rate, sent before audio chunks
    RESPONSE_DATA  = 4  – chunk of raw int16 PCM audio
    RESPONSE_END   = 5  – signals end of the response stream
    ERROR          = 6  – UTF-8 error message
"""

import struct

AUDIO_DATA = 1
AUDIO_END = 2
RESPONSE_META = 3
RESPONSE_DATA = 4
RESPONSE_END = 5
ERROR = 6

HEADER_FMT = "!BII"   # type(uint8), seq(uint32), length(uint32)
HEADER_SIZE = struct.calcsize(HEADER_FMT)  # 9 bytes

MAX_CHUNK = 60_000  # safe UDP payload


def pack(msg_type: int, seq: int, data: bytes) -> bytes:
    """Pack a single UDP packet."""
    header = struct.pack(HEADER_FMT, msg_type, seq, len(data))
    return header + data


def unpack(packet: bytes) -> tuple[int, int, bytes]:
    """Unpack a UDP packet into (type, seq, data)."""
    if len(packet) < HEADER_SIZE:
        raise ValueError(f"Packet too short: {len(packet)} bytes")
    msg_type, seq, length = struct.unpack(HEADER_FMT, packet[:HEADER_SIZE])
    data = packet[HEADER_SIZE: HEADER_SIZE + length]
    return msg_type, seq, data
