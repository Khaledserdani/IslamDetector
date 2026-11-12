# ESP32-S3 Rev A bridge — protocol core

**Status:** portable C frame decoder implemented and host-tested. This directory is not yet a complete ESP-IDF application and does not yet configure the ESP32-S3 UART peripheral, Wi-Fi server, or Android JSON endpoints.

## Component

`components/rev_a_protocol` is an ESP-IDF-compatible component with no dependency on ESP-IDF headers. It can also be compiled with a host C compiler. It accepts arbitrary UART byte fragments and recognizes:

- `MEASUREMENT` (type `0x10`), including one-to-eight raw 16-bit samples.
- `DEVICE_INFO` (type `0x82`), including ADC model, sample format, resolution, input mode, VREF, active profile and profile CRC32.

The decoder validates SYNC, protocol version, body length, sample count, valid mask, sweep-complete flag, non-zero pulse rate, CRC-16/CCITT-FALSE and the supported ADC metadata combinations. It preserves raw sample words. `rev_a_interpret_sample()` converts a raw word only when the DEVICE_INFO format and resolution are supplied; ADS8861 is signed 16-bit two's-complement, while ADS7054 is right-justified signed 14-bit.

## Integration contract

1. Create one `rev_a_parser_t` per UART stream and call `rev_a_parser_feed()` for every byte block returned by the ESP-IDF UART driver.
2. On `DEVICE_INFO`, store the complete metadata with the active acquisition session before interpreting any sample.
3. Do not interpret or merge `MEASUREMENT` frames until a valid DEVICE_INFO has been received for that session.
4. Copy callback data into a bounded queue; the parser callback runs synchronously in the caller's task and must not block.
5. Preserve `raw_word`, frame sequence, timestamp, profile ID, validity flags and metadata in logs. Never replace invalid windows with zero.
6. On UART overflow or framing loss, count the event and re-request DEVICE_INFO before opening a new data session.

## Host tests

The C test covers the CRC known vector, valid measurement and DEVICE_INFO frames, rejected inconsistent ADC metadata, 16-bit and 14-bit signed conversion, fragmented input, concatenated frames, noise and recovery after a corrupt frame.

The CI compiles with strict warnings and executes the test. This proves the portable decoder on the CI host only. ESP-IDF UART integration, FreeRTOS task behavior, UART loopback, Wi-Fi load, and the physical RP2040-to-ESP32 link remain untested.
