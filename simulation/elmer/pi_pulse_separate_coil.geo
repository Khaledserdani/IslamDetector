// Axisymmetric PI detector surrogate: independent TX coil, air gap, conductive target.
// Coordinates are (r,z) in metres. TX coil and target are separate physical bodies.
SetFactory("OpenCASCADE");
Mesh.MshFileVersion = 2.2;
Mesh.ElementOrder = 1;
Mesh.CharacteristicLengthMin = 0.0025;
Mesh.CharacteristicLengthMax = 0.020;

// Set IncludeTarget=0 with gmsh -setnumber for the no-target control case.
If (!Exists(IncludeTarget))
  IncludeTarget = 1;
EndIf

// Outer air domain: r=0..0.50 m, z=-0.35..0.35 m.
Rectangle(1) = {0.0, -0.35, 0, 0.50, 0.70};
// Aluminium plate: 250 mm radius, 5 mm thick.
If (IncludeTarget)
  Rectangle(2) = {0.0, -0.020, 0, 0.25, 0.005};
EndIf
// DD32-equivalent TX winding cross-section, near 145 mm radius.
Rectangle(3) = {0.130, 0.030, 0, 0.030, 0.010};

// Fragment the air domain with two independent internal regions.
fragmentTools[] = {3};
If (IncludeTarget)
  fragmentTools[] += {2};
EndIf
out[] = BooleanFragments{ Surface{1}; Delete; }{ Surface{fragmentTools[]}; Delete; };

air[] = {};
tx[] = {};
target[] = {};
For i In {0:#out[]-1}
  s = out[i];
  c[] = CenterOfMass Surface{s};
  If (c[0] > 0.129 && c[0] < 0.161 && c[1] > 0.029 && c[1] < 0.041)
    tx[] += {s};
  ElseIf (c[0] >= -0.0001 && c[0] < 0.251 && c[1] > -0.021 && c[1] < -0.014)
    target[] += {s};
  Else
    air[] += {s};
  EndIf
EndFor

Physical Surface("Air", 1) = {air[]};
Physical Surface("TX_Coil", 2) = {tx[]};
If (IncludeTarget)
  Physical Surface("Aluminium_Target", 3) = {target[]};
EndIf

// Explicitly select the axis and far-field exterior curves.
// Bounding-box selectors avoid fragile per-curve bounding-box array calls.
Physical Curve("Axis", 11) = Curve In BoundingBox{-1e-8, -0.350001, -1e-8, 1e-8, 0.350001, 1e-8};
Physical Curve("Outer_Infinity", 12) = {
  Curve In BoundingBox{-1e-8, -0.350001, -1e-8, 0.500001, -0.349999, 1e-8},
  Curve In BoundingBox{0.499999, -0.350001, -1e-8, 0.500001, 0.350001, 1e-8},
  Curve In BoundingBox{-1e-8, 0.349999, -1e-8, 0.500001, 0.350001, 1e-8}
};

// Refine the coil and target while keeping the surrounding air economical.
Field[1] = Distance;
If (IncludeTarget)
  Field[1].SurfacesList = {tx[], target[]};
Else
  Field[1].SurfacesList = {tx[]};
EndIf
Field[2] = Threshold;
Field[2].InField = 1;
Field[2].SizeMin = 0.0025;
Field[2].SizeMax = 0.020;
Field[2].DistMin = 0.005;
Field[2].DistMax = 0.060;
Background Field = 2;
Mesh 2;
