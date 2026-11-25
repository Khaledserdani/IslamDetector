#include "rev_a_http_api_policy.h"

#include <assert.h>
#include <string.h>

int main(void) {
    rev_a_http_command_result_t result;

    rev_a_http_command_decide("stop", &result);
    assert(result.http_status == 200);
    assert(result.accepted);
    assert(strcmp(result.state, "idle") == 0);
    assert(strcmp(result.reason, "SAFE_IDLE_NO_TX_PATH") == 0);

    rev_a_http_command_decide("start", &result);
    assert(result.http_status == 409);
    assert(!result.accepted);
    assert(strcmp(result.reason, "TX_INTERLOCK_NOT_IMPLEMENTED") == 0);

    rev_a_http_command_decide("calibrate", &result);
    assert(result.http_status == 409);
    assert(!result.accepted);
    assert(strcmp(result.reason, "ADC_NOT_INSTALLED") == 0);

    rev_a_http_command_decide("unknown", &result);
    assert(result.http_status == 400);
    assert(!result.accepted);

    rev_a_http_command_decide(NULL, &result);
    assert(result.http_status == 400);
    assert(!result.accepted);

    return 0;
}
