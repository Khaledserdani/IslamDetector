#ifndef ISLAM_REV_A_HTTP_API_POLICY_H
#define ISLAM_REV_A_HTTP_API_POLICY_H

#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    int http_status;
    bool accepted;
    const char *state;
    const char *reason;
} rev_a_http_command_result_t;

/*
 * Conservative Rev A policy:
 * - STOP is idempotently accepted while the TX path is not implemented.
 * - START remains blocked until an independently verified hardware interlock exists.
 * - CALIBRATE remains blocked until a real ADC measurement path is installed.
 */
void rev_a_http_command_decide(
    const char *command,
    rev_a_http_command_result_t *result_out);

#ifdef __cplusplus
}
#endif

#endif
