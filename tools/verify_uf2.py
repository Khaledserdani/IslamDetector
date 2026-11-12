#!/usr/bin/env python3
"""Validate UF2 block structure and an expected RP2040 family ID."""
from __future__ import annotations

import argparse
import struct
from pathlib import Path

UF2_BLOCK_SIZE = 512
UF2_MAGIC_START0 = 0x0A324655
UF2_MAGIC_START1 = 0x9E5D5157
UF2_MAGIC_END = 0x0AB16F30
UF2_FLAG_FAMILY_ID_PRESENT = 0x00002000
RP2040_FAMILY_ID = 0xE48BFF56
MAX_PAYLOAD_SIZE = 476


class UF2Error(ValueError):
    """Raised when a UF2 image is malformed or targets the wrong family."""


def verify_uf2(data: bytes, expected_family_id: int = RP2040_FAMILY_ID) -> dict[str, int]:
    if not data or len(data) % UF2_BLOCK_SIZE:
        raise UF2Error("file size must be a non-zero multiple of 512 bytes")

    block_count = len(data) // UF2_BLOCK_SIZE
    seen_numbers: set[int] = set()
    address_ranges: list[tuple[int, int]] = []
    family_ids: set[int] = set()
    payload_bytes = 0

    for index in range(block_count):
        offset = index * UF2_BLOCK_SIZE
        block = data[offset : offset + UF2_BLOCK_SIZE]
        magic0, magic1, flags, target, payload_size, block_no, total_blocks, family_id = struct.unpack_from(
            "<8I", block, 0
        )
        end_magic = struct.unpack_from("<I", block, 508)[0]

        if (magic0, magic1, end_magic) != (UF2_MAGIC_START0, UF2_MAGIC_START1, UF2_MAGIC_END):
            raise UF2Error(f"block {index}: invalid UF2 magic")
        if total_blocks != block_count:
            raise UF2Error(f"block {index}: total-block count does not match file")
        if block_no >= total_blocks or block_no in seen_numbers:
            raise UF2Error(f"block {index}: invalid or duplicate block number")
        if not (flags & UF2_FLAG_FAMILY_ID_PRESENT):
            raise UF2Error(f"block {index}: family ID flag is missing")
        if family_id != expected_family_id:
            raise UF2Error(f"block {index}: family ID 0x{family_id:08X} is not 0x{expected_family_id:08X}")
        if payload_size == 0 or payload_size > MAX_PAYLOAD_SIZE or payload_size % 4:
            raise UF2Error(f"block {index}: invalid payload size {payload_size}")
        if target % 4 or target + payload_size > 0x1_0000_0000:
            raise UF2Error(f"block {index}: invalid target address range")

        seen_numbers.add(block_no)
        address_ranges.append((target, target + payload_size))
        family_ids.add(family_id)
        payload_bytes += payload_size

    if seen_numbers != set(range(block_count)):
        raise UF2Error("block numbers are not a complete zero-based sequence")

    address_ranges.sort()
    for previous, current in zip(address_ranges, address_ranges[1:]):
        if previous[1] > current[0]:
            raise UF2Error("UF2 target address ranges overlap")

    return {
        "blocks": block_count,
        "payload_bytes": payload_bytes,
        "family_id": expected_family_id,
        "address_start": address_ranges[0][0],
        "address_end": address_ranges[-1][1],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("uf2", type=Path)
    parser.add_argument("--family-id", type=lambda value: int(value, 0), default=RP2040_FAMILY_ID)
    args = parser.parse_args()
    try:
        result = verify_uf2(args.uf2.read_bytes(), args.family_id)
    except (OSError, UF2Error) as error:
        parser.error(str(error))
    print(
        "UF2 valid: "
        f"{result['blocks']} blocks, {result['payload_bytes']} payload bytes, "
        f"family=0x{result['family_id']:08X}, "
        f"address=0x{result['address_start']:08X}..0x{result['address_end']:08X}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
