package com.islamlab.app;

import org.json.JSONException;
import org.json.JSONObject;

/** Lumped RX, protection and OPA365 behavioral parameters. */
public final class PiAfeInput {
    public final double rxResistance,rxInductance,dampingResistance,seriesResistance;
    public final double inputCapacitance,biasResistance,coilTvsThreshold,coilTvsDynamicResistance;
    public final double inputClampThreshold,inputClampDynamicResistance,maxStep;
    public final double opampGain,supplyLow,supplyHigh,referenceVoltage,gainBandwidth,slewRate,outputHeadroom;

    PiAfeInput(double rr,double ll,double rd,double rs,double c,double rb,
            double tv,double rtv,double iv,double riv,double step,
            double gain,double low,double high,double reference,double gbw,double slew,double headroom){
        rxResistance=rr;rxInductance=ll;dampingResistance=rd;seriesResistance=rs;
        inputCapacitance=c;biasResistance=rb;coilTvsThreshold=tv;coilTvsDynamicResistance=rtv;
        inputClampThreshold=iv;inputClampDynamicResistance=riv;maxStep=step;
        opampGain=gain;supplyLow=low;supplyHigh=high;referenceVoltage=reference;
        gainBandwidth=gbw;slewRate=slew;outputHeadroom=headroom;
    }
    private static double positive(JSONObject o,String k)throws JSONException{
        double v=o.getDouble(k);
        if(Double.isNaN(v)||Double.isInfinite(v)||v<=0)throw new IllegalArgumentException(k+" يجب أن يكون موجباً");
        return v;
    }
    private static double nonnegative(JSONObject o,String k)throws JSONException{
        double v=o.optDouble(k,0.0);
        if(Double.isNaN(v)||Double.isInfinite(v)||v<0)throw new IllegalArgumentException(k+" يجب ألا يكون سالباً");
        return v;
    }
    public static PiAfeInput defaults(){
        return new PiAfeInput(4.802,750e-6,390.0,1000.0,2e-9,1e6,
                6.0,2.0,0.35,50.0,10e-9,2.0,0.0,3.3,1.65,50e6,25e6,0.01);
    }
    PiAfeInput withDamping(double value){
        return new PiAfeInput(rxResistance,rxInductance,value,seriesResistance,inputCapacitance,biasResistance,
                coilTvsThreshold,coilTvsDynamicResistance,inputClampThreshold,inputClampDynamicResistance,maxStep,
                opampGain,supplyLow,supplyHigh,referenceVoltage,gainBandwidth,slewRate,outputHeadroom);
    }
    public static PiAfeInput parse(String json)throws JSONException{
        JSONObject root=new JSONObject(json);
        JSONObject rx=root.getJSONObject("rx_coil"),afe=root.getJSONObject("afe");
        JSONObject integration=root.optJSONObject("integration"),op=root.optJSONObject("opamp");
        double tv=nonnegative(afe,"coil_tvs_threshold_v");
        double iv=nonnegative(afe,"clamp_threshold_v");
        double step=integration==null?10e-9:positive(integration,"max_step_s");
        double gain=op==null?2.0:positive(op,"closed_loop_gain");
        double low=op==null?0.0:op.optDouble("supply_low_v",0.0);
        double high=op==null?3.3:op.optDouble("supply_high_v",3.3);
        double reference=op==null?0.5*(low+high):op.optDouble("reference_v",0.5*(low+high));
        double gbw=op==null?50e6:positive(op,"gain_bandwidth_hz");
        double slew=op==null?25e6:positive(op,"slew_rate_v_per_s");
        double headroom=op==null?0.01:nonnegative(op,"output_headroom_v");
        if(Double.isNaN(low)||Double.isInfinite(low)||Double.isNaN(high)||Double.isInfinite(high)
                ||Double.isNaN(reference)||Double.isInfinite(reference)||high<=low||reference<low||reference>high
                ||2*headroom>=high-low)throw new IllegalArgumentException("قضبان أو مرجع المضخم غير صالح");
        return new PiAfeInput(positive(rx,"resistance_ohm"),positive(rx,"inductance_h"),
                positive(afe,"parallel_damping_ohm"),positive(afe,"series_protection_ohm"),
                positive(afe,"input_capacitance_f"),positive(afe,"input_bias_ohm"),
                tv,positive(afe,"coil_tvs_dynamic_resistance_ohm"),iv,
                positive(afe,"clamp_dynamic_resistance_ohm"),step,gain,low,high,reference,gbw,slew,headroom);
    }
}
