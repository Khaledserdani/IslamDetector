// ISLAM LAB GetDP cross-check: transient PI pulse over an aluminium target.
// Axisymmetric (r,z) model. The TX is a stranded winding pack; target is massive conductor.
// Formulation follows the official GetDP 4 magneto-quasistatic tutorial.
Group {
  Air = Region[1];
  Coil = Region[2];
  AluminiumTarget = Region[3];
  Axis = Region[11];
  Outer = Region[12];

  Vol_Mag = Region[{Air, Coil, AluminiumTarget}];
  Vol_S_Mag = Region[Coil];
  Vol_C_Mag = Region[AluminiumTarget];
  Sur_Neu_Mag = Region[{}];
}
Function {
  mu0 = 4.e-7 * Pi;
  nu0 = 1 / mu0;
  nu[Region[{Air, Coil, AluminiumTarget}]] = nu0;
  sigma[AluminiumTarget] = 3.5e7;

  // 20 turns x 1 A peak distributed over 30 mm x 10 mm.
  // Smooth PI-like current: rises near 50 us and falls near 150 us.
  js[Coil] = Vector[0, 0,
    3.333333333e4 * (Tanh[($Time - 50.e-6)/5.e-6]
                    - Tanh[($Time - 150.e-6)/5.e-6])];
}
Constraint {
  { Name a_Mag;
    Case {
      { Region Axis; Value 0.; }
      { Region Outer; Value 0.; }
    }
  }
}
Group {
  Dom_Hcurl_a = Region[{Vol_Mag, Sur_Neu_Mag}];
}
FunctionSpace {
  { Name Hcurl_a; Type Form1P;
    BasisFunction {
      { Name se; NameOfCoef ae; Function BF_PerpendicularEdge;
        Support Dom_Hcurl_a; Entity NodesOf[All]; }
    }
    Constraint {
      { NameOfCoef ae; EntityType NodesOf; NameOfConstraint a_Mag; }
    }
  }
}
Jacobian {
  { Name Vol;
    Case {
      { Region All; Jacobian VolAxi; }
    }
  }
}
Integration {
  { Name Int;
    Case {
      { Type Gauss;
        Case {
          { GeoElement Triangle; NumberOfPoints 3; }
        }
      }
    }
  }
}
Formulation {
  { Name Magnetoquasistatics_a; Type FemEquation;
    Quantity {
      { Name a; Type Local; NameOfSpace Hcurl_a; }
    }
    Equation {
      Integral { [nu[] * Dof{d a}, {d a}];
        In Vol_Mag; Jacobian Vol; Integration Int; }
      Integral { DtDof[sigma[] * Dof{a}, {a}];
        In Vol_C_Mag; Jacobian Vol; Integration Int; }
      Integral { [-js[], {a}];
        In Vol_S_Mag; Jacobian Vol; Integration Int; }
    }
  }
}
Resolution {
  { Name Mag;
    System {
      { Name Sys_Mag; NameOfFormulation Magnetoquasistatics_a; }
    }
    Operation {
      InitSolution[Sys_Mag];
      TimeLoopTheta[0, 400.e-6, 1.e-6, 1] {
        Generate[Sys_Mag]; Solve[Sys_Mag]; SaveSolution[Sys_Mag];
      }
    }
  }
}
PostProcessing {
  { Name Mag; NameOfFormulation Magnetoquasistatics_a;
    Quantity {
      { Name a;
        Value { Term {[{a}]; In Vol_Mag; Jacobian Vol;} }
      }
      { Name b;
        Value { Term {[{d a}]; In Vol_Mag; Jacobian Vol;} }
      }
      { Name j;
        Value {
          Term {[-sigma[] * Dt[{a}]]; In Vol_C_Mag; Jacobian Vol;}
          Term {[js[]]; In Vol_S_Mag; Jacobian Vol;}
        }
      }
      // Integral of |J|^2 over the aluminium volume, evaluated at each time step.
      { Name J2;
        Value {
          Integral {[sigma[] * sigma[] * SquNorm[Dt[{a}]]];
            In Vol_C_Mag; Jacobian Vol; Integration Int;}
        }
      }
    }
  }
}
PostOperation {
  { Name Map; NameOfPostProcessing Mag;
    Operation {
      Print[b, OnElementsOf Vol_Mag, File "b.pos"];
      Print[j, OnElementsOf Vol_C_Mag, File "j_target.pos"];
      Print[J2[Vol_C_Mag], OnGlobal, Format Table, File "j2.txt"];
    }
  }
}
