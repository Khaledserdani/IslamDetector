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

typedef enum {
    ADS8861_SWEEP_NOT_READY = 0,
    ADS8861_SWEEP_READY = 1,
    ADS8861_SWEEP_READY_REARM_FAILED = 2
} ads8861_sweep_result_t;

// Non-blocking: returns a completed sweep and reports whether re-arming succeeded.
ads8861_sweep_result_t ads8861_capture_try_read_sweep(
    PIO pio, uint sm, uint16_t samples[ADS8861_SWEEP_SAMPLES]);
