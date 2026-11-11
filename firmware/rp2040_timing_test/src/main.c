#include <stdio.h>
#include <stdint.h>

#include "pico/stdlib.h"
#include "hardware/clocks.h"
#include "hardware/gpio.h"
#include "hardware/irq.h"
#include "hardware/pio.h"
#include "hardware/pwm.h"

#include "sample_marker_echo.pio.h"

#define TX_TEST_PIN       4u
#define SAMPLE_MARKER_PIN 5u
#define PIO_ECHO_PIN      6u

#define PWM_WRAP_VALUE    62499u
#define START_PULSE_US    20u
#define START_RATE_HZ     100u

static const uint16_t sample_delays_us[8] = {
    8u, 12u, 16u, 24u, 36u, 52u, 72u, 100u
};

static uint slice_num;
static float pwm_divider;
static uint16_t pulse_ticks;
static uint16_t sample_compare_ticks[8];
static volatile uint8_t profile_index = 0u;
static volatile bool running = false;

static uint16_t us_to_pwm_ticks(uint32_t microseconds) {
    const float tick_hz = (float)clock_get_hz(clk_sys) / pwm_divider;
    const float raw_ticks = ((float)microseconds * tick_hz) / 1000000.0f;
    return (uint16_t)(raw_ticks + 0.5f);
}

static void pwm_wrap_isr(void) {
    pwm_clear_irq(slice_num);

    if (!running) {
        return;
    }

    profile_index = (uint8_t)((profile_index + 1u) & 0x07u);
    // Precomputed before PWM starts: keep floating-point work out of the ISR.
    // The double-buffered compare value takes effect at the next wrap.
    pwm_set_chan_level(slice_num, PWM_CHAN_B,
                       sample_compare_ticks[profile_index]);
}

static void timing_outputs_stop(void) {
    running = false;

    pwm_set_irq_enabled(slice_num, false);
    pwm_set_enabled(slice_num, false);

    gpio_set_function(TX_TEST_PIN, GPIO_FUNC_SIO);
    gpio_set_dir(TX_TEST_PIN, GPIO_OUT);
    gpio_put(TX_TEST_PIN, 0);

    gpio_set_function(SAMPLE_MARKER_PIN, GPIO_FUNC_SIO);
    gpio_set_dir(SAMPLE_MARKER_PIN, GPIO_OUT);
    gpio_put(SAMPLE_MARKER_PIN, 1);

    printf("STOP: TX_TEST_PIN forced LOW; sample marker idle HIGH.\n");
}

static void timing_outputs_start(void) {
    if (running) {
        return;
    }

    gpio_set_function(TX_TEST_PIN, GPIO_FUNC_PWM);
    gpio_set_function(SAMPLE_MARKER_PIN, GPIO_FUNC_PWM);

    slice_num = pwm_gpio_to_slice_num(TX_TEST_PIN);
    // At the standard 125 MHz RP2040 system clock:
    // 125 MHz / 20 / 62500 = exactly 100 Hz.
    // One PWM tick is 160 ns; all eight delays are precomputed.
    if (clock_get_hz(clk_sys) != 125000000u) {
        printf("ERROR: timing test expects 125 MHz system clock; got %u Hz.\n",
               clock_get_hz(clk_sys));
        return;
    }
    pwm_divider = 20.0f;

    pulse_ticks = us_to_pwm_ticks(START_PULSE_US);
    for (uint8_t i = 0u; i < 8u; ++i) {
        const uint32_t compare =
            us_to_pwm_ticks(START_PULSE_US + sample_delays_us[i]);
        if (compare >= PWM_WRAP_VALUE) {
            printf("ERROR: sample compare exceeds PWM period.\n");
            return;
        }
        sample_compare_ticks[i] = (uint16_t)compare;
    }
    profile_index = 0u;

    pwm_config config = pwm_get_default_config();
    pwm_config_set_clkdiv(&config, pwm_divider);
    pwm_config_set_wrap(&config, PWM_WRAP_VALUE);

    pwm_init(slice_num, &config, false);

    pwm_set_chan_level(slice_num, PWM_CHAN_A, pulse_ticks);
    pwm_set_chan_level(slice_num, PWM_CHAN_B, sample_compare_ticks[0]);

    pwm_clear_irq(slice_num);
    pwm_set_irq_enabled(slice_num, true);
    running = true;
    pwm_set_enabled(slice_num, true);

    printf("RUN: logic-only timing test started. rate=%u Hz, TX pulse=%u us, "
           "PWM tick=160 ns, delay profile=8/12/16/24/36/52/72/100 us.\n",
           START_RATE_HZ, START_PULSE_US);
    printf("Pins: GP4=TX_TEST (logic only), GP5=SAMPLE_MARKER, GP6=PIO_ECHO.\n");
    printf("Do NOT connect GP4 to a gate driver or coil.\n");
}

static void setup_pio_echo(void) {
    PIO pio = pio0;
    const uint sm = pio_claim_unused_sm(pio, true);
    const uint offset = pio_add_program(pio, &sample_marker_echo_program);

    pio_sm_config config = sample_marker_echo_program_get_default_config(offset);
    sm_config_set_set_pins(&config, PIO_ECHO_PIN, 1u);
    sm_config_set_clkdiv(&config, 1.0f);

    pio_gpio_init(pio, PIO_ECHO_PIN);
    pio_sm_set_consecutive_pindirs(pio, sm, PIO_ECHO_PIN, 1u, true);

    gpio_set_input_enabled(SAMPLE_MARKER_PIN, true);

    pio_sm_init(pio, sm, offset, &config);
    pio_sm_set_enabled(pio, sm, true);
}

static void print_help(void) {
    printf("\nISLAM REV A - RP2040 LOGIC TIMING TEST v0.1\n");
    printf("R = start logic-only pulse/marker test\n");
    printf("S = stop and force TX test pin LOW\n");
    printf("I = show status\n");
    printf("? = help\n\n");
}

int main(void) {
    stdio_init_all();
    sleep_ms(1800);

    gpio_init(TX_TEST_PIN);
    gpio_set_dir(TX_TEST_PIN, GPIO_OUT);
    gpio_put(TX_TEST_PIN, 0);

    gpio_init(SAMPLE_MARKER_PIN);
    gpio_set_dir(SAMPLE_MARKER_PIN, GPIO_OUT);
    gpio_put(SAMPLE_MARKER_PIN, 1);

    setup_pio_echo();

    slice_num = pwm_gpio_to_slice_num(TX_TEST_PIN);
    irq_set_exclusive_handler(PWM_IRQ_WRAP, pwm_wrap_isr);
    irq_set_enabled(PWM_IRQ_WRAP, true);

    printf("Safe boot: no pulse is generated until command R.\n");
    print_help();

    while (true) {
        const int ch = getchar_timeout_us(0);
        if (ch == 'R' || ch == 'r') {
            timing_outputs_start();
        } else if (ch == 'S' || ch == 's') {
            timing_outputs_stop();
        } else if (ch == 'I' || ch == 'i') {
            printf("running=%u profile_index=%u pulse=%u us rate=%u Hz\n",
                   running ? 1u : 0u, profile_index,
                   START_PULSE_US, START_RATE_HZ);
        } else if (ch == '?' || ch == 'h' || ch == 'H') {
            print_help();
        }
        tight_loop_contents();
    }
}
