#include "rev_a_http_api_policy.h"

#include <string.h>

void rev_a_http_command_decide(
    const char *command,
    rev_a_http_command_result_t *result_out) {
    if (result_out == NULL) {
        return;
    }

    result_out->http_status = 400;
    result_out->accepted = false;
    result_out->state = "idle";
    result_out->reason = "UNKNOWN_COMMAND";

    if (command == NULL) {
        return;
    }

    if (strcmp(command, "stop") == 0) {
        result_out->http_status = 200;
        result_out->accepted = true;
        result_out->reason = "SAFE_IDLE_NO_TX_PATH";
    } else if (strcmp(command, "start") == 0) {
        result_out->http_status = 409;
        result_out->reason = "TX_INTERLOCK_NOT_IMPLEMENTED";
    } else if (strcmp(command, "calibrate") == 0) {
        result_out->http_status = 409;
        result_out->reason = "ADC_NOT_INSTALLED";
    }
}
