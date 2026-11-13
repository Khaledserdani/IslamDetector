package com.islamlab.app;

/** Coupled two-loop TX/target transient with open-circuit RX voltage observation. */
public final class PiPulseEngine {
    private PiPulseEngine() {}

    public static final class Result {
        public final double[] time, txCurrent, targetCurrent, rxDirect, rxTarget, rxTotal, storedEnergy;
        public final double mTxTarget, mTxRx, mRxTarget, normalizedInductanceDeterminant;
        public final double peakTxCurrent, txCurrentAtTurnoff, peakTargetCurrent;
        public final double peakRxVoltage, peakRxAfterTurnoff, peakRxDirect, peakRxTarget;
        public final double sourceEnergy, txLossEnergy, targetLossEnergy, clampEnergy, storedEnergyChange, energyResidual;
        public final double energyRelativeError;

        Result(double[] time,double[] itx,double[] it,double[] vd,double[] vt,double[] vr,double[] energy,
               double mtt,double mtr,double mrt,double normalizedDet,double ptx,double turnoff,double pt,
               double prv,double post,double pd,double ptarget,double source,double txloss,
               double targetloss,double clamp,double delta,double residual,double relative) {
            this.time=time; txCurrent=itx; targetCurrent=it; rxDirect=vd; rxTarget=vt; rxTotal=vr; storedEnergy=energy;
            mTxTarget=mtt; mTxRx=mtr; mRxTarget=mrt; normalizedInductanceDeterminant=normalizedDet;
            peakTxCurrent=ptx; txCurrentAtTurnoff=turnoff; peakTargetCurrent=pt;
            peakRxVoltage=prv; peakRxAfterTurnoff=post; peakRxDirect=pd; peakRxTarget=ptarget;
            sourceEnergy=source; txLossEnergy=txloss; targetLossEnergy=targetloss; clampEnergy=clamp;
            storedEnergyChange=delta; energyResidual=residual; energyRelativeError=relative;
        }
    }

    private static final class Derivative {
        final double tx,target;
        Derivative(double a,double b){tx=a;target=b;}
    }
    private static Derivative derivative(double itx,double it,double ltx,double lt,double rtx,double rt,
                                         double mutual,double determinant,double bus,double clamp,boolean on) {
        double clampDrop=on?0.0:clamp*(itx>0?1.0:itx<0?-1.0:0.0);
        double applied=(on?bus:0.0)-rtx*itx-clampDrop;
        double dtx=(lt*applied+mutual*rt*it)/determinant;
        double dt=(-mutual*applied-ltx*rt*it)/determinant;
        return new Derivative(dtx,dt);
    }
    private static double energy(double itx,double it,double ltx,double lt,double mutual){
        return 0.5*ltx*itx*itx+mutual*itx*it+0.5*lt*it*it;
    }
    private static double maxAbs(double[] a,int from){
        double m=0; for(int i=from;i<a.length;i++)m=Math.max(m,Math.abs(a[i])); return m;
    }
    private static double[] powers(double x,double y,boolean on,double bus,double rtx,double rt,double clamp){
        return new double[]{on?bus*x:0.0,rtx*x*x,rt*y*y,on?0.0:clamp*Math.abs(x)};
    }

