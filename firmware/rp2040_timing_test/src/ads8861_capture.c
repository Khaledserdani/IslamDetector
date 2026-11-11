#include "ads8861_capture.h"

#include "hardware/gpio.h"
#include "hardware/pio.h"
#include "ads8861_capture.pio.h"

bool ads8861_capture_init(PIO pio, uint sm) {
    if (pio == NULL || sm >= NUM_PIO_STATE_MACHINES) {
        return false;
    }
    if (!pio_can_add_program(pio, &ads8861_capture_program)) {
        return false;
    }

    const uint offset = pio_add_program(pio, &ads8861_capture_program);
    pio_sm_config config =
        ads8861_capture_program_get_default_config(offset);

    sm_config_set_set_pins(&config, ADS8861_CONVST_PIN, 1u);
    sm_config_set_sideset_pins(&config, ADS8861_SCLK_PIN);
    sm_config_set_in_pins(&config, ADS8861_DOUT_PIN);
    // Shift left so the first MSB-first bit ends in bit 15 after 16 clocks.
    sm_config_set_in_shift(&config, false, true, 16u);
    sm_config_set_fifo_join(&config, PIO_FIFO_JOIN_RX);
    sm_config_set_clkdiv(&config, 1.0f);

    pio_gpio_init(pio, ADS8861_CONVST_PIN);
    pio_gpio_init(pio, ADS8861_SCLK_PIN);
    pio_gpio_init(pio, ADS8861_DOUT_PIN);
    gpio_set_input_enabled(ADS8861_MARKER_PIN, true);
    gpio_set_input_enabled(ADS8861_DOUT_PIN, true);

    pio_sm_set_consecutive_pindirs(pio, sm, ADS8861_CONVST_PIN, 1u, true);
    pio_sm_set_consecutive_pindirs(pio, sm, ADS8861_SCLK_PIN, 1u, true);
    pio_sm_set_consecutive_pindirs(pio, sm, ADS8861_DOUT_PIN, 1u, false);

    pio_sm_init(pio, sm, offset, &config);
    pio_sm_clear_fifos(pio, sm);
    pio_sm_set_pins_with_mask(
        pio, sm, 0u,
        (1u << ADS8861_CONVST_PIN) | (1u << ADS8861_SCLK_PIN));
    pio_sm_set_enabled(pio, sm, true);
    return true;
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
