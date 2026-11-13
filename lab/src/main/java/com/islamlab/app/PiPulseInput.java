package com.islamlab.app;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

/** Validated JSON configuration for the coupled PI pulse simulation. */
public final class PiPulseInput {
    public final double[][] txPath, rxPath, targetPath;
    public final int txTurns, rxTurns, targetTurns;
    public final double txResistance, txInductance, rxInductance;
    public final double targetResistance, targetInductance;
    public final double busVoltage, pulseWidth, clampVoltage, timeStep, stopTime;

    private PiPulseInput(double[][] tx, double[][] rx, double[][] target,
            int ntx, int nrx, int ntarget, double rtx, double ltx, double lrx,
            double rt, double lt, double vb, double width, double clamp,
            double dt, double stop) {
        txPath=tx; rxPath=rx; targetPath=target;
        txTurns=ntx; rxTurns=nrx; targetTurns=ntarget;
        txResistance=rtx; txInductance=ltx; rxInductance=lrx;
        targetResistance=rt; targetInductance=lt;
        busVoltage=vb; pulseWidth=width; clampVoltage=clamp; timeStep=dt; stopTime=stop;
    }

    private static boolean finite(double v){return !Double.isNaN(v)&&!Double.isInfinite(v);}
    private static double positive(JSONObject o,String key) throws JSONException {
        double v=o.getDouble(key);
        if(!finite(v)||v<=0) throw new IllegalArgumentException(key+" يجب أن يكون موجباً");
        return v;
    }
    private static double[][] path(JSONObject paths,String key) throws JSONException {
        JSONArray a=paths.getJSONArray(key);
        if(a.length()<4) throw new IllegalArgumentException(key+": يلزم أربع نقاط على الأقل");
        double[][] out=new double[a.length()][3];
        for(int i=0;i<a.length();i++){
            JSONArray p=a.getJSONArray(i);
            if(p.length()!=3) throw new IllegalArgumentException(key+": كل نقطة يجب أن تكون X/Y/Z");
            for(int j=0;j<3;j++){
                double v=p.getDouble(j);
                if(!finite(v)) throw new IllegalArgumentException(key+": إحداثيات غير صالحة");
                out[i][j]=v;
            }
        }
        return out;
    }

    public static PiPulseInput parse(String json) throws JSONException {
        if(json==null||json.trim().isEmpty()) throw new IllegalArgumentException("ملف النبضة فارغ");
        JSONObject root=new JSONObject(json);
        JSONObject paths=root.getJSONObject("paths_m");
        JSONObject turns=root.getJSONObject("turns");
        JSONObject e=root.getJSONObject("electrical");
        JSONObject target=root.getJSONObject("target");
        JSONObject pulse=root.getJSONObject("pulse");
        int ntx=turns.getInt("TX"), nrx=turns.getInt("RX");
        int nt=turns.optInt("target_loop",1);
        if(ntx<1||nrx<1||nt<1) throw new IllegalArgumentException("أعداد اللفات يجب أن تكون موجبة");
        double vb=positive(pulse,"bus_voltage_v");
        double width=positive(pulse,"pulse_width_s");
        double clamp=pulse.optDouble("clamp_voltage_v",0.0);
        if(!finite(clamp)||clamp<0) throw new IllegalArgumentException("جهد التثبيت غير صالح");
        double dt=positive(pulse,"time_step_s");
        double stop=positive(pulse,"stop_time_s");
        if(stop<=width) throw new IllegalArgumentException("زمن المحاكاة يجب أن يتجاوز عرض النبضة");
        return new PiPulseInput(path(paths,"TX"),path(paths,"RX"),path(paths,"target_loop"),
                ntx,nrx,nt,positive(e,"tx_resistance_ohm"),positive(e,"tx_inductance_h"),
                positive(e,"rx_inductance_h"),positive(target,"resistance_ohm"),
                positive(target,"inductance_h"),vb,width,clamp,dt,stop);
    }
}
