package com.islamlab.app;

/** Transient lumped RX loading, coil TVS, series protection and AFE-input clamp model. */
public final class PiAfeEngine {
    private PiAfeEngine(){}
    public static final class Result{
        public final double[] time,inducedEmf,coilCurrent,coilTerminalVoltage,inputVoltage,seriesCurrent,coilTvsCurrent,inputClampCurrent,storedEnergy,opampOutput;
        public final double peakInducedEmf,peakCoilCurrent,peakCoilTerminal,peakInputVoltage,peakSeriesCurrent,peakClampCurrent;
        public final double sourceEnergy,coilLoss,dampingLoss,coilTvsEnergy,seriesLoss,biasLoss,inputClampEnergy,storedEnergyChange,energyResidual,energyRelativeError;
        public final int clampSamples,slewLimitedSamples,outputSaturationSamples;
        public final double peakOpampOutput,minOpampOutput;
        Result(double[] t,double[] emf,double[] ic,double[] va,double[] vin,double[] is,double[] itvs,double[] iclamp,double[] stored,double[] opout,
                double pe,double pc,double pv,double pi,double ps,double pk,double se,double cl,double dl,double te,double sl,double bl,double ie,double de,double er,double rel,int samples,int slewCount,int satCount,double opPeak,double opMin){
            time=t;inducedEmf=emf;coilCurrent=ic;coilTerminalVoltage=va;inputVoltage=vin;seriesCurrent=is;coilTvsCurrent=itvs;inputClampCurrent=iclamp;storedEnergy=stored;opampOutput=opout;
            peakInducedEmf=pe;peakCoilCurrent=pc;peakCoilTerminal=pv;peakInputVoltage=pi;peakSeriesCurrent=ps;peakClampCurrent=pk;
            sourceEnergy=se;coilLoss=cl;dampingLoss=dl;coilTvsEnergy=te;seriesLoss=sl;biasLoss=bl;inputClampEnergy=ie;storedEnergyChange=de;energyResidual=er;energyRelativeError=rel;clampSamples=samples;slewLimitedSamples=slewCount;outputSaturationSamples=satCount;peakOpampOutput=opPeak;minOpampOutput=opMin;
        }
    }
    private static final class D{
        final double di,dv,va,is,itvs,iclamp;
        D(double a,double b,double c,double d,double e,double f){di=a;dv=b;va=c;is=d;itvs=e;iclamp=f;}
    }
    private static final class S{
        final double i,v;final double[] energy;
        S(double a,double b,double[] e){i=a;v=b;energy=e;}
    }
    private static double clamp(double v,double threshold,double resistance){
        if(threshold<=0)return 0;
        if(v>threshold)return (v-threshold)/resistance;
        if(v< -threshold)return (v+threshold)/resistance;
        return 0;
    }
    private static double terminal(double i,double v,PiAfeInput p){
        double extent=Math.abs(v)+Math.abs(i)*(p.dampingResistance+p.seriesResistance)+p.coilTvsThreshold+20;
        double lo=-extent,hi=extent;
        for(int n=0;n<64;n++){
            double mid=0.5*(lo+hi);
            double tv=p.coilTvsThreshold>0?clamp(mid,p.coilTvsThreshold,p.coilTvsDynamicResistance):0;
            double f=mid/p.dampingResistance+tv+(mid-v)/p.seriesResistance-i;
            if(f>0)hi=mid;else lo=mid;
        }
        return 0.5*(lo+hi);
    }
    private static D derivative(double i,double v,double source,PiAfeInput p){
        double va=terminal(i,v,p);
        double is=(va-v)/p.seriesResistance;
        double tv=p.coilTvsThreshold>0?clamp(va,p.coilTvsThreshold,p.coilTvsDynamicResistance):0;
        double ci=clamp(v,p.inputClampThreshold,p.inputClampDynamicResistance);
        return new D((source-p.rxResistance*i-va)/p.rxInductance,
                (is-v/p.biasResistance-ci)/p.inputCapacitance,va,is,tv,ci);
    }
    private static double source(double[] t,double[] e,double x){
        int lo=0,hi=t.length-1;
        if(x<=t[0])return e[0];if(x>=t[hi])return e[hi];
        while(hi-lo>1){int m=(lo+hi)>>>1;if(t[m]<=x)lo=m;else hi=m;}
        double f=(x-t[lo])/(t[hi]-t[lo]);return e[lo]+f*(e[hi]-e[lo]);
    }
    private static double[] powers(double i,double v,double src,PiAfeInput p){
        D d=derivative(i,v,src,p);
        return new double[]{src*i,p.rxResistance*i*i,d.va*d.va/p.dampingResistance,
                d.va*d.itvs,p.seriesResistance*d.is*d.is,v*v/p.biasResistance,v*d.iclamp};
    }
    private static S advance(double i,double v,double t,double h,double[] times,double[] emf,PiAfeInput p){
        double s1=source(times,emf,t),s2=source(times,emf,t+h/2),s4=source(times,emf,t+h);
        D k1=derivative(i,v,s1,p);
        D k2=derivative(i+0.5*h*k1.di,v+0.5*h*k1.dv,s2,p);
        D k3=derivative(i+0.5*h*k2.di,v+0.5*h*k2.dv,s2,p);
        D k4=derivative(i+h*k3.di,v+h*k3.dv,s4,p);
        double[][] q={powers(i,v,s1,p),powers(i+0.5*h*k1.di,v+0.5*h*k1.dv,s2,p),
                powers(i+0.5*h*k2.di,v+0.5*h*k2.dv,s2,p),powers(i+h*k3.di,v+h*k3.dv,s4,p)};
        double[] e=new double[7];
        for(int j=0;j<7;j++)e[j]=h*(q[0][j]+2*q[1][j]+2*q[2][j]+q[3][j])/6.0;
        return new S(i+h*(k1.di+2*k2.di+2*k3.di+k4.di)/6.0,
                v+h*(k1.dv+2*k2.dv+2*k3.dv+k4.dv)/6.0,e);
    }
    private static double max(double[] a){double m=0;for(double x:a)m=Math.max(m,Math.abs(x));return m;}
    private static double min(double[] a){double m=Double.POSITIVE_INFINITY;for(double x:a)m=Math.min(m,x);return m;}
    public static Result simulate(double[] times,double[] emf,PiAfeInput p){
        if(times==null||emf==null||times.length<3||times.length!=emf.length)throw new IllegalArgumentException("موجة RX غير صالحة");
        for(int i=0;i<times.length;i++){
            if((Double.isNaN(times[i])||Double.isInfinite(times[i]))||(Double.isNaN(emf[i])||Double.isInfinite(emf[i]))||(i>0&&times[i]<=times[i-1]))throw new IllegalArgumentException("عينات الزمن أو الجهد غير صالحة");
        }
        double span=times[times.length-1]-times[0];
        if(span/p.maxStep>500000)throw new IllegalArgumentException("AFE يتجاوز 500 ألف خطوة");
        int cap=(int)Math.ceil(span/p.maxStep)+times.length+2;
        double[] t=new double[cap],ic=new double[cap],vin=new double[cap],va=new double[cap],is=new double[cap],itvs=new double[cap],iclamp=new double[cap],stored=new double[cap],eout=new double[cap];
        int n=1; t[0]=times[0]; double i=0,v=0;double[] totals=new double[7];boolean clampActive=false;
        for(int k=0;k<times.length-1;k++){
            double left=times[k],right=times[k+1],dt=right-left;
            int count=Math.max(1,(int)Math.ceil(dt/p.maxStep));
            for(int j=0;j<count;j++){
                double now=left+j*dt/count,h=dt/count;
                S s=advance(i,v,now,h,times,emf,p);i=s.i;v=s.v;
                for(int q=0;q<7;q++)totals[q]+=s.energy[q];
                D d=derivative(i,v,source(times,emf,now+h),p);
                t[n]=now+h;ic[n]=i;vin[n]=v;va[n]=d.va;is[n]=d.is;itvs[n]=d.itvs;iclamp[n]=d.iclamp;eout[n]=source(times,emf,now+h);
                stored[n]=0.5*p.rxInductance*i*i+0.5*p.inputCapacitance*v*v;
                if(Math.abs(d.iclamp)>0)clampActive=true;
                n++;
            }
        }
        double[] tt=new double[n],ii=new double[n],vv=new double[n],vva=new double[n],iis=new double[n],iit=new double[n],iic=new double[n],ee=new double[n],ss=new double[n];
        System.arraycopy(t,0,tt,0,n);System.arraycopy(ic,0,ii,0,n);System.arraycopy(vin,0,vv,0,n);
        System.arraycopy(va,0,vva,0,n);System.arraycopy(is,0,iis,0,n);System.arraycopy(itvs,0,iit,0,n);
        System.arraycopy(iclamp,0,iic,0,n);System.arraycopy(eout,0,ee,0,n);System.arraycopy(stored,0,ss,0,n);
        double[] opout=new double[n];
        double low=p.supplyLow+p.outputHeadroom,high=p.supplyHigh-p.outputHeadroom;
        double output=Math.min(Math.max(p.referenceVoltage,low),high);
        opout[0]=output;int slewCount=0,satCount=0;
        double bw=p.gainBandwidth/p.opampGain;
        for(int k=1;k<n;k++){
            double h=tt[k]-tt[k-1];
            double target=Math.min(Math.max(p.referenceVoltage+p.opampGain*vv[k],low),high);
            double ideal=(target-output)*(-Math.expm1(-2.0*Math.PI*bw*h));
            double limit=p.slewRate*h;
            if(Math.abs(ideal)>limit)slewCount++;
            double raw=output+Math.max(-limit,Math.min(limit,ideal));
            double clipped=Math.min(Math.max(raw,low),high);
            if(clipped!=raw)satCount++;
            output=clipped;opout[k]=output;
        }
        double delta=ss[n-1]-ss[0],residual=totals[0]-(totals[1]+totals[2]+totals[3]+totals[4]+totals[5]+totals[6])-delta;
        return new Result(tt,ee,ii,vva,vv,iis,iit,iic,ss,max(ee),max(ii),max(vva),max(vv),max(iis),max(iic),
                totals[0],totals[1],totals[2],totals[3],totals[4],totals[5],totals[6],delta,residual,
                Math.abs(residual)/Math.max(Math.abs(totals[0]),1e-18),clampActive?1:0,slewCount,satCount,max(opout),min(opout));
    }
}
