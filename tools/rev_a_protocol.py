"""Golden reference for Islam Detector Rev A binary protocol v0.1 (wire version 1).

Implements measurement, DEVICE_INFO, command and ACK frames plus an incremental
UART stream decoder. Uses only the Python standard library.
"""
from __future__ import annotations

import struct
from typing import Any

SYNC = b"IS"
VERSION = 1
TYPE_MEASUREMENT = 0x10
TYPE_ACK = 0x80
TYPE_DEVICE_INFO = 0x82

TYPE_HELLO = 0x01
TYPE_GET_INFO = 0x02
TYPE_START = 0x03
TYPE_STOP = 0x04
TYPE_SET_PROFILE = 0x05
TYPE_SELF_TEST = 0x06
COMMAND_TYPES = frozenset({
    TYPE_HELLO, TYPE_GET_INFO, TYPE_START, TYPE_STOP, TYPE_SET_PROFILE, TYPE_SELF_TEST
})

ACK_STATUS_OK = 0x00
ACK_STATUS_REJECTED = 0x01
ACK_STATUS_BUSY = 0x02
ACK_STATUS_UNSUPPORTED = 0x03
ACK_REASON_NONE = 0x00
ACK_REASON_TX_NOT_ARMED = 0x01
ACK_REASON_ADC_NOT_PRESENT = 0x02
ACK_REASON_PROFILE_UNKNOWN = 0x03
ACK_REASON_SELF_TEST_UNAVAILABLE = 0x04
ACK_REASON_COMMAND_UNSUPPORTED = 0x05

MAX_SAMPLES = 8
INVALID_CURRENT_MA = 0xFFFF
INVALID_TEMPERATURE_CENTI_C = 0x7FFF
FLAG_SWEEP_COMPLETE = 1 << 8

# Fields from VERSION through SAMPLE_COUNT; SYNC and CRC are outside this.
_HEADER = struct.Struct("<BBHIIBHIHHHhBB")
_HEADER_SIZE = _HEADER.size  # 29 bytes
_U16 = struct.Struct("<H")
_CONTROL_HEADER = struct.Struct("<BBH")
_DEVICE_INFO = struct.Struct("<8BIBI")  # 17-byte payload


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


ADC_MODEL_NONE = 0x00
ADC_MODEL_ADS8861 = 0x01
ADC_MODEL_ADS8860 = 0x02
ADC_MODEL_ADS7054 = 0x03
ADC_MODEL_AD7980 = 0x04

SAMPLE_FORMAT_UNKNOWN = 0x00
SAMPLE_FORMAT_TWOS_COMPLEMENT = 0x01
SAMPLE_FORMAT_UNSIGNED = 0x02

ADC_INPUT_UNKNOWN = 0x00
ADC_INPUT_DIFFERENTIAL = 0x01
ADC_INPUT_SINGLE_ENDED = 0x02
ADC_INPUT_PSEUDO_DIFFERENTIAL = 0x03

_ADC_METADATA = {
    ADC_MODEL_NONE: (SAMPLE_FORMAT_UNKNOWN, 0, ADC_INPUT_UNKNOWN),
    ADC_MODEL_ADS8861: (SAMPLE_FORMAT_TWOS_COMPLEMENT, 16, ADC_INPUT_DIFFERENTIAL),
    ADC_MODEL_ADS8860: (SAMPLE_FORMAT_UNSIGNED, 16, ADC_INPUT_SINGLE_ENDED),
    ADC_MODEL_ADS7054: (SAMPLE_FORMAT_TWOS_COMPLEMENT, 14, ADC_INPUT_DIFFERENTIAL),
    ADC_MODEL_AD7980: (SAMPLE_FORMAT_UNSIGNED, 16, ADC_INPUT_PSEUDO_DIFFERENTIAL),
}

# Nonzero ADC_VREF_UV limits from official vendor datasheets. ADS7054 reports AVDD.
_ADC_VREF_RANGES_UV = {
    ADC_MODEL_ADS8861: (2_500_000, 5_000_000),
    ADC_MODEL_ADS8860: (2_500_000, 5_000_000),
    ADC_MODEL_ADS7054: (1_650_000, 3_600_000),
    ADC_MODEL_AD7980: (2_400_000, 5_100_000),
}


def _validate_adc_metadata(model_id: int, sample_format_id: int,
                           resolution_bits: int, input_mode_id: int,
                           adc_vref_uv: int) -> None:
    expected = _ADC_METADATA.get(model_id)
    actual = (sample_format_id, resolution_bits, input_mode_id)
    if expected is None or actual != expected:
        raise ProtocolError("ADC model, resolution, input mode, and sample format are inconsistent")
    if not isinstance(adc_vref_uv, int) or not 0 <= adc_vref_uv <= 0xFFFFFFFF:
        raise ProtocolError("adc_vref_uv must be an unsigned 32-bit value")
    if model_id == ADC_MODEL_NONE:
        if adc_vref_uv != 0:
            raise ProtocolError("ADC_NONE requires adc_vref_uv=0")
        return
    if adc_vref_uv == 0:  # Explicit unknown/unmeasured reference sentinel.
        return
    minimum_uv, maximum_uv = _ADC_VREF_RANGES_UV[model_id]
    if not minimum_uv <= adc_vref_uv <= maximum_uv:
        raise ProtocolError("adc_vref_uv is outside the selected ADC's supported reference range")


