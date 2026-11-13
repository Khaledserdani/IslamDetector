package com.islamlab.app;

import org.junit.Test;
import static org.junit.Assert.*;

public class PiAfeEngineTest {
    private PiAfeInput p(){return PiAfeInput.defaults();}
    private double[][] wave(double amplitude){
        int n=1001;double[][] a=new double[2][n];
        for(int i=0;i<n;i++){
            double t=i*0.1e-6;a[0][i]=t;
            a[1][i]=amplitude*Math.exp(-Math.pow((t-20e-6)/3e-6,2))
                    -0.4*amplitude*Math.exp(-Math.pow((t-35e-6)/5e-6,2));
        }
        return a;
    }
    @Test public void zeroSourceRemainsZero(){
        double[][] w=wave(0);PiAfeEngine.Result r=PiAfeEngine.simulate(w[0],w[1],p());
        assertEquals(0,r.peakInputVoltage,1e-15);assertTrue(r.energyRelativeError<1e-8);
    }
    @Test public void inputClampConductsAndEnergyCloses(){
        double[][] w=wave(30);PiAfeEngine.Result r=PiAfeEngine.simulate(w[0],w[1],p());
        assertTrue(r.peakClampCurrent>0);assertTrue(r.peakInputVoltage<2.5);
        assertTrue(r.energyRelativeError<3e-4);
    }
    @Test public void strongerDampingReducesTerminalVoltage(){
        double[][] w=wave(0.1);PiAfeInput a=p();
        PiAfeInput b=new PiAfeInput(4.802,750e-6,100,1000,2e-9,1e6,6,2,.35,50,10e-9);
        PiAfeEngine.Result x=PiAfeEngine.simulate(w[0],w[1],a),y=PiAfeEngine.simulate(w[0],w[1],b);
        assertTrue(y.peakCoilTerminal<x.peakCoilTerminal);
    }
    @Test public void energyBalanceIncludesBothProtectionStages(){
        double[][] w=wave(30);PiAfeEngine.Result r=PiAfeEngine.simulate(w[0],w[1],p());
        assertTrue(r.coilTvsEnergy>0);assertTrue(r.inputClampEnergy>0);
        assertTrue(r.energyRelativeError<3e-4);
    }
}
