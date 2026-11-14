#include "esp_err.h"
#include "esp_log.h"
#include "rev_a_uart_bridge.h"
static const char *TAG = "islam_rev_a";
#if CONFIG_REV_A_UART_ENABLE
#if CONFIG_REV_A_UART_TX_GPIO < 0 || CONFIG_REV_A_UART_RX_GPIO < 0
#error "UART is enabled but TX/RX GPIOs are unset. Verify the actual ESP32-S3 board pinout first."
#endif
#endif
void app_main(void) {
#if CONFIG_REV_A_UART_ENABLE
    const rev_a_uart_bridge_config_t cfg = {
        .uart_port = (uart_port_t)CONFIG_REV_A_UART_PORT,
        .tx_gpio_num = CONFIG_REV_A_UART_TX_GPIO,
        .rx_gpio_num = CONFIG_REV_A_UART_RX_GPIO,
        .baud_rate = CONFIG_REV_A_UART_BAUD,
    };
    ESP_ERROR_CHECK(rev_a_uart_bridge_start(&cfg));
    ESP_LOGI(TAG, "UART protocol bridge active; waiting for DEVICE_INFO.");
#else
    ESP_LOGW(TAG, "UART bridge compiled but disabled. Verify board pinout and set TX/RX GPIOs before enabling.");
#endif
}
