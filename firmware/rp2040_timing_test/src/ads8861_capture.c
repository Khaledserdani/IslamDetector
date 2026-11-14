#include <stddef.h>
#include "ads8861_capture.h"

#include "hardware/gpio.h"
#include "hardware/clocks.h"
#include "hardware/dma.h"
#include "hardware/pio.h"
#include "hardware/pio_instructions.h"
#include "ads8861_capture.pio.h"

#define ADS8861_SYS_CLOCK_HZ 125000000u

// Each 12-bit field is the number of PIO delay-loop iterations minus one.
// The first value assumes the 2-cycle GPIO synchronizer; hardware timing
// measurement must confirm or trim this first offset.
static const uint32_t delay_words[4] = {
    0x000A23E3u, // 995, 162
    0x002960A2u, // 162, 662
    0x0067E48Au, // 1162, 1662
    0x00C5A872u  // 2162, 3162
};

static PIO capture_pio;
static uint capture_sm;
static uint capture_offset;
static pio_sm_config capture_config;
static int capture_dma = -1;
static dma_channel_config capture_dma_config;
static uint32_t capture_buffer[ADS8861_SWEEP_SAMPLES];
static bool capture_configured = false;
static bool capture_active = false;

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

static bool capture_arm_next_sweep(PIO pio, uint sm) {
    if (clock_get_hz(clk_sys) != ADS8861_SYS_CLOCK_HZ) {
        return false;
    }

    pio_sm_set_enabled(pio, sm, false);
    pio_sm_init(pio, sm, capture_offset, &capture_config);
    capture_set_pin_directions(pio, sm);
    pio_sm_clear_fifos(pio, sm);
    capture_force_idle(pio, sm);

    // Load the first word into OSR explicitly, avoiding any dependency on
    // the reset value of the OSR shift counter. The remaining three words
    // stay in TX FIFO; autopull occurs after each pair of 12-bit OUTs.
    pio_sm_put_blocking(pio, sm, delay_words[0]);
    pio_sm_exec(pio, sm, pio_encode_pull(false, true));
    for (size_t i = 1u; i < 4u; ++i) {
        pio_sm_put_blocking(pio, sm, delay_words[i]);
    }

    // RX DMA drains the normal four-word PIO FIFO while the PIO captures
    // eight samples. This avoids disabling TX FIFO with PIO_FIFO_JOIN_RX.
    dma_channel_configure(
        (uint)capture_dma, &capture_dma_config, capture_buffer,
        &pio->rxf[sm], ADS8861_SWEEP_SAMPLES, false);
    dma_start_channel_mask(1u << (uint)capture_dma);
    pio_sm_set_enabled(pio, sm, true);
    capture_active = true;
    return true;
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
    // Keep TX and RX FIFOs separate: four delay words TX, DMA-drained RX.
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

    capture_dma = dma_claim_unused_channel(true);
    capture_dma_config = dma_channel_get_default_config((uint)capture_dma);
    channel_config_set_transfer_data_size(&capture_dma_config, DMA_SIZE_32);
    channel_config_set_read_increment(&capture_dma_config, false);
    channel_config_set_write_increment(&capture_dma_config, true);
    channel_config_set_dreq(
        &capture_dma_config, pio_get_dreq(pio, sm, false));

    capture_configured = true;
    return true;
}

bool ads8861_capture_start(PIO pio, uint sm) {
    if (!capture_configured || pio != capture_pio || sm != capture_sm) {
        return false;
    }
    return capture_arm_next_sweep(pio, sm);
}

void ads8861_capture_stop(PIO pio, uint sm) {
    if (capture_configured && pio == capture_pio && sm == capture_sm) {
        pio_sm_set_enabled(pio, sm, false);
        if (capture_active && dma_channel_is_busy((uint)capture_dma)) {
            dma_channel_abort((uint)capture_dma);
        }
        capture_active = false;
        capture_force_idle(pio, sm);
        pio_sm_clear_fifos(pio, sm);
    }
}

ads8861_sweep_result_t ads8861_capture_try_read_sweep(
    PIO pio, uint sm, uint16_t samples[ADS8861_SWEEP_SAMPLES]) {
    if (!capture_configured || !capture_active || pio != capture_pio ||
        sm != capture_sm || samples == NULL ||
        dma_channel_is_busy((uint)capture_dma)) {
        return ADS8861_SWEEP_NOT_READY;
    }

    for (size_t i = 0u; i < ADS8861_SWEEP_SAMPLES; ++i) {
        samples[i] = (uint16_t)(capture_buffer[i] & 0xFFFFu);
    }

    // Re-arm before the next TX pulse. A failed re-arm is returned explicitly
    // so the caller can stop pulse generation instead of silently going idle.
    capture_active = false;
    return capture_arm_next_sweep(pio, sm)
        ? ADS8861_SWEEP_READY
        : ADS8861_SWEEP_READY_REARM_FAILED;
}
