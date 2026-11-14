#ifndef ISLAM_REV_A_UART_BRIDGE_H
#define ISLAM_REV_A_UART_BRIDGE_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "driver/uart.h"
#include "esp_err.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "rev_a_session.h"
#ifdef __cplusplus
extern "C" {
#endif
typedef struct {
    uart_port_t uart_port;
    int tx_gpio_num; /* Must be taken from the exact ESP32-S3 board schematic. */
    int rx_gpio_num; /* Must be taken from the exact ESP32-S3 board schematic. */
    int baud_rate; /* 921600 when zero. */
    size_t rx_buffer_size; /* 4096 when zero. */
    size_t tx_buffer_size; /* 512 when zero. */
    size_t event_queue_length; /* 16 when zero. */
    size_t measurement_queue_length; /* 8 when zero. */
    uint32_t task_stack_size_bytes; /* 4096 when zero. */
    UBaseType_t task_priority; /* 10 when zero. */
    uint32_t device_info_retry_ms; /* 1000 when zero. */
} rev_a_uart_bridge_config_t;
typedef struct {
    bool running;
    bool device_info_valid;
    rev_a_device_info_t device_info;
    uint32_t rx_bytes;
    uint32_t parser_rejections;
    uint32_t parser_discarded_bytes;
    uint32_t accepted_device_info;
    uint32_t accepted_measurements;
    uint32_t rejected_measurements_without_info;
    uint32_t dropped_measurements;
    uint32_t uart_fifo_overflows;
    uint32_t uart_buffer_full_events;
    uint32_t uart_frame_errors;
    uint32_t uart_parity_errors;
    uint32_t uart_break_events;
    uint32_t info_requests;
    uint32_t tx_errors;
} rev_a_uart_bridge_status_t;
esp_err_t rev_a_uart_bridge_start(const rev_a_uart_bridge_config_t *config);
esp_err_t rev_a_uart_bridge_stop(void);
esp_err_t rev_a_uart_bridge_send_command(
    uint8_t command_type, const uint8_t *payload, uint8_t payload_length);
QueueHandle_t rev_a_uart_bridge_measurement_queue(void);
void rev_a_uart_bridge_get_status(rev_a_uart_bridge_status_t *status_out);
#ifdef __cplusplus
}
#endif
#endif