def encode_device_info(
    *,
    hw_rev: int,
    fw_major: int,
    fw_minor: int,
    fw_patch: int,
    adc_model_id: int,
    sample_format_id: int,
    adc_resolution_bits: int,
    adc_input_mode_id: int,
    adc_vref_uv: int,
    active_profile_id: int,
    profile_crc32: int,
) -> bytes:
    """Encode DEVICE_INFO (TYPE 0x82) using the fixed v1 metadata payload."""
    _validate_adc_metadata(
        adc_model_id, sample_format_id, adc_resolution_bits, adc_input_mode_id,
        adc_vref_uv
    )

    payload = _DEVICE_INFO.pack(
        _bounded(hw_rev, 0, 255, "hw_rev"),
        _bounded(fw_major, 0, 255, "fw_major"),
        _bounded(fw_minor, 0, 255, "fw_minor"),
        _bounded(fw_patch, 0, 255, "fw_patch"),
        _bounded(adc_model_id, 0, 255, "adc_model_id"),
        _bounded(sample_format_id, 0, 255, "sample_format_id"),
        _bounded(adc_resolution_bits, 0, 255, "adc_resolution_bits"),
        _bounded(adc_input_mode_id, 0, 255, "adc_input_mode_id"),
        _bounded(adc_vref_uv, 0, 0xFFFFFFFF, "adc_vref_uv"),
        _bounded(active_profile_id, 0, 255, "active_profile_id"),
        _bounded(profile_crc32, 0, 0xFFFFFFFF, "profile_crc32"),
    )
    body_length = _CONTROL_HEADER.size + len(payload)
    body = _CONTROL_HEADER.pack(VERSION, TYPE_DEVICE_INFO, body_length) + payload
    return SYNC + body + _U16.pack(crc16_ccitt_false(body))


def decode_device_info(frame: bytes) -> dict[str, int]:
    """Validate and decode one DEVICE_INFO response."""
    expected_body_length = _CONTROL_HEADER.size + _DEVICE_INFO.size
    if len(frame) != 2 + expected_body_length + 2:
        raise ProtocolError("DEVICE_INFO frame length mismatch")
    if frame[:2] != SYNC:
        raise ProtocolError("bad sync word")
    body = frame[2:-2]
    if crc16_ccitt_false(body) != _U16.unpack(frame[-2:])[0]:
        raise ProtocolError("CRC mismatch")
    version, msg_type, length = _CONTROL_HEADER.unpack(body[:_CONTROL_HEADER.size])
    if version != VERSION or msg_type != TYPE_DEVICE_INFO:
        raise ProtocolError("not a supported DEVICE_INFO frame")
    if length != len(body):
        raise ProtocolError("declared DEVICE_INFO length mismatch")
    fields = _DEVICE_INFO.unpack(body[_CONTROL_HEADER.size:])
    keys = (
        "hw_rev", "fw_major", "fw_minor", "fw_patch", "adc_model_id",
        "sample_format_id", "adc_resolution_bits", "adc_input_mode_id",
        "adc_vref_uv", "active_profile_id", "profile_crc32",
    )
    result = dict(zip(keys, fields))
    result["version"] = version
    result["type"] = msg_type
    _validate_adc_metadata(
        result["adc_model_id"], result["sample_format_id"],
        result["adc_resolution_bits"], result["adc_input_mode_id"],
        result["adc_vref_uv"]
    )
    return result


def _encode_control_frame(msg_type: int, payload: bytes) -> bytes:
    body_length = _CONTROL_HEADER.size + len(payload)
    body = _CONTROL_HEADER.pack(VERSION, msg_type, body_length) + payload
    return SYNC + body + _U16.pack(crc16_ccitt_false(body))


def _decode_control_frame(frame: bytes, expected_type: int, expected_body_length: int) -> bytes:
    if len(frame) != 2 + expected_body_length + 2:
        raise ProtocolError("control frame length mismatch")
    if frame[:2] != SYNC:
        raise ProtocolError("bad sync word")
    body = frame[2:-2]
    if crc16_ccitt_false(body) != _U16.unpack(frame[-2:])[0]:
        raise ProtocolError("CRC mismatch")
    version, msg_type, length = _CONTROL_HEADER.unpack(body[:_CONTROL_HEADER.size])
    if version != VERSION or msg_type != expected_type:
        raise ProtocolError("unexpected control frame type or version")
    if length != len(body):
        raise ProtocolError("declared control-frame length mismatch")
    return body[_CONTROL_HEADER.size:]


def encode_command(command_type: int, profile_id: int | None = None) -> bytes:
    """Encode HELLO/GET_INFO/START/STOP/SELF_TEST or SET_PROFILE."""
    if command_type not in COMMAND_TYPES:
        raise ProtocolError("unsupported command type")
    if command_type == TYPE_SET_PROFILE:
        payload = bytes((_bounded(profile_id, 0, 255, "profile_id"),))
    else:
        if profile_id is not None:
            raise ProtocolError("profile_id is only valid for SET_PROFILE")
        payload = b""
    return _encode_control_frame(command_type, payload)


