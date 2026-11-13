package com.islamlab.app;

import org.junit.Test;
import static org.junit.Assert.*;

public class FilamentPhysicsTest {
    @Test public void circularLoopFieldConvergesToAnalyticalValue() {
        double radius=0.16, z=0.10;
        double exact=FilamentPhysics.circularLoopAxisFieldTesla(radius,z,1.0,1);
        double[] errors=new double[4];
        int[] counts={100,200,400,800};
        for(int i=0;i<counts.length;i++){
            double[][] loop=FilamentPhysics.circularLoop(radius,counts[i],0);
            double actual=FilamentPhysics.fieldAtPoints(loop,new double[][]{{0,0,z}},1.0,1)[0][2];
            errors[i]=Math.abs(actual-exact)/exact;
        }
        assertTrue(errors[3] < 1e-5);
        for(int i=1;i<errors.length;i++) assertTrue(errors[i] < errors[i-1]);
    }

    @Test public void fieldScalesWithCurrentAndTurns() {
        double[][] loop=FilamentPhysics.circularLoop(0.12,512,0);
        double[][] p={{0,0,0.04}};
        double one=FilamentPhysics.fieldAtPoints(loop,p,1.0,1)[0][2];
        double scaled=FilamentPhysics.fieldAtPoints(loop,p,2.5,20)[0][2];
        assertEquals(one*50.0,scaled,Math.abs(scaled)*1e-12);
    }

    @Test public void mutualInductanceIsReciprocal() {
        double[][] tx=FilamentPhysics.circularLoop(0.12,256,0);
        double[][] rx=FilamentPhysics.circularLoop(0.10,256,0.015);
        double ab=FilamentPhysics.mutualInductanceHenries(tx,rx,20,30);
        double ba=FilamentPhysics.mutualInductanceHenries(rx,tx,30,20);
        assertTrue(ab>0);
        assertEquals(ab,ba,Math.abs(ab)*1e-12);
    }

    @Test public void reversingRxPathReversesMutualInductanceSign() {
        double[][] tx=FilamentPhysics.circularLoop(0.12,256,0);
        double[][] rx=FilamentPhysics.circularLoop(0.10,256,0.015);
        double[][] reversed=new double[rx.length][3];
        for(int i=0;i<rx.length;i++) reversed[i]=rx[rx.length-1-i].clone();
        double forward=FilamentPhysics.mutualInductanceHenries(tx,rx,1,1);
        double backward=FilamentPhysics.mutualInductanceHenries(tx,reversed,1,1);
        assertEquals(-forward,backward,Math.abs(forward)*1e-12);
    }

    @Test public void pathLengthMatchesCircleCircumference() {
        double radius=0.16;
        double length=FilamentPhysics.pathLengthMetres(FilamentPhysics.circularLoop(radius,2048,0));
        assertEquals(2*Math.PI*radius,length,2*Math.PI*radius*1e-6);
    }

    @Test(expected=IllegalArgumentException.class)
    public void rejectsNonFiniteCoordinates() {
        FilamentPhysics.fieldAtPoints(new double[][]{{0,0,0},{1,0,0},{1,1,0},{Double.NaN,0,0}},
                new double[][]{{0,0,1}},1.0,1);
    }
}
