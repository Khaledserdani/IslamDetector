"""Reference encoder/decoder for Islam Detector Rev A telemetry v1.

This module is the protocol golden reference for RP2040 firmware and ESP32-S3
receiver implementations. It uses only the Python standard library.
"""
from __future__ import annotations

import struct
from typing import Any

SYNC = b"IS"
VERSION = 1
TYPE_MEASUREMENT = 0x10
MAX_SAMPLES = 8
INVALID_CURRENT_MA = 0xFFFF
INVALID_TEMPERATURE_CENTI_C = 0x7FFF
FLAG_SWEEP_COMPLETE = 1 << 8

# Fields from VERSION through SAMPLE_COUNT; SYNC and CRC are outside this.
_HEADER = struct.Struct("<BBHIIBHIHHHhBB")
_HEADER_SIZE = _HEADER.size  # 29 bytes
_U16 = struct.Struct("<H")


class ProtocolError(ValueError):
    """Raised when a telemetry frame is malformed or fails its CRC."""


def crc16_ccitt_false(data: bytes) -> int:
    """CRC-16/CCITT-FALSE: poly=0x1021, init=0xFFFF, xorout=0."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def encode_measurement(
    *,
    sequence: int,
    timestamp_us: int,
    profile_id: int,
    flags: int,
    pulse_width_ns: int,
    pulse_rate_hz: int,
    supply_mv: int,
    tx_current_ma: int,
    temp_centi_c: int,
    valid_mask: int,
    samples: list[int] | tuple[int, ...],
) -> bytes:
    """Encode one interleaved profile-sweep measurement frame."""
    count = len(samples)
    if not 1 <= count <= MAX_SAMPLES:
        raise ProtocolError("sample count must be between 1 and 8")
    if valid_mask & ~((1 << count) - 1):
        raise ProtocolError("valid_mask sets bits beyond sample_count")
    if pulse_rate_hz <= 0:
        raise ProtocolError("pulse_rate_hz must be positive")
    if flags & FLAG_SWEEP_COMPLETE and count != MAX_SAMPLES:
        raise ProtocolError("a complete sweep must contain exactly 8 samples")
    if temp_centi_c == INVALID_TEMPERATURE_CENTI_C:
        pass
    elif not -32768 <= temp_centi_c <= 32766:
        raise ProtocolError("temperature is outside int16 range or uses reserved sentinel")
    if tx_current_ma != INVALID_CURRENT_MA and not 0 <= tx_current_ma <= 65534:
        raise ProtocolError("current must be 0..65534 mA or 0xFFFF")

    sample_bytes = b"".join(_U16.pack(_bounded(v, 0, 65535, "sample")) for v in samples)
    length = _HEADER_SIZE + len(sample_bytes)
    header = _HEADER.pack(
        VERSION,
        TYPE_MEASUREMENT,
        length,
        _bounded(sequence, 0, 0xFFFFFFFF, "sequence"),
        _bounded(timestamp_us, 0, 0xFFFFFFFF, "timestamp_us"),
        _bounded(profile_id, 0, 255, "profile_id"),
        _bounded(flags, 0, 65535, "flags"),
        _bounded(pulse_width_ns, 0, 0xFFFFFFFF, "pulse_width_ns"),
        _bounded(pulse_rate_hz, 1, 65535, "pulse_rate_hz"),
        _bounded(supply_mv, 0, 65535, "supply_mv"),
        _bounded(tx_current_ma, 0, 65535, "tx_current_ma"),
        temp_centi_c,
        valid_mask,
        count,
    )
    body = header + sample_bytes
    crc = crc16_ccitt_false(body)
    return SYNC + body + _U16.pack(crc)


def decode_measurement(frame: bytes) -> dict[str, Any]:
    """Validate and decode one Rev A measurement frame."""
    if len(frame) < 2 + _HEADER_SIZE + 2:
        raise ProtocolError("frame is too short")
    if frame[:2] != SYNC:
        raise ProtocolError("bad sync word")

    body = frame[2:-2]
    received_crc = _U16.unpack(frame[-2:])[0]
    if crc16_ccitt_false(body) != received_crc:
        raise ProtocolError("CRC mismatch")
    if len(body) < _HEADER_SIZE:
        raise ProtocolError("missing header")

    fields = _HEADER.unpack(body[:_HEADER_SIZE])
    (
        version, msg_type, length, sequence, timestamp_us, profile_id, flags,
        pulse_width_ns, pulse_rate_hz, supply_mv, tx_current_ma, temp_centi_c,
        valid_mask, sample_count,
    ) = fields

    if version != VERSION:
        raise ProtocolError("unsupported protocol version")
    if msg_type != TYPE_MEASUREMENT:
        raise ProtocolError("not a measurement frame")
    if length != len(body):
        raise ProtocolError("declared length does not match frame size")
    if not 1 <= sample_count <= MAX_SAMPLES:
        raise ProtocolError("invalid sample_count")
    expected_body_size = _HEADER_SIZE + 2 * sample_count
    if len(body) != expected_body_size:
        raise ProtocolError("sample payload length mismatch")
    if valid_mask & ~((1 << sample_count) - 1):
        raise ProtocolError("valid_mask sets bits beyond sample_count")
    if pulse_rate_hz == 0:
        raise ProtocolError("pulse_rate_hz must be positive")
    if flags & FLAG_SWEEP_COMPLETE and sample_count != MAX_SAMPLES:
        raise ProtocolError("complete sweep does not contain 8 samples")

    samples = list(struct.unpack("<" + "H" * sample_count, body[_HEADER_SIZE:]))
    return {
        "version": version,
        "type": msg_type,
        "sequence": sequence,
        "timestamp_us": timestamp_us,
        "profile_id": profile_id,
        "flags": flags,
        "pulse_width_ns": pulse_width_ns,
        "pulse_rate_hz": pulse_rate_hz,
        "supply_mv": supply_mv,
        "tx_current_ma": tx_current_ma,
        "temp_centi_c": temp_centi_c,
        "valid_mask": valid_mask,
        "sample_count": sample_count,
        "samples": samples,
        "crc16": received_crc,
    }


class MeasurementStreamDecoder:
    """Incremental UART stream parser with sync recovery and CRC validation."""

    MIN_BODY_LENGTH = _HEADER_SIZE + 2
    MAX_BODY_LENGTH = _HEADER_SIZE + 2 * MAX_SAMPLES

    def __init__(self) -> None:
        self._buffer = bytearray()
        self.discarded_bytes = 0
        self.rejected_frames = 0

    def feed(self, data: bytes | bytearray | memoryview) -> list[dict[str, Any]]:
        self._buffer.extend(data)
        decoded: list[dict[str, Any]] = []

        while True:
            sync_at = self._buffer.find(SYNC)
            if sync_at < 0:
                # Preserve a possible first sync byte split across UART reads.
                keep = 1 if self._buffer.endswith(SYNC[:1]) else 0
                drop = len(self._buffer) - keep
                if drop:
                    del self._buffer[:drop]
                    self.discarded_bytes += drop
                break

            if sync_at:
                del self._buffer[:sync_at]
                self.discarded_bytes += sync_at

            # SYNC + VERSION + TYPE + LENGTH
            if len(self._buffer) < 6:
                break

            if self._buffer[2] != VERSION or self._buffer[3] != TYPE_MEASUREMENT:
                del self._buffer[0]
                self.discarded_bytes += 1
                self.rejected_frames += 1
                continue

            body_length = int.from_bytes(self._buffer[4:6], "little")
            if not self.MIN_BODY_LENGTH <= body_length <= self.MAX_BODY_LENGTH:
                del self._buffer[0]
                self.discarded_bytes += 1
                self.rejected_frames += 1
                continue

            frame_length = 2 + body_length + 2
            if len(self._buffer) < frame_length:
                break

            candidate = bytes(self._buffer[:frame_length])
            try:
                item = decode_measurement(candidate)
            except ProtocolError:
                # Advance one byte, not a whole claimed frame: a valid SYNC
                # may occur later in the buffered stream after corruption.
                del self._buffer[0]
                self.discarded_bytes += 1
                self.rejected_frames += 1
                continue

            decoded.append(item)
            del self._buffer[:frame_length]

        return decoded

    def reset(self) -> None:
        self._buffer.clear()
        self.discarded_bytes = 0
        self.rejected_frames = 0


def _bounded(value: int, minimum: int, maximum: int, field: str) -> int:
    if not isinstance(value, int) or not minimum <= value <= maximum:
        raise ProtocolError(f"{field} must be an integer in {minimum}..{maximum}")
    return value
