package com.islamlab.app;

/**
 * Geometry-driven 3D wire-path reference calculations. Open paths remain open;
 * closed loops must repeat their first vertex. B is integrated exactly for each
 * straight segment; accuracy still depends on how finely a curved wire is polygonized.
 * Coordinates are metres, current is amperes, B is tesla and M is henry.
 * The turns multiplier represents coincident identical paths only. A complete
 * multi-turn spiral centerline must be supplied once with turns=1.
 * This is a thin-filament magnetostatic kernel, not a transient PI/soil solver.
 */
public final class FilamentPhysics {
    private static final double MU0 = 4.0e-7 * Math.PI;
    private FilamentPhysics() {}
    private static boolean finite(double value) { return !Double.isNaN(value) && !Double.isInfinite(value); }

    private static final class Segments {
        final double[][] mid;
        final double[][] dl;
        Segments(double[][] mid, double[][] dl) { this.mid = mid; this.dl = dl; }
    }

    private static Segments segments(double[][] path, String name) {
        if (path == null || path.length < 2) throw new IllegalArgumentException(name + ": at least two 3D vertices required");
        double[][] points = new double[path.length][3];
        for (int i = 0; i < path.length; i++) {
            if (path[i] == null || path[i].length != 3) throw new IllegalArgumentException(name + ": each vertex must have three coordinates");
            for (int j = 0; j < 3; j++) {
                if (!finite(path[i][j])) throw new IllegalArgumentException(name + ": coordinates must be finite");
                points[i][j] = path[i][j];
            }
        }
        double[][] mid = new double[path.length - 1][3];
        double[][] dl = new double[path.length - 1][3];
        for (int i = 0; i < path.length - 1; i++) {
            double length2 = 0;
            for (int j = 0; j < 3; j++) {
                dl[i][j] = points[i + 1][j] - points[i][j];
                mid[i][j] = 0.5 * (points[i + 1][j] + points[i][j]);
                length2 += dl[i][j] * dl[i][j];
            }
            if (length2 <= 1e-24) throw new IllegalArgumentException(name + ": zero-length segment");
        }
        return new Segments(mid, dl);
    }

    private static double distance(double[] a, double[] b) {
        double x=a[0]-b[0], y=a[1]-b[1], z=a[2]-b[2];
        return Math.sqrt(x*x+y*y+z*z);
    }

    public static double pathLengthMetres(double[][] path) {
        Segments s = segments(path, "coil");
        double total = 0;
        for (double[] dl : s.dl) total += Math.sqrt(dl[0]*dl[0]+dl[1]*dl[1]+dl[2]*dl[2]);
        return total;
    }

    public static double[][] fieldAtPoints(double[][] path, double[][] observationPoints,
                                            double currentAmps, int turns) {
        if (!finite(currentAmps) || turns < 1) throw new IllegalArgumentException("current must be finite and turns positive");
        if (observationPoints == null) throw new IllegalArgumentException("observation points are required");
        Segments s = segments(path, "coil");
        double[][] result = new double[observationPoints.length][3];
        double scale = MU0 * currentAmps * turns / (4.0 * Math.PI);
        for (int p = 0; p < observationPoints.length; p++) {
            double[] point = observationPoints[p];
            if (point == null || point.length != 3) throw new IllegalArgumentException("each observation point must have three coordinates");
            for (double value : point) if (!finite(value)) throw new IllegalArgumentException("observation coordinates must be finite");
            double bx=0, by=0, bz=0;
            for (int i = 0; i < s.mid.length; i++) {
                double length = Math.sqrt(s.dl[i][0]*s.dl[i][0] + s.dl[i][1]*s.dl[i][1] + s.dl[i][2]*s.dl[i][2]);
                double ux=s.dl[i][0]/length, uy=s.dl[i][1]/length, uz=s.dl[i][2]/length;
                double rx=point[0]-(s.mid[i][0]-0.5*s.dl[i][0]);
                double ry=point[1]-(s.mid[i][1]-0.5*s.dl[i][1]);
                double rz=point[2]-(s.mid[i][2]-0.5*s.dl[i][2]);
                double axial=rx*ux+ry*uy+rz*uz;
                double px=rx-axial*ux, py=ry-axial*uy, pz=rz-axial*uz;
                double rho2=px*px+py*py+pz*pz;
                if (rho2 <= 1e-24) {
                    if (axial >= -1e-12 && axial <= length+1e-12)
                        throw new IllegalArgumentException("field is singular on a wire segment");
                    continue;
                }
                double end=axial-length;
                double factor=axial/(rho2*Math.sqrt(rho2+axial*axial))
                        - end/(rho2*Math.sqrt(rho2+end*end));
                bx += (uy*pz-uz*py)*factor;
                by += (uz*px-ux*pz)*factor;
                bz += (ux*py-uy*px)*factor;
            }
            result[p][0]=scale*bx; result[p][1]=scale*by; result[p][2]=scale*bz;
        }
        return result;
    }

    public static double mutualInductanceHenries(double[][] pathA, double[][] pathB,
                                                  int turnsA, int turnsB) {
        if (turnsA < 1 || turnsB < 1) throw new IllegalArgumentException("turn counts must be positive");
        Segments a=segments(pathA,"coil A"), b=segments(pathB,"coil B");
        double sum=0;
        for (int i=0;i<a.mid.length;i++) {
            for (int j=0;j<b.mid.length;j++) {
                double dx=a.mid[i][0]-b.mid[j][0];
                double dy=a.mid[i][1]-b.mid[j][1];
                double dz=a.mid[i][2]-b.mid[j][2];
                double distance=Math.sqrt(dx*dx+dy*dy+dz*dz);
                if (distance <= 1e-9) throw new IllegalArgumentException("filament paths intersect or approach within 1 nm");
                double dot=a.dl[i][0]*b.dl[j][0]+a.dl[i][1]*b.dl[j][1]+a.dl[i][2]*b.dl[j][2];
                sum += dot/distance;
            }
        }
        return MU0*turnsA*turnsB*sum/(4.0*Math.PI);
    }

    public static double[][] circularLoop(double radiusMetres, int segmentCount, double zMetres) {
        if (!finite(radiusMetres) || radiusMetres <= 0 || segmentCount < 16 || !finite(zMetres))
            throw new IllegalArgumentException("invalid circular-loop geometry");
        double[][] points=new double[segmentCount+1][3];
        for(int i=0;i<=segmentCount;i++){
            double angle=2.0*Math.PI*i/segmentCount;
            points[i][0]=radiusMetres*Math.cos(angle);
            points[i][1]=radiusMetres*Math.sin(angle);
            points[i][2]=zMetres;
        }
        return points;
    }

    public static double circularLoopAxisFieldTesla(double radiusMetres, double zMetres,
                                                     double currentAmps, int turns) {
        if (!finite(radiusMetres) || radiusMetres <= 0 || !finite(zMetres)
                || !finite(currentAmps) || turns < 1) throw new IllegalArgumentException("invalid circular-loop parameters");
        double sum=radiusMetres*radiusMetres+zMetres*zMetres;
        return MU0*turns*currentAmps*radiusMetres*radiusMetres/(2.0*Math.pow(sum,1.5));
    }
}
