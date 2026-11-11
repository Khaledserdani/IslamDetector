# RP2040 Rev A — Logic Timing Test v0.1

## Purpose

This is the first executable timing prototype for the Rev A acquisition controller. It validates phase-locked TX and sample-marker edges and verifies that a PIO state machine can respond to the sample marker. It is **not** a metal detector firmware and does not read an ADC.

## Pin map for the Waveshare RP2040-Zero

| RP2040 GPIO | Function | Notes |
|---|---|---|
| GP4 | TX_TEST | 20 µs logic pulse at 100 Hz; logic-only output |
| GP5 | SAMPLE_MARKER | Edge occurs at TX pulse width + one delay from the 8-point profile |
| GP6 | PIO_ECHO | Short PIO pulse after SAMPLE_MARKER falling edge |
| USB-C | USB CDC console | Send R, S, I, or ? |

GP4 and GP5 are PWM channels A/B of the same RP2040 PWM slice (slice 2), so both use the same counter. GP5's compare value changes at PWM wrap to step through the eight delay points. The PIO program watches GP5 and emits the response pulse on GP6.

## Safe use

- Firmware boots with outputs disabled.
- Send R over USB serial to start the logic timing test.
- Send S to stop; GP4 is forced low.
- Send I to read status.
- **Do not connect GP4 to a MOSFET gate driver, MOSFET, coil, or 12 V circuit.** It is only a 3.3 V logic test output.
- GP6 is only a marker echo, not an ADC conversion trigger for a selected ADC yet.

## Build

The GitHub Actions workflow builds the UF2 with the Raspberry Pi Pico SDK and publishes it as IslamDetector-RevA-RP2040-Timing-Test-UF2.

## Acceptance test on hardware

Use a logic analyzer or oscilloscope to verify:
1. GP4 pulse width is 20 µs and repetition is 100 Hz.
2. GP5 falling edge occurs at 20 µs + the active delay.
3. Delay sequence cycles through 8, 12, 16, 24, 36, 52, 72, 100 µs.
4. GP6 responds consistently to GP5 with fixed PIO latency.
5. No pulses occur before command R; command S forces GP4 low.

Measured timing and jitter must be recorded from the actual RP2040-Zero board. No timing accuracy is claimed until measured.
