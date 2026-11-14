# ESP32-S3 Rev A bridge — protocol core

**Status:** portable C frame decoder and DEVICE_INFO-gated session layer implemented and host-tested. This directory is not yet a complete ESP-IDF application and does not yet configure the ESP32-S3 UART peripheral, FreeRTOS RX ring buffer, Wi-Fi server, or Android JSON endpoints.

## Component

`components/rev_a_protocol` is an ESP-IDF-compatible component with no dependency on ESP-IDF headers. It can also be compiled with a host C compiler. It accepts arbitrary UART byte fragments and recognizes:

- `MEASUREMENT` (type `0x10`), including one-to-eight raw 16-bit samples.
- `DEVICE_INFO` (type `0x82`), including ADC model, sample format, resolution, input mode, VREF, active profile and profile CRC32.

The decoder validates SYNC, protocol version, body length, sample count, valid mask, sweep-complete flag, non-zero pulse rate, CRC-16/CCITT-FALSE and the supported ADC metadata combinations. It preserves raw sample words. `rev_a_interpret_sample()` converts a raw word only when the DEVICE_INFO format and resolution are supplied; ADS8861 is signed 16-bit two's-complement, while ADS7054 is right-justified signed 14-bit.

## Command frame encoder

`rev_a_encode_command()` builds CRC-protected HELLO, GET_INFO, START, STOP and SELF_TEST frames with no payload, plus SET_PROFILE with exactly one profile-ID byte. The encoder does not decide which profile IDs are safe; the RP2040 firmware must enforce its own allowlist. ACK generation/handling and the RP2040 command receiver are not implemented yet.

## Integration contract

1. Create one `rev_a_parser_t` per UART stream and call `rev_a_parser_feed()` for every byte block returned by the ESP-IDF UART driver.
2. Pass each decoded frame to `rev_a_session_accept_frame()` from the parser callback.
3. A valid `DEVICE_INFO` opens/refreshes the session; `MEASUREMENT` is rejected until metadata is valid. Each accepted record carries a metadata snapshot and generation number.
4. Call `rev_a_session_invalidate_device_info()` after UART overflow, reconnect, framing loss or RP2040 reset; request DEVICE_INFO again before accepting measurements.
5. Copy callback/session output into a bounded queue; the parser callback runs synchronously and must not block.
6. Preserve raw words, sequence, timestamp, profile, validity mask and metadata. Interpret only VALID_MASK bits; never replace invalid windows with zero.

## Host tests

The C tests cover the CRC known vector, valid measurement and DEVICE_INFO frames, rejected inconsistent ADC metadata, 16-bit and 14-bit signed conversion, fragmented input, concatenated frames, noise and recovery after a corrupt frame. The session tests reject measurements before DEVICE_INFO, preserve raw invalid windows, snapshot metadata, and require a fresh DEVICE_INFO after session invalidation.

The CI compiles with strict warnings and executes the test. This proves the portable decoder on the CI host only. ESP-IDF UART integration, FreeRTOS task behavior, UART loopback, Wi-Fi load, and the physical RP2040-to-ESP32 link remain untested.


## ESP-IDF project and UART task

This directory contains a standalone ESP-IDF project for ESP32-S3. The rev_a_uart_bridge component owns UART events, RX/TX ring buffers, parser/session integration, DEVICE_INFO retry, and a bounded measurement queue.

UART defaults to disabled and TX/RX GPIO -1. No development-board pins are assumed. Enable UART1 or UART2 only after checking the exact board schematic and setting both GPIOs in idf.py menuconfig. UART0 remains reserved for the console.

Default transport: 921600 baud, 8N1. The bridge sends HELLO/GET_INFO, retries GET_INFO until valid DEVICE_INFO arrives, invalidates metadata after UART faults or parser rejection, and exposes measurement snapshots through a FreeRTOS queue.

This is not yet complete detector firmware: ACK parsing, RP2040 command receiver/DEVICE_INFO transmitter, Wi-Fi/WebServer JSON endpoints, Android integration, and physical UART loopback remain outstanding. A successful build does not prove a physical connection.