    public static Result simulate(PiPulseInput p) {
        double mtt=FilamentPhysics.mutualInductanceHenries(p.txPath,p.targetPath,p.txTurns,p.targetTurns);
        double mtr=FilamentPhysics.mutualInductanceHenries(p.txPath,p.rxPath,p.txTurns,p.rxTurns);
        double mrt=FilamentPhysics.mutualInductanceHenries(p.rxPath,p.targetPath,p.rxTurns,p.targetTurns);
        double ltx=p.txInductance, lt=p.targetInductance, lrx=p.rxInductance;
        double d2=ltx*lt-mtt*mtt;
        if(d2<=Math.max(ltx*lt*1e-12,1e-24)) throw new IllegalArgumentException("اقتران TX/الهدف يجعل مصفوفة المحاثة غير مستقرة");
        double det3=ltx*(lt*lrx-mrt*mrt)-mtt*(mtt*lrx-mrt*mtr)+mtr*(mtt*mrt-lt*mtr);
        if(det3<=Math.max(ltx*lt*lrx*1e-12,1e-36)) throw new IllegalArgumentException("مصفوفة محاثة TX/الهدف/RX غير موجبة التعريف؛ راجع الاقتران والهندسة");
        double normalizedDet=det3/(ltx*lt*lrx); // normalized determinant indicator, not an eigenvalue

        int capacity=(int)Math.ceil(p.stopTime/p.timeStep)+4;
        if(capacity>2000000) throw new IllegalArgumentException("عدد خطوات المحاكاة يتجاوز الحد الآمن");
        double[] time=new double[capacity], itx=new double[capacity], it=new double[capacity];
        double[] vd=new double[capacity], vt=new double[capacity], vr=new double[capacity], stored=new double[capacity];
        int n=1; double t=0, x=0, y=0;
        double sourceEnergy=0,txLossEnergy=0,targetLossEnergy=0,clampEnergy=0;
        stored[0]=0;
        while(t<p.stopTime-Math.max(1e-15,p.stopTime*1e-14)){
            boolean on=t<p.pulseWidth-Math.max(1e-15,p.pulseWidth*1e-14);
            double boundary=on?p.pulseWidth:p.stopTime;
            double h=Math.min(p.timeStep,Math.min(p.stopTime-t,boundary-t));
            if(h<=0) throw new IllegalStateException("خطوة زمنية غير موجبة");
            double x1=x,y1=y;
            Derivative k1=derivative(x1,y1,ltx,lt,p.txResistance,p.targetResistance,mtt,d2,p.busVoltage,p.clampVoltage,on);
            double x2=x+0.5*h*k1.tx,y2=y+0.5*h*k1.target;
            Derivative k2=derivative(x2,y2,ltx,lt,p.txResistance,p.targetResistance,mtt,d2,p.busVoltage,p.clampVoltage,on);
            double x3=x+0.5*h*k2.tx,y3=y+0.5*h*k2.target;
            Derivative k3=derivative(x3,y3,ltx,lt,p.txResistance,p.targetResistance,mtt,d2,p.busVoltage,p.clampVoltage,on);
            double x4=x+h*k3.tx,y4=y+h*k3.target;
            Derivative k4=derivative(x4,y4,ltx,lt,p.txResistance,p.targetResistance,mtt,d2,p.busVoltage,p.clampVoltage,on);
            double[] q1=powers(x1,y1,on,p.busVoltage,p.txResistance,p.targetResistance,p.clampVoltage);
            double[] q2=powers(x2,y2,on,p.busVoltage,p.txResistance,p.targetResistance,p.clampVoltage);
            double[] q3=powers(x3,y3,on,p.busVoltage,p.txResistance,p.targetResistance,p.clampVoltage);
            double[] q4=powers(x4,y4,on,p.busVoltage,p.txResistance,p.targetResistance,p.clampVoltage);
            sourceEnergy+=h*(q1[0]+2*q2[0]+2*q3[0]+q4[0])/6.0;
            txLossEnergy+=h*(q1[1]+2*q2[1]+2*q3[1]+q4[1])/6.0;
            targetLossEnergy+=h*(q1[2]+2*q2[2]+2*q3[2]+q4[2])/6.0;
            clampEnergy+=h*(q1[3]+2*q2[3]+2*q3[3]+q4[3])/6.0;
            x+=h*(k1.tx+2*k2.tx+2*k3.tx+k4.tx)/6.0;
            y+=h*(k1.target+2*k2.target+2*k3.target+k4.target)/6.0;
            t+=h;
            boolean sampleOn=t<p.pulseWidth-Math.max(1e-15,p.pulseWidth*1e-14);
            Derivative deriv=derivative(x,y,ltx,lt,p.txResistance,p.targetResistance,mtt,d2,p.busVoltage,p.clampVoltage,sampleOn);
            time[n]=t; itx[n]=x; it[n]=y;
            vd[n]=-mtr*deriv.tx; vt[n]=-mrt*deriv.target; vr[n]=vd[n]+vt[n];
            stored[n]=energy(x,y,ltx,lt,mtt);
            n++;
            if(n>=capacity) throw new IllegalStateException("تجاوزت المحاكاة سعة سجل العينات");
        }
        double[] ta=trim(time,n), xa=trim(itx,n), ya=trim(it,n), da=trim(vd,n), tva=trim(vt,n), va=trim(vr,n), ea=trim(stored,n);
        double delta=ea[n-1]-ea[0], residual=sourceEnergy-txLossEnergy-targetLossEnergy-clampEnergy-delta;
        int turnoff=0; while(turnoff<n && ta[turnoff]<p.pulseWidth-1e-15)turnoff++;
        double peakTx=maxAbs(xa,0), peakTarget=maxAbs(ya,0), peakRx=maxAbs(va,0);
        double post=maxAbs(va,turnoff), peakDirect=maxAbs(da,0), peakTargetRx=maxAbs(tva,0);
        return new Result(ta,xa,ya,da,tva,va,ea,mtt,mtr,mrt,normalizedDet,peakTx,
                xa[Math.min(turnoff,n-1)],peakTarget,peakRx,post,peakDirect,peakTargetRx,
                sourceEnergy,txLossEnergy,targetLossEnergy,clampEnergy,delta,residual,
                Math.abs(residual)/Math.max(Math.abs(sourceEnergy),1e-18));
    }
    private static double[] trim(double[] a,int n){double[] b=new double[n];System.arraycopy(a,0,b,0,n);return b;}
}
