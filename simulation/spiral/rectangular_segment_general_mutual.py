"""General Neumann mutual inductance for two straight rectangular conductors.

Six-dimensional tensor-product quadrature over axial coordinates and finite
rectangular cross-sections. Supports arbitrary segment orientations when the
conductor volumes are disjoint. Diagnostic primitive, not a complete coil model.
"""
from __future__ import annotations
import math

MU0 = 4.0 * math.pi * 1e-7

def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))

def _cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])

def _unit(vector, name):
    if len(vector) != 3 or not all(math.isfinite(x) for x in vector):
        raise ValueError(f"{name} must contain three finite coordinates")
    norm = math.sqrt(_dot(vector, vector))
    if norm <= 0.0:
        raise ValueError(f"{name} must be non-zero")
    return tuple(x / norm for x in vector)

def _gauss_legendre(order):
    if order < 2 or order > 16:
        raise ValueError("quadrature order must be between 2 and 16")
    nodes, weights = [0.0]*order, [0.0]*order
    for i in range((order+1)//2):
        z = math.cos(math.pi*(i+0.75)/(order+0.5))
        for _ in range(100):
            p0,p1=1.0,z
            for degree in range(2,order+1):
                p0,p1=p1,((2*degree-1)*z*p1-(degree-1)*p0)/degree
            derivative=order*(z*p1-p0)/(z*z-1.0)
            step=p1/derivative
            z-=step
            if abs(step)<2e-15: break
        else: raise ArithmeticError("Gauss-Legendre root did not converge")
        p0,p1=1.0,z
        for degree in range(2,order+1):
            p0,p1=p1,((2*degree-1)*z*p1-(degree-1)*p0)/degree
        derivative=order*(z*p1-p0)/(z*z-1.0)
        weight=2.0/((1.0-z*z)*derivative*derivative)
        nodes[i],nodes[order-1-i]=-z,z
        weights[i]=weights[order-1-i]=weight
    return nodes,weights

def _validate(center, axis, u, v, length, width, height, name):
    if len(center)!=3 or not all(math.isfinite(x) for x in center):
        raise ValueError(f"{name} center must contain three finite coordinates")
    if not all(math.isfinite(x) and x>0 for x in (length,width,height)):
        raise ValueError(f"{name} dimensions must be finite and positive")
    axis,u,v=_unit(axis,name+" axis"),_unit(u,name+" cross_u"),_unit(v,name+" cross_v")
    tol=1e-10
    if abs(_dot(axis,u))>tol or abs(_dot(axis,v))>tol or abs(_dot(u,v))>tol:
        raise ValueError(f"{name} axis and cross-section basis must be orthonormal")
    handed=_dot(_cross(u,v),axis)
    if abs(abs(handed)-1.0)>tol:
        raise ValueError(f"{name} cross-section basis must span the plane normal to its axis")
    return tuple(center),axis,u,v

def rectangular_segment_mutual_inductance(
    center_a, axis_a, cross_u_a, cross_v_a, length_a_m, width_a_m, height_a_m,
    center_b, axis_b, cross_u_b, cross_v_b, length_b_m, width_b_m, height_b_m,
    order=6,
):
    """Finite-cross-section Neumann mutual inductance in henries.

    Centers and basis vectors are 3-tuples in metres / unit directions.
    Each segment is a straight rectangular prism with uniform axial current.
    The two physical conductor volumes must not overlap. Near-touching cases
    converge slowly and require an explicit quadrature-order study.
    """
    if order<2 or order>16: raise ValueError("quadrature order must be between 2 and 16")
    a=_validate(center_a,axis_a,cross_u_a,cross_v_a,length_a_m,width_a_m,height_a_m,"segment A")
    b=_validate(center_b,axis_b,cross_u_b,cross_v_b,length_b_m,width_b_m,height_b_m,"segment B")
    ca,ta,ua,va=a
    cb,tb,ub,vb=b
    direction_dot=_dot(ta,tb)
    if abs(direction_dot)<1e-15: return 0.0
    nodes,weights=_gauss_legendre(order)

    def samples(center,axis,u,v,length,width,height):
        out=[]
        for i,n in enumerate(nodes):
            s=0.5*length*n
            ws=0.5*length*weights[i]
            for j,m in enumerate(nodes):
                x=0.5*width*m
                wx=0.5*weights[j]
                for k,p in enumerate(nodes):
                    y=0.5*height*p
                    wy=0.5*weights[k]
                    point=tuple(center[q]+axis[q]*s+u[q]*x+v[q]*y for q in range(3))
                    out.append((point,ws,wx*wy))
        return out

    pa=samples(ca,ta,ua,va,length_a_m,width_a_m,height_a_m)
    pb=samples(cb,tb,ub,vb,length_b_m,width_b_m,height_b_m)
    weighted=0.0
    scale=max(length_a_m,length_b_m,width_a_m,height_a_m,width_b_m,height_b_m)
    for ra,wa,sa in pa:
        for rb,wb,sb in pb:
            distance=math.sqrt(sum((ra[q]-rb[q])**2 for q in range(3)))
            if distance<=1e-15*scale:
                raise ArithmeticError("quadrature sampled coincident points; volumes may touch or overlap")
            weighted+=wa*wb*sa*sb/distance
    return MU0/(4.0*math.pi)*direction_dot*weighted
