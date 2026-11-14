// Axisymmetric PI detector surrogate: independent TX coil, air gap, conductive target.
// Coordinates are (r,z) in metres. TX coil and target are separate physical bodies.
SetFactory("OpenCASCADE");
Mesh.MshFileVersion = 2.2;
Mesh.ElementOrder = 1;
Mesh.CharacteristicLengthMin = 0.00025;
Mesh.CharacteristicLengthMax = 0.020;

// Local target/coil refinement control for the mesh-convergence study.
If (!Exists(MeshRefinementDivisions))
  MeshRefinementDivisions = 3;
EndIf
If (MeshRefinementDivisions < 2)
  Error("MeshRefinementDivisions must be >= 2");
EndIf

// Set IncludeTarget=0 for the no-target control. TargetGap is measured from
// the lower face of the TX winding (z=30 mm) to the target upper face.
If (!Exists(IncludeTarget))
  IncludeTarget = 1;
EndIf
If (!Exists(TargetGap))
  TargetGap = 0.045;
EndIf
TargetTop = 0.030 - TargetGap;
// Outer air domain: r=0..0.50 m, z=-0.35..0.35 m.
Rectangle(1) = {0.0, -0.35, 0, 0.50, 0.70};
// Parametric axisymmetric target cross-section.
// Default remains the legacy 250 mm-radius, 5 mm-thick aluminium foil surrogate.
// A coin is a solid disk (inner radius 0); a ring is an annular rectangle.
If (!Exists(TargetInnerRadiusM))
  TargetInnerRadiusM = 0.0;
EndIf
If (!Exists(TargetRadialWidthM))
  TargetRadialWidthM = 0.250;
EndIf
If (!Exists(TargetThicknessM))
  TargetThicknessM = 0.005;
EndIf
TargetBottom = TargetTop - TargetThicknessM;
If (IncludeTarget)
  Rectangle(2) = {TargetInnerRadiusM, TargetBottom, 0, TargetRadialWidthM, TargetThicknessM};
EndIf
// Parameterized axisymmetric TX winding pack. Sweep changes radius only;
// radial width, height, turn count and current density remain fixed.
If (!Exists(CoilInnerRadiusM))
  CoilInnerRadiusM = 0.130;
EndIf
If (!Exists(CoilRadialWidthM))
  CoilRadialWidthM = 0.030;
EndIf
Rectangle(3) = {CoilInnerRadiusM, 0.030, 0, CoilRadialWidthM, 0.010};

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
  If (c[0] > (CoilInnerRadiusM - 0.001) && c[0] < (CoilInnerRadiusM + CoilRadialWidthM + 0.001) && c[1] > 0.029 && c[1] < 0.041)
    tx[] += {s};
  ElseIf (c[0] >= (TargetInnerRadiusM - 0.001) && c[0] < (TargetInnerRadiusM + TargetRadialWidthM + 0.001) && c[1] > (TargetBottom - 0.001) && c[1] < (TargetTop + 0.001))
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
Field[2].SizeMin = TargetThicknessM / MeshRefinementDivisions;
Field[2].SizeMax = 0.020;
Field[2].DistMin = 0.005; // resolve thin coin/ring sections with local target-scale elements
Field[2].DistMax = 0.060;
Background Field = 2;
Mesh 2;
