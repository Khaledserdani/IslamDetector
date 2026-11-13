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
        PiAfeInput b=a.withDamping(100.0);
        PiAfeEngine.Result x=PiAfeEngine.simulate(w[0],w[1],a),y=PiAfeEngine.simulate(w[0],w[1],b);
        assertTrue(y.peakCoilTerminal<x.peakCoilTerminal);
    }
    @Test public void opampOutputRespectsRailsAndSlewRate(){
        double[][] w=wave(30);PiAfeInput base=p();
        PiAfeInput highGain=new PiAfeInput(base.rxResistance,base.rxInductance,base.dampingResistance,base.seriesResistance,
                base.inputCapacitance,base.biasResistance,base.coilTvsThreshold,base.coilTvsDynamicResistance,
                base.inputClampThreshold,base.inputClampDynamicResistance,base.inputClampLowRail,base.inputClampHighRail,base.maxStep,100.0,
                base.supplyLow,base.supplyHigh,base.referenceVoltage,base.gainBandwidth,base.slewRate,base.outputHeadroom,
                base.inputClampCurveVoltage,base.inputClampCurveCurrent);
        PiAfeEngine.Result r=PiAfeEngine.simulate(w[0],w[1],highGain);
        assertTrue(r.outputSaturationSamples>0);
        assertTrue(r.minOpampOutput>=0.01-1e-12);
        assertTrue(r.peakOpampOutput<=3.29+1e-12);
        PiAfeInput lowGain=base.withSlewRate(1e6);
        PiAfeEngine.Result slew=PiAfeEngine.simulate(w[0],w[1],lowGain);
        assertTrue(slew.slewLimitedSamples>0);
    }
    @Test public void energyBalanceIncludesBothProtectionStages(){
        double[][] w=wave(30);PiAfeEngine.Result r=PiAfeEngine.simulate(w[0],w[1],p());
        assertTrue(r.coilTvsEnergy>0);assertTrue(r.inputClampEnergy>0);
        assertTrue(r.energyRelativeError<3e-4);
    }
}
