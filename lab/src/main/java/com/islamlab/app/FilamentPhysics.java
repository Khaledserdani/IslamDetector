package com.islamlab.app;

/**
 * Geometry-driven 3D filament reference calculations.
 * Coordinates are metres, current is amperes, B is tesla and M is henry.
 * This is a thin-filament magnetostatic kernel, not a transient PI/soil solver.
 */
public final class FilamentPhysics {
    private static final double MU0 = 4.0e-7 * Math.PI;
    private FilamentPhysics() {}

    private static final class Segments {
        final double[][] mid;
        final double[][] dl;
        Segments(double[][] mid, double[][] dl) { this.mid = mid; this.dl = dl; }
    }

    private static Segments segments(double[][] path, String name) {
        if (path == null || path.length < 4) throw new IllegalArgumentException(name + ": at least four 3D vertices required");
        double[][] points = new double[path.length + 1][3];
        for (int i = 0; i < path.length; i++) {
            if (path[i] == null || path[i].length != 3) throw new IllegalArgumentException(name + ": each vertex must have three coordinates");
            for (int j = 0; j < 3; j++) {
                if (!Double.isFinite(path[i][j])) throw new IllegalArgumentException(name + ": coordinates must be finite");
                points[i][j] = path[i][j];
            }
        }
        int count = path.length;
        if (distance(points[0], points[count - 1]) > 1e-9) {
            points[count] = points[0].clone();
            count++;
        }
        double[][] mid = new double[count - 1][3];
        double[][] dl = new double[count - 1][3];
        for (int i = 0; i < count - 1; i++) {
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
        if (!Double.isFinite(currentAmps) || turns < 1) throw new IllegalArgumentException("current must be finite and turns positive");
        if (observationPoints == null) throw new IllegalArgumentException("observation points are required");
        Segments s = segments(path, "coil");
        double[][] result = new double[observationPoints.length][3];
        double scale = MU0 * currentAmps * turns / (4.0 * Math.PI);
        for (int p = 0; p < observationPoints.length; p++) {
            double[] point = observationPoints[p];
            if (point == null || point.length != 3) throw new IllegalArgumentException("each observation point must have three coordinates");
            for (double value : point) if (!Double.isFinite(value)) throw new IllegalArgumentException("observation coordinates must be finite");
            double bx=0, by=0, bz=0;
            for (int i = 0; i < s.mid.length; i++) {
                double rx=point[0]-s.mid[i][0], ry=point[1]-s.mid[i][1], rz=point[2]-s.mid[i][2];
                double r2=rx*rx+ry*ry+rz*rz;
                if (r2 <= 1e-20) throw new IllegalArgumentException("field is singular at a wire-segment midpoint");
                double invR3 = 1.0 / (r2 * Math.sqrt(r2));
                bx += (s.dl[i][1]*rz - s.dl[i][2]*ry) * invR3;
                by += (s.dl[i][2]*rx - s.dl[i][0]*rz) * invR3;
                bz += (s.dl[i][0]*ry - s.dl[i][1]*rx) * invR3;
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
        if (!Double.isFinite(radiusMetres) || radiusMetres <= 0 || segmentCount < 16 || !Double.isFinite(zMetres))
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
        if (!Double.isFinite(radiusMetres) || radiusMetres <= 0 || !Double.isFinite(zMetres)
                || !Double.isFinite(currentAmps) || turns < 1) throw new IllegalArgumentException("invalid circular-loop parameters");
        double sum=radiusMetres*radiusMetres+zMetres*zMetres;
        return MU0*turns*currentAmps*radiusMetres*radiusMetres/(2.0*Math.pow(sum,1.5));
    }
}
