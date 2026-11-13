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
    private static final class Step {
        final double tx,target,sourceEnergy,txLoss,targetLoss,clampEnergy;
        Step(double x,double y,double source,double txloss,double targetloss,double clamp){
            tx=x;target=y;sourceEnergy=source;txLoss=txloss;targetLoss=targetloss;clampEnergy=clamp;
        }
    }

    private static Derivative derivative(double itx,double it,double ltx,double lt,double rtx,double rt,
            double mutual,double determinant,double bus,double clamp,boolean on,boolean txBlocked) {
        if(txBlocked) return new Derivative(0.0,-rt*it/lt);
        double clampDrop=on?0.0:(itx>0.0?clamp:0.0);
        double applied=(on?bus:0.0)-rtx*itx-clampDrop;
        double dtx=(lt*applied+mutual*rt*it)/determinant;
        double dt=(-mutual*applied-ltx*rt*it)/determinant;
        return new Derivative(dtx,dt);
    }

    private static double[] powers(double x,double y,boolean on,boolean blocked,
            double bus,double rtx,double rt,double clamp){
        return new double[]{on?bus*x:0.0,blocked?0.0:rtx*x*x,rt*y*y,
                on||blocked?0.0:clamp*Math.max(x,0.0)};
    }

    private static Step advance(double x,double y,double h,boolean on,boolean blocked,
            double ltx,double lt,double rtx,double rt,double mutual,double determinant,
            double bus,double clamp){
        Derivative k1=derivative(x,y,ltx,lt,rtx,rt,mutual,determinant,bus,clamp,on,blocked);
        double x2=x+0.5*h*k1.tx,y2=y+0.5*h*k1.target;
        Derivative k2=derivative(x2,y2,ltx,lt,rtx,rt,mutual,determinant,bus,clamp,on,blocked);
        double x3=x+0.5*h*k2.tx,y3=y+0.5*h*k2.target;
        Derivative k3=derivative(x3,y3,ltx,lt,rtx,rt,mutual,determinant,bus,clamp,on,blocked);
        double x4=x+h*k3.tx,y4=y+h*k3.target;
        Derivative k4=derivative(x4,y4,ltx,lt,rtx,rt,mutual,determinant,bus,clamp,on,blocked);
        double[] q1=powers(x,y,on,blocked,bus,rtx,rt,clamp);
        double[] q2=powers(x2,y2,on,blocked,bus,rtx,rt,clamp);
        double[] q3=powers(x3,y3,on,blocked,bus,rtx,rt,clamp);
        double[] q4=powers(x4,y4,on,blocked,bus,rtx,rt,clamp);
        double source=h*(q1[0]+2*q2[0]+2*q3[0]+q4[0])/6.0;
        double txloss=h*(q1[1]+2*q2[1]+2*q3[1]+q4[1])/6.0;
        double targetloss=h*(q1[2]+2*q2[2]+2*q3[2]+q4[2])/6.0;
        double clampEnergy=h*(q1[3]+2*q2[3]+2*q3[3]+q4[3])/6.0;
        double nextX=x+h*(k1.tx+2*k2.tx+2*k3.tx+k4.tx)/6.0;
        double nextY=y+h*(k1.target+2*k2.target+2*k3.target+k4.target)/6.0;
        return new Step(nextX,nextY,source,txloss,targetloss,clampEnergy);
    }

    private static double energy(double x,double y,double ltx,double lt,double mutual){
        return 0.5*ltx*x*x+mutual*x*y+0.5*lt*y*y;
    }
    private static double maxAbs(double[] a,int from){
        double m=0;for(int i=from;i<a.length;i++)m=Math.max(m,Math.abs(a[i]));return m;
    }
    private static double[] trim(double[] a,int n){double[] b=new double[n];System.arraycopy(a,0,b,0,n);return b;}

    public static Result simulate(PiPulseInput p) {
        double mtt=FilamentPhysics.mutualInductanceHenries(p.txPath,p.targetPath,p.txTurns,p.targetTurns);
        double mtr=FilamentPhysics.mutualInductanceHenries(p.txPath,p.rxPath,p.txTurns,p.rxTurns);
        double mrt=FilamentPhysics.mutualInductanceHenries(p.rxPath,p.targetPath,p.rxTurns,p.targetTurns);
        double ltx=p.txInductance,lt=p.targetInductance,lrx=p.rxInductance;
        double d2=ltx*lt-mtt*mtt;
        if(d2<=Math.max(ltx*lt*1e-12,1e-24))throw new IllegalArgumentException("اقتران TX/الهدف يجعل مصفوفة المحاثة غير مستقرة");
        double det3=ltx*(lt*lrx-mrt*mrt)-mtt*(mtt*lrx-mrt*mtr)+mtr*(mtt*mrt-lt*mtr);
        if(det3<=Math.max(ltx*lt*lrx*1e-12,1e-36))throw new IllegalArgumentException("مصفوفة محاثة TX/الهدف/RX غير موجبة التعريف؛ راجع الاقتران والهندسة");
        double normalizedDet=det3/(ltx*lt*lrx);

        int capacity=(int)Math.ceil(p.stopTime/p.timeStep)+8;
        if(capacity>200008)throw new IllegalArgumentException("عدد خطوات المحاكاة يتجاوز الحد الآمن");
        double[] time=new double[capacity],itx=new double[capacity],it=new double[capacity];
        double[] vd=new double[capacity],vt=new double[capacity],vr=new double[capacity],stored=new double[capacity];
        int n=1;double t=0,x=0,y=0;
        double sourceEnergy=0,txLossEnergy=0,targetLossEnergy=0,clampEnergy=0;
        boolean txBlocked=false;
        while(t<p.stopTime-Math.max(1e-15,p.stopTime*1e-14)){
            boolean on=t<p.pulseWidth-Math.max(1e-15,p.pulseWidth*1e-14);
            double boundary=on?p.pulseWidth:p.stopTime;
            double h=Math.min(p.timeStep,Math.min(p.stopTime-t,boundary-t));
            if(h<=0)throw new IllegalStateException("خطوة زمنية غير موجبة");
            Step trial=advance(x,y,h,on,txBlocked,ltx,lt,p.txResistance,p.targetResistance,mtt,d2,p.busVoltage,p.clampVoltage);
            boolean hitZero=!on&&p.clampVoltage>0&&!txBlocked&&x>0&&trial.tx<=0;
            Step step=trial;
            if(hitZero){
                double lo=0,hi=h;
                for(int i=0;i<48;i++){
                    double mid=0.5*(lo+hi);
                    Step candidate=advance(x,y,mid,false,false,ltx,lt,p.txResistance,p.targetResistance,mtt,d2,p.busVoltage,p.clampVoltage);
                    if(candidate.tx>0)lo=mid;else hi=mid;
                }
                h=hi;
                step=advance(x,y,h,false,false,ltx,lt,p.txResistance,p.targetResistance,mtt,d2,p.busVoltage,p.clampVoltage);
                x=0.0;y=step.target;txBlocked=true;
            }else{
                x=step.tx;y=step.target;
            }
            sourceEnergy+=step.sourceEnergy;txLossEnergy+=step.txLoss;
            targetLossEnergy+=step.targetLoss;clampEnergy+=step.clampEnergy;
            t=Math.min(t+h,p.stopTime);
            boolean sampleOn=t<p.pulseWidth-Math.max(1e-15,p.pulseWidth*1e-14);
            Derivative deriv=derivative(x,y,ltx,lt,p.txResistance,p.targetResistance,mtt,d2,p.busVoltage,p.clampVoltage,sampleOn,txBlocked);
            time[n]=t;itx[n]=x;it[n]=y;
            vd[n]=-mtr*deriv.tx;vt[n]=-mrt*deriv.target;vr[n]=vd[n]+vt[n];
            stored[n]=energy(x,y,ltx,lt,mtt);
            n++;
            if(n>=capacity)throw new IllegalStateException("تجاوزت المحاكاة سعة سجل العينات");
        }
        double[] ta=trim(time,n),xa=trim(itx,n),ya=trim(it,n),da=trim(vd,n),tva=trim(vt,n),va=trim(vr,n),ea=trim(stored,n);
        double delta=ea[n-1]-ea[0];
        double residual=sourceEnergy-txLossEnergy-targetLossEnergy-clampEnergy-delta;
        int turnoff=0;while(turnoff<n&&ta[turnoff]<p.pulseWidth-1e-15)turnoff++;
        double peakTx=maxAbs(xa,0),peakTarget=maxAbs(ya,0),peakRx=maxAbs(va,0);
        double post=maxAbs(va,turnoff),peakDirect=maxAbs(da,0),peakTargetRx=maxAbs(tva,0);
        return new Result(ta,xa,ya,da,tva,va,ea,mtt,mtr,mrt,normalizedDet,peakTx,
                xa[Math.min(turnoff,n-1)],peakTarget,peakRx,post,peakDirect,peakTargetRx,
                sourceEnergy,txLossEnergy,targetLossEnergy,clampEnergy,delta,residual,
                Math.abs(residual)/Math.max(Math.abs(sourceEnergy),1e-18));
    }
}
