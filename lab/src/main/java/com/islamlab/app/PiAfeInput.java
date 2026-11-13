package com.islamlab.app;

import org.json.JSONException;
import org.json.JSONObject;

/** Lumped RX and AFE protection network parameters. */
public final class PiAfeInput {
    public final double rxResistance,rxInductance,dampingResistance,seriesResistance;
    public final double inputCapacitance,biasResistance,coilTvsThreshold,coilTvsDynamicResistance;
    public final double inputClampThreshold,inputClampDynamicResistance,maxStep;

    PiAfeInput(double rr,double ll,double rd,double rs,double c,double rb,
            double tv,double rtv,double iv,double riv,double step){
        rxResistance=rr;rxInductance=ll;dampingResistance=rd;seriesResistance=rs;
        inputCapacitance=c;biasResistance=rb;coilTvsThreshold=tv;coilTvsDynamicResistance=rtv;
        inputClampThreshold=iv;inputClampDynamicResistance=riv;maxStep=step;
    }
    private static double positive(JSONObject o,String k)throws JSONException{
        double v=o.getDouble(k);
        if((Double.isNaN(v)||Double.isInfinite(v))||v<=0)throw new IllegalArgumentException(k+" يجب أن يكون موجباً");
        return v;
    }
    private static double nonnegative(JSONObject o,String k)throws JSONException{
        double v=o.optDouble(k,0.0);
        if(!Double.isFinite(v)||v<0)throw new IllegalArgumentException(k+" يجب ألا يكون سالباً");
        return v;
    }
    public static PiAfeInput defaults(){
        return new PiAfeInput(4.802,750e-6,390.0,1000.0,2e-9,1e6,
                6.0,2.0,0.35,50.0,10e-9);
    }
    public static PiAfeInput parse(String json)throws JSONException{
        JSONObject root=new JSONObject(json);
        JSONObject rx=root.getJSONObject("rx_coil"),afe=root.getJSONObject("afe");
        JSONObject integration=root.optJSONObject("integration");
        double tv=nonnegative(afe,"coil_tvs_threshold_v");
        double iv=nonnegative(afe,"clamp_threshold_v");
        double step=integration==null?10e-9:positive(integration,"max_step_s");
        return new PiAfeInput(positive(rx,"resistance_ohm"),positive(rx,"inductance_h"),
                positive(afe,"parallel_damping_ohm"),positive(afe,"series_protection_ohm"),
                positive(afe,"input_capacitance_f"),positive(afe,"input_bias_ohm"),
                tv,positive(afe,"coil_tvs_dynamic_resistance_ohm"),iv,
                positive(afe,"clamp_dynamic_resistance_ohm"),step);
    }
}
