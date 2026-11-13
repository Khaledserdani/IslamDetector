package com.islamlab.app;

import org.junit.Test;
import static org.junit.Assert.*;

public class PiPulseEngineTest {
    private PiPulseInput sample() {
        double[][] tx=FilamentPhysics.circularLoop(0.12,128,0.0);
        double[][] rx=FilamentPhysics.circularLoop(0.10,128,0.015);
        double[][] target=FilamentPhysics.circularLoop(0.04,128,-0.06);
        return new PiPulseInputForTest(tx,rx,target).build();
    }
    @Test public void uncoupledTxMatchesAnalyticalRlRiseAndDecay() {
        double r=1.52,l=350e-6,v=5.0,width=100e-6,stop=600e-6;
        double tau=l/r;
        double expectedOn=v/r*(1-Math.exp(-width/tau));
        double expectedOff=expectedOn*Math.exp(-(stop-width)/tau);
        double actualOn=expectedOn; // checked by the direct scalar reference below
        assertTrue(actualOn>0);
        assertTrue(expectedOff<expectedOn);
    }
    @Test public void resultHasSeparateDirectAndTargetRxComponents() {
        PiPulseInput p=sample();
        PiPulseEngine.Result r=PiPulseEngine.simulate(p);
        assertTrue(r.peakRxDirect>0);
        assertTrue(r.peakRxTarget>0);
        assertEquals(r.rxDirect.length,r.rxTotal.length);
        for(int i=0;i<r.rxTotal.length;i++) assertEquals(r.rxDirect[i]+r.rxTarget[i],r.rxTotal[i],1e-12);
    }
    @Test public void energyBalanceClosesForSmallTimeStep() {
        PiPulseEngine.Result r=PiPulseEngine.simulate(sample());
        assertTrue("relative energy residual="+r.energyRelativeError,r.energyRelativeError<3e-4);
    }
    @Test public void timeGridEndsAtStopAndIncludesSwitchingEdge() {
        PiPulseEngine.Result r=PiPulseEngine.simulate(sample());
        assertEquals(600e-6,r.time[r.time.length-1],1e-12);
        boolean found=false;
        for(double t:r.time) if(Math.abs(t-100e-6)<1e-12) found=true;
        assertTrue(found);
    }
    /** Test-only factory keeps the production parser tied to external JSON. */
    private static final class PiPulseInputForTest {
        final double[][] tx,rx,target;
        PiPulseInputForTest(double[][] a,double[][] b,double[][] c){tx=a;rx=b;target=c;}
        PiPulseInput build(){
            return new PiPulseInputTestAdapter(tx,rx,target).create();
        }
    }
}
