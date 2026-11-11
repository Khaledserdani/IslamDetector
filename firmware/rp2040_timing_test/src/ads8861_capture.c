#include <stddef.h>
#include "ads8861_capture.h"

#include "hardware/gpio.h"
#include "hardware/clocks.h"
#include "hardware/pio.h"
#include "ads8861_capture.pio.h"

#define ADS8861_SYS_CLOCK_HZ 125000000u

// Each 12-bit field is the number of PIO delay-loop iterations minus one.
// The first value assumes the 2-cycle GPIO synchronizer; hardware timing
// measurement must confirm or trim this first offset.
static const uint32_t delay_words[4] = {
    0x000B23E3u, // 995, 178
    0x002A60B2u, // 178, 678
    0x0068E49Au, // 1178, 1678
    0x00C6A882u  // 2178, 3178
};

static PIO capture_pio;
static uint capture_sm;
static uint capture_offset;
static pio_sm_config capture_config;
static bool capture_configured = false;

static void capture_set_pin_directions(PIO pio, uint sm) {
    pio_sm_set_consecutive_pindirs(pio, sm, ADS8861_CONVST_PIN, 1u, true);
    pio_sm_set_consecutive_pindirs(pio, sm, ADS8861_SCLK_PIN, 1u, true);
    pio_sm_set_consecutive_pindirs(pio, sm, ADS8861_DOUT_PIN, 1u, false);
}

static void capture_force_idle(PIO pio, uint sm) {
    pio_sm_set_pins_with_mask(
        pio, sm, 0u,
        (1u << ADS8861_CONVST_PIN) | (1u << ADS8861_SCLK_PIN));
}

bool ads8861_capture_init(PIO pio, uint sm) {
    if (pio == NULL || sm >= NUM_PIO_STATE_MACHINES ||
        clock_get_hz(clk_sys) != ADS8861_SYS_CLOCK_HZ) {
        return false;
    }
    if (!pio_can_add_program(pio, &ads8861_capture_program)) {
        return false;
    }

    capture_offset = pio_add_program(pio, &ads8861_capture_program);
    capture_pio = pio;
    capture_sm = sm;
    capture_config =
        ads8861_capture_program_get_default_config(capture_offset);

    sm_config_set_set_pins(&capture_config, ADS8861_CONVST_PIN, 1u);
    sm_config_set_sideset_pins(&capture_config, ADS8861_SCLK_PIN);
    sm_config_set_in_pins(&capture_config, ADS8861_DOUT_PIN);
    sm_config_set_in_shift(&capture_config, false, true, 16u);
    sm_config_set_out_shift(&capture_config, true, true, 24u);
    sm_config_set_fifo_join(&capture_config, PIO_FIFO_JOIN_RX);
    sm_config_set_clkdiv(&capture_config, 1.0f);

    pio_gpio_init(pio, ADS8861_CONVST_PIN);
    pio_gpio_init(pio, ADS8861_SCLK_PIN);
    pio_gpio_init(pio, ADS8861_DOUT_PIN);
    // GP4 remains PWM-muxed for TX_TEST; WAIT GPIO reads the physical pad.
    gpio_set_input_enabled(ADS8861_TX_FALL_PIN, true);
    gpio_set_input_enabled(ADS8861_DOUT_PIN, true);

    pio_sm_init(pio, sm, capture_offset, &capture_config);
    capture_set_pin_directions(pio, sm);
    pio_sm_clear_fifos(pio, sm);
    capture_force_idle(pio, sm);

    capture_configured = true;
    return true;
}

bool ads8861_capture_start(PIO pio, uint sm) {
    if (!capture_configured || pio != capture_pio || sm != capture_sm ||
        clock_get_hz(clk_sys) != ADS8861_SYS_CLOCK_HZ) {
        return false;
    }

    pio_sm_set_enabled(pio, sm, false);
    pio_sm_init(pio, sm, capture_offset, &capture_config);
    capture_set_pin_directions(pio, sm);
    pio_sm_clear_fifos(pio, sm);
    capture_force_idle(pio, sm);

    for (size_t i = 0u; i < 4u; ++i) {
        pio_sm_put_blocking(pio, sm, delay_words[i]);
    }

    pio_sm_set_enabled(pio, sm, true);
    return true;
}

void ads8861_capture_stop(PIO pio, uint sm) {
    if (capture_configured && pio == capture_pio && sm == capture_sm) {
        pio_sm_set_enabled(pio, sm, false);
        capture_force_idle(pio, sm);
        pio_sm_clear_fifos(pio, sm);
    }
}

bool ads8861_capture_try_read(PIO pio, uint sm, uint16_t *raw_sample) {
    if (pio == NULL || raw_sample == NULL || sm >= NUM_PIO_STATE_MACHINES) {
        return false;
    }
    if (pio_sm_is_rx_fifo_empty(pio, sm)) {
        return false;
    }
    *raw_sample = (uint16_t)(pio_sm_get(pio, sm) & 0xFFFFu);
    return true;
}
