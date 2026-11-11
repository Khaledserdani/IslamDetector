#pragma once

#include <stdbool.h>
#include <stdint.h>
#include "hardware/pio.h"

#define ADS8861_CONVST_PIN  8u
#define ADS8861_SCLK_PIN    9u
#define ADS8861_DOUT_PIN    10u
#define ADS8861_TX_FALL_PIN 4u
#define ADS8861_SWEEP_SAMPLES 8u

// One GP4 TX falling edge captures all eight decay windows in the same pulse.
// DMA drains the PIO RX FIFO; the PIO TX FIFO holds the eight delay values.
// ADS8861 DIN must be tied to DVDD for 3-wire CS mode. Not a TX gate driver.
bool ads8861_capture_init(PIO pio, uint sm);
bool ads8861_capture_start(PIO pio, uint sm);
void ads8861_capture_stop(PIO pio, uint sm);

// Non-blocking: returns one completed eight-sample raw sweep and re-arms PIO/DMA.
bool ads8861_capture_try_read_sweep(
    PIO pio, uint sm, uint16_t samples[ADS8861_SWEEP_SAMPLES]);
