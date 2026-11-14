# RP2040 Rev A — Logic Timing Test v0.1

## Purpose

This is an executable timing prototype for the Rev A acquisition controller. The default build validates phase-locked TX and sample-marker edges. An optional, disabled-by-default PIO capture engine is designed to read eight ADS8861 decay windows from one TX pulse. This is **not** metal-detector firmware and has not been verified on physical ADC hardware.

## Pin map for the Waveshare RP2040-Zero

| RP2040 GPIO | Function | Notes |
|---|---|---|
| GP4 | TX_TEST | 20 µs logic pulse at 100 Hz; logic-only output |
| GP5 | SAMPLE_MARKER | Edge occurs at TX pulse width + one delay from the 8-point profile |
| GP6 | PIO_ECHO | 128 ns PIO response pulse after GP5 test-marker falling edge |
| USB-C | USB CDC console | Send R, S, I, or ? |

GP4 and GP5 are PWM channels A/B of the same RP2040 PWM slice (slice 2), so both use the same counter. GP5's compare value changes at PWM wrap to step through the eight delay points. The test PIO program watches GP5 and emits the response pulse on GP6. The separate ADS8861 capture PIO watches GP4 TX falling edge and captures the eight windows within that same pulse.

## Safe use

- Firmware boots with outputs disabled.
- Send R over USB serial to start the logic timing test.
- Send S to stop; GP4 is forced low.
- Send I to read status.
- **Do not connect GP4 to a MOSFET gate driver, MOSFET, coil, or 12 V circuit.** It is only a 3.3 V logic test output.
- GP6 is only a marker echo. The optional ADC capture path uses GP4 falling edge and remains disabled by default.

## Build

The GitHub Actions workflow builds the UF2 with the Raspberry Pi Pico SDK and publishes it as IslamDetector-RevA-RP2040-Timing-Test-UF2. CI also validates the UF2 block magic, complete block numbering, payload bounds, non-overlapping target ranges, and RP2040 family ID `0xE48BFF56` with `tools/verify_uf2.py` before uploading it.

## Acceptance test on hardware

Use a logic analyzer or oscilloscope to verify:
1. GP4 pulse width is 20 µs and repetition is 100 Hz (at the required 125 MHz system clock). PWM tick resolution is 160 ns.
2. GP5 falling edge occurs at 20 µs + the active delay, quantized to the 160 ns PWM tick.
3. Delay sequence cycles through 8, 12, 16, 24, 36, 52, 72, 100 µs.
4. GP6 responds consistently to GP5 with fixed PIO latency.
5. No pulses occur before command R; command S forces GP4 low.

Measured timing and jitter must be recorded from the actual RP2040-Zero board. No timing accuracy is claimed until measured.

## ADS8861 PIO capture driver (compiled, disabled by default)

One falling edge on GP4 starts a complete eight-window decay capture within the same TX pulse:
- GP4=TX_TEST; GP8=CONVST; GP9=SCLK; GP10=DOUT. ADS8861 DIN must be strapped HIGH for 3-wire CS mode.
- Delay points from TX falling are nominally 8/12/16/24/36/52/72/100 µs. The first delay count assumes the RP2040's two-cycle GPIO input synchronizer; the actual offset must be measured and trimmed on hardware.
- Four preloaded TX FIFO words contain the eight 12-bit delay counts. PIO autopull threshold is 24 bits; RX DMA drains the normal four-word FIFO into an eight-word RAM buffer; the TX FIFO remains available for the delay schedule.
- CONVST HIGH is 96 PIO cycles at125MHz =768ns, exceeding tconv-max=710ns. The PIO waits120ns after CONVST falls before the first SCLK sample, exceeding t_d-CNV-DO=12.3ns max.
- SCLK is 7 cycles HIGH +7 cycles LOW =112ns period, about8.929MHz with 50% duty. Sixteen bits take224 cycles=1.792µs. The minimum 4µs spacing between sample points leaves time for conversion and readout; tACQ=290ns is also exceeded. These are instruction-budget calculations, not measured timings.
- The eight raw16 samples are drained by the main loop and printed as one ADS8861_SWEEP_RAW16 line per TX pulse.
- ENABLE_ADS8861_CAPTURE=0 until the physical ADC, analog protection, supplies and wiring are installed and reviewed. Do not enable against floating pins or without the physical ADC.
- PIO capture is stopped before GP4 is forced low, preventing a STOP command from being mistaken for a new TX falling edge.
- This is a firmware compile milestone only; no hardware loopback, analog accuracy, timing jitter or ADC performance has yet been measured.