def decode_command(frame: bytes) -> dict[str, int]:
    """Validate and decode one complete command frame."""
    if len(frame) < 8 or frame[:2] != SYNC:
        raise ProtocolError("command frame is too short or has bad sync")
    command_type = frame[3]
    if command_type not in COMMAND_TYPES:
        raise ProtocolError("unsupported command type")
    expected_body_length = 5 if command_type == TYPE_SET_PROFILE else 4
    payload = _decode_control_frame(frame, command_type, expected_body_length)
    result = {"version": VERSION, "type": command_type}
    if command_type == TYPE_SET_PROFILE:
        result["profile_id"] = payload[0]
    return result


def _validate_ack(command_type: int, status: int, reason: int) -> None:
    if command_type not in COMMAND_TYPES:
        raise ProtocolError("ACK command_type is unsupported")
    if status not in (
        ACK_STATUS_OK, ACK_STATUS_REJECTED, ACK_STATUS_BUSY, ACK_STATUS_UNSUPPORTED
    ):
        raise ProtocolError("ACK status is unsupported")
    if reason not in (
        ACK_REASON_NONE, ACK_REASON_TX_NOT_ARMED, ACK_REASON_ADC_NOT_PRESENT,
        ACK_REASON_PROFILE_UNKNOWN, ACK_REASON_SELF_TEST_UNAVAILABLE,
        ACK_REASON_COMMAND_UNSUPPORTED,
    ):
        raise ProtocolError("ACK reason is unsupported")
    if (status == ACK_STATUS_OK) != (reason == ACK_REASON_NONE):
        raise ProtocolError("ACK status and reason are inconsistent")


def encode_ack(command_type: int, status: int, reason: int) -> bytes:
    """Encode the fixed v0.1 ACK payload (command, status, reason)."""
    _validate_ack(command_type, status, reason)
    return _encode_control_frame(TYPE_ACK, bytes((command_type, status, reason)))


def decode_ack(frame: bytes) -> dict[str, int]:
    """Validate and decode one complete ACK frame."""
    payload = _decode_control_frame(frame, TYPE_ACK, 7)
    command_type, status, reason = payload
    _validate_ack(command_type, status, reason)
    return {
        "version": VERSION,
        "type": TYPE_ACK,
        "command_type": command_type,
        "status": status,
        "reason": reason,
    }


def interpret_sample(
    raw_word: int, sample_format_id: int, resolution_bits: int = 16
) -> int:
    """Interpret a right-justified raw ADC word using DEVICE_INFO metadata."""
    if resolution_bits not in (14, 16):
        raise ProtocolError("resolution_bits must be 14 or 16")
    maximum = (1 << resolution_bits) - 1
    if not isinstance(raw_word, int) or not 0 <= raw_word <= maximum:
        raise ProtocolError(f"raw ADC word must fit in {resolution_bits} bits")
    if sample_format_id == SAMPLE_FORMAT_UNSIGNED:
        return raw_word
    if sample_format_id == SAMPLE_FORMAT_TWOS_COMPLEMENT:
        sign_bit = 1 << (resolution_bits - 1)
        return raw_word - (1 << resolution_bits) if raw_word & sign_bit else raw_word
    raise ProtocolError(f"unsupported SAMPLE_FORMAT_ID: {sample_format_id}")


class ProtocolStreamDecoder:
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

            if self._buffer[2] != VERSION:
                del self._buffer[0]
                self.discarded_bytes += 1
                self.rejected_frames += 1
                continue

            msg_type = self._buffer[3]
            body_length = int.from_bytes(self._buffer[4:6], "little")
            if msg_type == TYPE_MEASUREMENT:
                length_ok = self.MIN_BODY_LENGTH <= body_length <= self.MAX_BODY_LENGTH
            elif msg_type == TYPE_DEVICE_INFO:
                length_ok = body_length == _CONTROL_HEADER.size + _DEVICE_INFO.size
            elif msg_type == TYPE_ACK:
                length_ok = body_length == 7
            elif msg_type in COMMAND_TYPES:
                length_ok = body_length == (5 if msg_type == TYPE_SET_PROFILE else 4)
            else:
                length_ok = False
            if not length_ok:
                del self._buffer[0]
                self.discarded_bytes += 1
                self.rejected_frames += 1
                continue

            frame_length = 2 + body_length + 2
            if len(self._buffer) < frame_length:
                break

            candidate = bytes(self._buffer[:frame_length])
            try:
                if msg_type == TYPE_MEASUREMENT:
                    item = decode_measurement(candidate)
                elif msg_type == TYPE_DEVICE_INFO:
                    item = decode_device_info(candidate)
                elif msg_type == TYPE_ACK:
                    item = decode_ack(candidate)
                else:
                    item = decode_command(candidate)
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


# Backwards-compatible name retained for telemetry-only callers.
MeasurementStreamDecoder = ProtocolStreamDecoder
