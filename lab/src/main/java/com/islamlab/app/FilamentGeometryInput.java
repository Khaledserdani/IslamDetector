package com.islamlab.app;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

/** Strict JSON input model for measured/CAD-exported 3D coil centerlines. */
public final class FilamentGeometryInput {
    private static boolean finite(double value) { return !Double.isNaN(value) && !Double.isInfinite(value); }
    public final double[][] txPath;
    public final double[][] rxPath;
    public final double[][] observationPoints;
    public final int txTurns;
    public final int rxTurns;
    public final double txCurrentAmps;
    public final Double txWireLengthMetres;
    public final Double rxWireLengthMetres;

    private FilamentGeometryInput(double[][] tx, double[][] rx, double[][] points,
                                  int ntx, int nrx, double current, Double txLength, Double rxLength) {
        txPath=tx; rxPath=rx; observationPoints=points;
        txTurns=ntx; rxTurns=nrx; txCurrentAmps=current;
        txWireLengthMetres=txLength; rxWireLengthMetres=rxLength;
    }

    public static FilamentGeometryInput parse(String json) throws JSONException {
        if (json == null || json.trim().isEmpty()) throw new IllegalArgumentException("ملف الهندسة فارغ");
        JSONObject root=new JSONObject(json);
        JSONObject paths=root.getJSONObject("paths_m");
        JSONObject turns=root.getJSONObject("turns");
        double[][] tx=coordinates(paths.getJSONArray("TX"),"TX");
        double[][] rx=coordinates(paths.getJSONArray("RX"),"RX");
        double[][] points=coordinates(root.getJSONArray("observation_points_m"),"observation_points_m");
        int ntx=turns.getInt("TX"), nrx=turns.getInt("RX");
        if(ntx<1 || nrx<1) throw new IllegalArgumentException("عدد اللفات يجب أن يكون موجباً");
        double current=root.optDouble("tx_current_a",1.0);
        if(!finite(current)) throw new IllegalArgumentException("تيار TX غير صالح");
        Double txLength=null, rxLength=null;
        JSONObject wire=root.optJSONObject("wire_lengths_m");
        if(wire!=null){
            if(wire.has("TX")) txLength=positiveLength(wire.getDouble("TX"),"TX");
            if(wire.has("RX")) rxLength=positiveLength(wire.getDouble("RX"),"RX");
        }
        return new FilamentGeometryInput(tx,rx,points,ntx,nrx,current,txLength,rxLength);
    }

    private static Double positiveLength(double value,String name){
        if(!finite(value) || value<=0) throw new IllegalArgumentException(name+": طول السلك يجب أن يكون موجباً");
        return value;
    }

    private static double[][] coordinates(JSONArray array,String name) throws JSONException {
        if(array.length()<1) throw new IllegalArgumentException(name+": لا توجد إحداثيات");
        double[][] result=new double[array.length()][3];
        for(int i=0;i<array.length();i++){
            JSONArray point=array.getJSONArray(i);
            if(point.length()!=3) throw new IllegalArgumentException(name+": كل نقطة يجب أن تحتوي X وY وZ");
            for(int j=0;j<3;j++){
                double value=point.getDouble(j);
                if(!finite(value)) throw new IllegalArgumentException(name+": إحداثيات غير محدودة");
                result[i][j]=value;
            }
        }
        return result;
    }
}
