import struct
import unittest

from verify_uf2 import (
    RP2040_FAMILY_ID,
    UF2Error,
    UF2_MAGIC_END,
    UF2_MAGIC_START0,
    UF2_MAGIC_START1,
    UF2_FLAG_FAMILY_ID_PRESENT,
    verify_uf2,
)


def make_block(number=0, total=1, target=0x10000000, payload=b"\\x00" * 256,
               family=RP2040_FAMILY_ID, flags=UF2_FLAG_FAMILY_ID_PRESENT):
    block = bytearray(512)
    struct.pack_into(
        "<8I", block, 0, UF2_MAGIC_START0, UF2_MAGIC_START1, flags, target,
        len(payload), number, total, family
    )
    block[32 : 32 + len(payload)] = payload
    struct.pack_into("<I", block, 508, UF2_MAGIC_END)
    return bytes(block)


class VerifyUF2Tests(unittest.TestCase):
    def test_valid_two_block_rp2040_image(self):
        image = make_block(number=0, total=2) + make_block(number=1, total=2, target=0x10000100)
        result = verify_uf2(image)
        self.assertEqual(result["blocks"], 2)
        self.assertEqual(result["payload_bytes"], 512)
        self.assertEqual(result["family_id"], RP2040_FAMILY_ID)
        self.assertEqual(result["address_start"], 0x10000000)
        self.assertEqual(result["address_end"], 0x10000200)

    def test_rejects_truncated_file(self):
        with self.assertRaises(UF2Error):
            verify_uf2(b"\\x00" * 511)

    def test_rejects_bad_magic(self):
        block = bytearray(make_block())
        block[0] ^= 0x01
        with self.assertRaises(UF2Error):
            verify_uf2(bytes(block))

    def test_rejects_wrong_family(self):
        with self.assertRaises(UF2Error):
            verify_uf2(make_block(family=0x12345678))

    def test_rejects_missing_family_flag(self):
        with self.assertRaises(UF2Error):
            verify_uf2(make_block(flags=0))

    def test_rejects_duplicate_block_numbers(self):
        image = make_block(number=0, total=2) + make_block(number=0, total=2, target=0x10000100)
        with self.assertRaises(UF2Error):
            verify_uf2(image)

    def test_rejects_overlapping_address_ranges(self):
        image = make_block(number=0, total=2) + make_block(number=1, total=2, target=0x10000080)
        with self.assertRaises(UF2Error):
            verify_uf2(image)

    def test_rejects_incorrect_total_count(self):
        with self.assertRaises(UF2Error):
            verify_uf2(make_block(total=2))

    def test_rejects_oversized_payload(self):
        with self.assertRaises(UF2Error):
            verify_uf2(make_block(payload=b"\\x00" * 480))


if __name__ == "__main__":
    unittest.main()
