idf_component_register(
    SRCS "app_main.c" "rev_a_http_api.c" "rev_a_http_api_policy.c"
    INCLUDE_DIRS "."
    REQUIRES rev_a_uart_bridge esp_wifi esp_netif esp_event nvs_flash esp_http_server json
)
