package com.islamlab.app;

/** Package-private test factory for immutable pulse input values. */
final class PiPulseInputTestAdapter {
    private final double[][] tx,rx,target;
    PiPulseInputTestAdapter(double[][] a,double[][] b,double[][] c){tx=a;rx=b;target=c;}
    PiPulseInput create(){
        return PiPulseInputFactory.create(tx,rx,target,20,30,1,1.52,350e-6,750e-6,0.08,20e-6,5.0,100e-6,0.0,0.25e-6,600e-6);
    }
}
