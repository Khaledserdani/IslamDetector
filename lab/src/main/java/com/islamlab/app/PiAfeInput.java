package com.islamlab.app;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

/** Lumped RX, protection and OPA365 behavioral parameters. */
public final class PiAfeInput {
    public final double rxResistance,rxInductance,dampingResistance,seriesResistance;
    public final double inputCapacitance,biasResistance,coilTvsThreshold,coilTvsDynamicResistance;
    public final double inputClampThreshold,inputClampDynamicResistance,maxStep;
    public final double opampGain,supplyLow,supplyHigh,referenceVoltage,gainBandwidth,slewRate,outputHeadroom;
    public final double[] inputClampCurveVoltage,inputClampCurveCurrent;

    PiAfeInput(double rr,double ll,double rd,double rs,double c,double rb,
            double tv,double rtv,double iv,double riv,double step,
            double gain,double low,double high,double reference,double gbw,double slew,double headroom,
            double[] curveV,double[] curveI){
        rxResistance=rr;rxInductance=ll;dampingResistance=rd;seriesResistance=rs;
        inputCapacitance=c;biasResistance=rb;coilTvsThreshold=tv;coilTvsDynamicResistance=rtv;
        inputClampThreshold=iv;inputClampDynamicResistance=riv;maxStep=step;
        opampGain=gain;supplyLow=low;supplyHigh=high;referenceVoltage=reference;
        gainBandwidth=gbw;slewRate=slew;outputHeadroom=headroom;
        inputClampCurveVoltage=curveV.clone();inputClampCurveCurrent=curveI.clone();
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
    private static double[][] parseCurve(JSONObject afe)throws JSONException{
        JSONArray curve=afe.optJSONArray("input_clamp_iv_curve_v_a");
        if(curve==null)return new double[][]{new double[0],new double[0]};
        if(curve.length()<2)throw new IllegalArgumentException("منحنى BAT54S يحتاج نقطتين على الأقل");
        double[] v=new double[curve.length()],i=new double[curve.length()];
        for(int n=0;n<curve.length();n++){
            JSONArray point=curve.getJSONArray(n);
            if(point.length()!=2)throw new IllegalArgumentException("كل نقطة I-V يجب أن تحتوي جهداً وتياراً");
            v[n]=point.getDouble(0);i[n]=point.getDouble(1);
            if(Double.isNaN(v[n])||Double.isInfinite(v[n])||Double.isNaN(i[n])||Double.isInfinite(i[n])
                    ||v[n]<0||i[n]<0||(n>0&&(v[n]<=v[n-1]||i[n]<=i[n-1])))
                throw new IllegalArgumentException("منحنى I-V يجب أن يكون موجباً ومتزايداً");
        }
        return new double[][]{v,i};
    }
    public static PiAfeInput defaults(){
        return new PiAfeInput(4.802,750e-6,390.0,1000.0,2e-9,1e6,
                6.4,0.049,0.24,88.9,10e-9,2.0,0.0,3.3,1.65,50e6,25e6,0.01,
                new double[]{0.24,0.32,0.40,0.50,0.80},
                new double[]{0.0001,0.001,0.010,0.030,0.100});
    }
    PiAfeInput withDamping(double value){
        return copy(value,opampGain,slewRate);
    }
    PiAfeInput withSlewRate(double value){
        return copy(dampingResistance,opampGain,value);
    }
    private PiAfeInput copy(double damping,double gain,double slew){
        return new PiAfeInput(rxResistance,rxInductance,damping,seriesResistance,inputCapacitance,biasResistance,
                coilTvsThreshold,coilTvsDynamicResistance,inputClampThreshold,inputClampDynamicResistance,maxStep,
                gain,supplyLow,supplyHigh,referenceVoltage,gainBandwidth,slew,outputHeadroom,
                inputClampCurveVoltage,inputClampCurveCurrent);
    }
    public static PiAfeInput parse(String json)throws JSONException{
        JSONObject root=new JSONObject(json);
        JSONObject rx=root.getJSONObject("rx_coil"),afe=root.getJSONObject("afe");
        JSONObject integration=root.optJSONObject("integration"),op=root.optJSONObject("opamp");
        double[][] curve=parseCurve(afe);
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
                ||high-low<2.2||high-low>5.5||2*headroom>=high-low)throw new IllegalArgumentException("قضبان أو مرجع المضخم غير صالح");
        return new PiAfeInput(positive(rx,"resistance_ohm"),positive(rx,"inductance_h"),
                positive(afe,"parallel_damping_ohm"),positive(afe,"series_protection_ohm"),
                positive(afe,"input_capacitance_f"),positive(afe,"input_bias_ohm"),
                tv,positive(afe,"coil_tvs_dynamic_resistance_ohm"),iv,
                positive(afe,"clamp_dynamic_resistance_ohm"),step,gain,low,high,reference,gbw,slew,headroom,
                curve[0],curve[1]);
    }
}
