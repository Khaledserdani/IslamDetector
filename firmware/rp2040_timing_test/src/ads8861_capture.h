#pragma once

#include <stdbool.h>
#include <stdint.h>
#include "hardware/pio.h"

#define ADS8861_CONVST_PIN 8u
#define ADS8861_SCLK_PIN   9u
#define ADS8861_DOUT_PIN   10u
#define ADS8861_MARKER_PIN 5u

// Configure one PIO state machine for ADS8861 3-wire CS mode.
// DIN must be tied to DVDD externally. This function does not enable TX.
bool ads8861_capture_init(PIO pio, uint sm);

// Non-blocking read of one raw, right-justified 16-bit two's-complement sample.
bool ads8861_capture_try_read(PIO pio, uint sm, uint16_t *raw_sample);
