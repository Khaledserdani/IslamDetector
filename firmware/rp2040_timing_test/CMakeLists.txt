cmake_minimum_required(VERSION 3.13)

if(NOT DEFINED PICO_SDK_PATH)
    if(DEFINED ENV{PICO_SDK_PATH})
        set(PICO_SDK_PATH $ENV{PICO_SDK_PATH})
    else()
        message(FATAL_ERROR "PICO_SDK_PATH must point to the Raspberry Pi pico-sdk")
    endif()
endif()

include(${PICO_SDK_PATH}/external/pico_sdk_import.cmake)

project(islam_detector_rev_a_timing_test C CXX ASM)
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

pico_sdk_init()

add_executable(islam_rev_a_timing_test
    src/main.c
    src/ads8861_capture.c
    ../esp32_s3_bridge/components/rev_a_protocol/rev_a_protocol.c
)

target_include_directories(islam_rev_a_timing_test PRIVATE
    ../esp32_s3_bridge/components/rev_a_protocol/include
)

pico_generate_pio_header(islam_rev_a_timing_test
    ${CMAKE_CURRENT_LIST_DIR}/pio/sample_marker_echo.pio
)

pico_generate_pio_header(islam_rev_a_timing_test
    ${CMAKE_CURRENT_LIST_DIR}/pio/ads8861_capture.pio
)

target_link_libraries(islam_rev_a_timing_test
    pico_stdlib
    hardware_pwm
    hardware_irq
    hardware_pio
    hardware_clocks
    hardware_dma
)

pico_enable_stdio_usb(islam_rev_a_timing_test 1)
pico_enable_stdio_uart(islam_rev_a_timing_test 0)

pico_add_extra_outputs(islam_rev_a_timing_test)
