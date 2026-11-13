package com.islamlab.app;

import org.junit.Test;
import static org.junit.Assert.*;

public class PiAfeInputTest {
    private String json(double high){
        return "{\"rx_coil\":{\"resistance_ohm\":4.802,\"inductance_h\":0.00075},"+
          "\"afe\":{\"parallel_damping_ohm\":390,\"series_protection_ohm\":1000,\"input_capacitance_f\":2e-9,\"input_bias_ohm\":1e6,\"coil_tvs_threshold_v\":6,\"coil_tvs_dynamic_resistance_ohm\":2,\"clamp_threshold_v\":0.35,\"clamp_dynamic_resistance_ohm\":50},"+
          "\"integration\":{\"max_step_s\":1e-8},"+
          "\"opamp\":{\"closed_loop_gain\":2,\"supply_low_v\":0,\"supply_high_v\":"+high+",\"reference_v\":1.65,\"gain_bandwidth_hz\":50000000,\"slew_rate_v_per_s\":25000000,\"output_headroom_v\":0.01}}";
    }
    @Test public void parsesRxProtectionAndOpampParameters() throws Exception {
        PiAfeInput p=PiAfeInput.parse(json(3.3));
        assertEquals(4.802,p.rxResistance,0.0);
        assertEquals(390,p.dampingResistance,0.0);
        assertEquals(2.0,p.opampGain,0.0);
        assertEquals(50e6,p.gainBandwidth,0.0);
    }
    @Test(expected=IllegalArgumentException.class)
    public void rejectsSupplyOutsideOpa365OperatingRange() throws Exception {
        PiAfeInput.parse(json(6.0));
    }
    @Test public void defaultsUseOfficialRxResistanceAndNominalOpaLimits(){
        PiAfeInput p=PiAfeInput.defaults();
        assertEquals(4.802,p.rxResistance,0.0);
        assertEquals(50e6,p.gainBandwidth,0.0);
        assertEquals(25e6,p.slewRate,0.0);
    }
}
