"""Axisymmetric multi-ring conducting-disk surrogate for Mono Spiral PI.

The disk is approximated by concentric shorted conducting loops. This is a
reduced-order eddy-current surrogate, not a full 3-D FEM model. It is useful
for controlled parameter sweeps and for exposing position/depth dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from mono_spiral_geometry import MonoSpiral

MU0 = 4.0 * math.pi * 1e-7


@dataclass(frozen=True)
class Coil:
    """Nominal simulation fixture, not a measured coil characterization.

    Resistance is the geometry-based 20 C copper estimate. The 175.8 uH
    inductance is a provisional model input and has not yet been validated
    against a field measurement or an independent inductance calculation.
    """
    resistance_ohm: float = 1.0641
    inductance_h: float = 175.8e-6
    outer_side_m: float = 0.350
    turns: int = 13
    pitch_m: float = 0.0012


@dataclass(frozen=True)
class ConductiveDisk:
    radius_m: float
    thickness_m: float
    conductivity_s_m: float
    depth_m: float
    x_offset_m: float = 0.0
    y_offset_m: float = 0.0
    rings: int = 6

    def validate(self) -> None:
        if min(self.radius_m, self.thickness_m, self.conductivity_s_m, self.depth_m) <= 0:
            raise ValueError("disk radius, thickness, conductivity and depth must be positive")
        if self.rings < 1:
            raise ValueError("rings must be at least one")
        if self.rings > 8:
            raise ValueError("more than 8 target rings are unsupported until the reduced-order model is revalidated")


@dataclass(frozen=True)
class Pulse:
    voltage_v: float = 12.0
    on_time_s: float = 200e-6
    clamp_resistance_ohm: float = 20.0
    time_step_s: float = 0.5e-6

    def validate(self) -> None:
        if self.voltage_v < 0 or self.on_time_s <= 0 or self.clamp_resistance_ohm <= 0:
            raise ValueError("invalid pulse parameters")
        if self.time_step_s <= 0:
            raise ValueError("time_step_s must be positive")


def _segments_coil_path(coil: Coil, subdivisions: int = 16):
    """Discretize the same continuous spiral used by the geometry model.

    Each straight section, including all radial inter-turn connectors, is
    subdivided uniformly. This prevents the target-coupling model from silently
    reverting to electrically disconnected concentric square loops.
    """
    if subdivisions < 1:
        raise ValueError("subdivisions must be positive")
    geometry = MonoSpiral(
        outer_side_m=coil.outer_side_m,
        turns=coil.turns,
        pitch_m=coil.pitch_m,
    )
    segments = []
    for a, b in geometry.continuous_spiral_segments():
        for q in range(subdivisions):
            f0, f1 = q / subdivisions, (q + 1) / subdivisions
            p0 = tuple(a[i] + (b[i] - a[i]) * f0 for i in range(3))
            p1 = tuple(a[i] + (b[i] - a[i]) * f1 for i in range(3))
            segments.append((p0, p1))
    return segments


def _segments_ring(radius: float, z: float, cx: float, cy: float, count: int):
    points = [
        (cx + radius*math.cos(2*math.pi*k/count),
         cy + radius*math.sin(2*math.pi*k/count), z)
        for k in range(count + 1)
    ]
    return list(zip(points[:-1], points[1:]))


def _mutual_neumann(seg_a, seg_b) -> float:
    total = 0.0
    for a0,a1 in seg_a:
        da = tuple(a1[i]-a0[i] for i in range(3))
        ma = tuple((a1[i]+a0[i])*0.5 for i in range(3))
        for b0,b1 in seg_b:
            db = tuple(b1[i]-b0[i] for i in range(3))
            mb = tuple((b1[i]+b0[i])*0.5 for i in range(3))
            rx,ry,rz = ma[0]-mb[0], ma[1]-mb[1], ma[2]-mb[2]
            r = math.sqrt(rx*rx+ry*ry+rz*rz)
            if r == 0.0:
                raise ValueError("coincident filament segments in mutual-inductance calculation")
            dot = da[0]*db[0] + da[1]*db[1] + da[2]*db[2]
            total += dot/r
    return MU0/(4.0*math.pi)*total



def _coaxial_loop_mutual(radius_a: float, radius_b: float, axial_gap: float = 0.0,
                        integration_steps: int = 2048) -> float:
    """Mutual inductance of coaxial circular filaments via elliptic-integral quadrature."""
    if min(radius_a, radius_b) <= 0 or axial_gap < 0:
        raise ValueError("loop radii must be positive and axial gap non-negative")
    if radius_a == radius_b and axial_gap == 0:
        raise ValueError("self inductance requires finite conductor cross-section")
    if integration_steps < 2 or integration_steps % 2:
        raise ValueError("Simpson integration_steps must be an even integer >= 2")
    m = 4.0*radius_a*radius_b/((radius_a+radius_b)**2+axial_gap**2)
    m = min(max(m,0.0),1.0-1e-15)
    h = (math.pi/2.0)/integration_steps
    sum_k = 0.0
    sum_e = 0.0
    for i in range(integration_steps+1):
        theta=i*h
        q=1.0-m*math.sin(theta)**2
        weight=1 if i in (0,integration_steps) else (4 if i%2 else 2)
        root=math.sqrt(q)
        sum_k += weight/root
        sum_e += weight*root
    K=sum_k*h/3.0
    E=sum_e*h/3.0
    k=math.sqrt(m)
    return MU0*math.sqrt(radius_a*radius_b)*(((2.0-m)*K-2.0*E)/k)


def _solve(matrix, rhs):
    """Gaussian elimination with partial pivoting."""
    a = [list(row) + [rhs[i]] for i,row in enumerate(matrix)]
    n = len(rhs)
    for col in range(n):
        pivot = max(range(col,n), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-24:
            raise ValueError("singular inductance matrix")
        a[col],a[pivot] = a[pivot],a[col]
        scale = a[col][col]
        for j in range(col,n+1):
            a[col][j] /= scale
        for row in range(n):
            if row == col:
                continue
            factor = a[row][col]
            for j in range(col,n+1):
                a[row][j] -= factor*a[col][j]
    return [a[i][n] for i in range(n)]


def build_disk_model(coil: Coil, disk: ConductiveDisk, ring_segments: int = 96):
    disk.validate()
    if ring_segments < 24:
        raise ValueError("ring_segments must be at least 24")
    # Equal-area annuli avoid an unrealistically wide first ring around r=0.
    # Each ring's radial width is retained for its effective conductor section.
    edges = [disk.radius_m*math.sqrt(i/disk.rings) for i in range(disk.rings+1)]
    radii = [disk.radius_m*math.sqrt((i+0.5)/disk.rings) for i in range(disk.rings)]
    widths = [edges[i+1]-edges[i] for i in range(disk.rings)]
    coil_segments = _segments_coil_path(coil)
    target_segments = [
        _segments_ring(r,disk.depth_m,disk.x_offset_m,disk.y_offset_m,ring_segments)
        for r in radii
    ]

    n = disk.rings + 1
    L = [[0.0]*n for _ in range(n)]
    R = [coil.resistance_ohm] + [
        2*math.pi*r/(disk.conductivity_s_m*widths[i]*disk.thickness_m)
        for i,r in enumerate(radii)
    ]
    L[0][0] = coil.inductance_h
    for i in range(disk.rings):
        r = radii[i]
        area = widths[i]*disk.thickness_m
        equivalent_wire_radius = math.sqrt(area/math.pi)
        L[i+1][i+1] = MU0*r*(math.log(8*r/equivalent_wire_radius)-2.0)
        L[0][i+1] = L[i+1][0] = _mutual_neumann(coil_segments,target_segments[i])
    for i in range(disk.rings):
        for j in range(i+1,disk.rings):
            # Exact coaxial-loop mutual inductance avoids loss of matrix
            # positive-definiteness from coarse polygon midpoint quadrature.
            m = _coaxial_loop_mutual(radii[i],radii[j],0.0)
            L[i+1][j+1] = L[j+1][i+1] = m

    # Cholesky positive-definiteness check; reject invalid surrogate matrices.
    lower = [[0.0]*n for _ in range(n)]
    for i in range(n):
        for j in range(i+1):
            value = L[i][j] - sum(lower[i][k]*lower[j][k] for k in range(j))
            if i == j:
                if value <= 0:
                    raise ValueError("inductance matrix is not positive definite; refine model")
                lower[i][j] = math.sqrt(value)
            else:
                lower[i][j] = value/lower[j][j]
    diagonal = [lower[i][i] for i in range(n)]
    if min(diagonal)/max(diagonal) < 1e-4:
        raise ValueError("inductance matrix is ill-conditioned for this ring discretization")
    return L, R, radii


def simulate(coil: Coil, disk: ConductiveDisk, pulse: Pulse,
             ring_segments: int = 96) -> list[dict[str,float]]:
    """Run primary drive/clamp, then open-coil disk-current receive decay."""
    pulse.validate()
    L,R,radii = build_disk_model(coil,disk,ring_segments)
    n = len(R)
    currents = [0.0]*n
    dt = pulse.time_step_s
    clamp_decay = max(10*coil.inductance_h/(coil.resistance_ohm+pulse.clamp_resistance_ohm),20e-6)
    total = pulse.on_time_s + clamp_decay
    steps = math.ceil(total/dt)
    rows = []

    def deriv(state, source, primary_extra_r):
        rhs = [source-(R[0]+primary_extra_r)*state[0]] + [-R[i]*state[i] for i in range(1,n)]
        return _solve(L,rhs)

    def rk4(state, source, primary_extra_r):
        k1=deriv(state,source,primary_extra_r)
        s2=[state[i]+dt*k1[i]/2 for i in range(n)]
        k2=deriv(s2,source,primary_extra_r)
        s3=[state[i]+dt*k2[i]/2 for i in range(n)]
        k3=deriv(s3,source,primary_extra_r)
        s4=[state[i]+dt*k3[i] for i in range(n)]
        k4=deriv(s4,source,primary_extra_r)
        return [state[i]+dt*(k1[i]+2*k2[i]+2*k3[i]+k4[i])/6 for i in range(n)]

    for k in range(steps+1):
        t=k*dt
        drive = t < pulse.on_time_s
        source = pulse.voltage_v if drive else 0.0
        extra_r = 0.0 if drive else pulse.clamp_resistance_ohm
        if k:
            currents=rk4(currents,source,extra_r)
        rows.append({"time_s":t,"phase":0.0 if drive else 1.0,
                     "coil_current_a":currents[0],
                     "target_total_abs_current_a":sum(abs(v) for v in currents[1:])})

    # Primary winding is now isolated (i1 forced to zero). The target loops
    # remain mutually coupled and decay through their own resistances.
    target_L=[row[1:] for row in L[1:]]
    target_R=R[1:]
    target_i=currents[1:]
    target_n=len(target_i)

    def target_deriv(state):
        return _solve(target_L,[-target_R[i]*state[i] for i in range(target_n)])

    def target_rk4(state):
        k1=target_deriv(state)
        s2=[state[i]+dt*k1[i]/2 for i in range(target_n)]
        k2=target_deriv(s2)
        s3=[state[i]+dt*k2[i]/2 for i in range(target_n)]
        k3=target_deriv(s3)
        s4=[state[i]+dt*k3[i] for i in range(target_n)]
        k4=target_deriv(s4)
        return [state[i]+dt*(k1[i]+2*k2[i]+2*k3[i]+k4[i])/6 for i in range(target_n)]

    t0=rows[-1]["time_s"]
    rx_steps=math.ceil(500e-6/dt)
    for k in range(1,rx_steps+1):
        target_i=target_rk4(target_i)
        didt=target_deriv(target_i)
        # Open-circuit receive emf from the coupled target loops.
        rx_v=-sum(L[0][i+1]*didt[i] for i in range(target_n))
        rows.append({"time_s":t0+k*dt,"phase":2.0,
                     "coil_current_a":0.0,
                     "target_total_abs_current_a":sum(abs(v) for v in target_i),
                     "rx_voltage_v":rx_v})
    return rows


def receive_peak(rows, start_s: float = 0.0, stop_s: float = 500e-6) -> float:
    """Return peak receive voltage in a window relative to RX-phase start.

    The RX phase begins after the TX pulse and clamp interval, so comparing
    absolute simulation time against a 500 us stop value truncates the intended
    receive tail. Window bounds here are measured from the first phase-2 row.
    """
    receive_rows = [row for row in rows if row["phase"] == 2.0]
    if not receive_rows:
        return 0.0
    phase_start = receive_rows[0]["time_s"]
    return max(
        (
            abs(row.get("rx_voltage_v", 0.0))
            for row in receive_rows
            if start_s <= row["time_s"] - phase_start <= stop_s
        ),
        default=0.0,
    )
