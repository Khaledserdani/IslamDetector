package com.islamlab.app;

/** Package-private constructor bridge used by deterministic numerical tests. */
final class PiPulseInputFactory {
    private PiPulseInputFactory(){}
    static PiPulseInput create(double[][] tx,double[][] rx,double[][] target,int ntx,int nrx,int nt,
        double rtx,double ltx,double lrx,double rt,double lt,double vb,double width,double clamp,double dt,double stop){
        return new PiPulseInput(tx,rx,target,ntx,nrx,nt,rtx,ltx,lrx,rt,lt,vb,width,clamp,dt,stop);
    }
}
