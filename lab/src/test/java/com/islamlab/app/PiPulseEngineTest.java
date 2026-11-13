package com.islamlab.app;

import org.junit.Test;
import static org.junit.Assert.*;

public class PiPulseEngineTest {
    private PiPulseInput sample(boolean decoupledTarget) {
        double[][] tx=FilamentPhysics.circularLoop(0.12,128,0.0);
        double[][] rx=FilamentPhysics.circularLoop(0.10,128,0.015);
        double[][] target;
        if(decoupledTarget){
            target=new double[129][3];
            for(int i=0;i<=128;i++){
                double a=2.0*Math.PI*i/128;
                target[i][0]=0.04*Math.cos(a);
                target[i][1]=0.0;
                target[i][2]=-0.06+0.04*Math.sin(a);
            }
        }else{
            target=FilamentPhysics.circularLoop(0.04,128,-0.06);
        }
        return PiPulseInputFactory.create(tx,rx,target,20,30,1,
                1.52,350e-6,750e-6,0.08,20e-6,
                5.0,100e-6,0.0,0.25e-6,600e-6);
    }

    @Test public void uncoupledTxMatchesAnalyticalRlRiseAndDecay() {
        PiPulseInput p=sample(true);
        PiPulseEngine.Result result=PiPulseEngine.simulate(p);
        double r=1.52,l=350e-6,v=5.0,width=100e-6,stop=600e-6;
        double expectedOn=v/r*(1-Math.exp(-r*width/l));
        double expectedOff=expectedOn*Math.exp(-r*(stop-width)/l);
        assertEquals(expectedOn,result.txCurrentAtTurnoff,2e-4);
        assertEquals(expectedOff,result.txCurrent[result.txCurrent.length-1],2e-4);
    }

    @Test public void resultHasSeparateDirectAndTargetRxComponents() {
        PiPulseEngine.Result r=PiPulseEngine.simulate(sample(false));
        assertTrue(r.peakRxDirect>0);
        assertTrue(r.peakRxTarget>0);
        assertEquals(r.rxDirect.length,r.rxTotal.length);
        for(int i=0;i<r.rxTotal.length;i++)
            assertEquals(r.rxDirect[i]+r.rxTarget[i],r.rxTotal[i],1e-12);
    }

    @Test public void energyBalanceClosesForSmallTimeStep() {
        PiPulseEngine.Result r=PiPulseEngine.simulate(sample(false));
        assertTrue("relative energy residual="+r.energyRelativeError,r.energyRelativeError<3e-4);
    }

    @Test public void timeGridEndsAtStopAndIncludesSwitchingEdge() {
        PiPulseEngine.Result r=PiPulseEngine.simulate(sample(false));
        assertEquals(600e-6,r.time[r.time.length-1],1e-12);
        boolean found=false;
        for(double time:r.time) if(Math.abs(time-100e-6)<1e-12) found=true;
        assertTrue(found);
    }
}
