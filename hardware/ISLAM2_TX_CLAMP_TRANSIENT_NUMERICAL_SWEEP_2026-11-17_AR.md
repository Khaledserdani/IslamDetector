# ISLAM2 TX transient clamp sweep — numerical bench model
Date: 2026-11-17
Branch: hardware/islam-nextgen-final-platform

## Scope and honesty
This is a numerical time-domain integration of the lumped RL coil equations using SciPy solve_ivp. It is **not an ngspice run**, not a measured hardware result, and not a validated semiconductor-level SPICE model. The local Debian environment had no ngspice binary; apt installation did not complete within the available execution window. The official ngspice manual describes transient analysis and device-model requirements: https://ngspice.sourceforge.io/docs.html and https://ngspice.sourceforge.io/modelparams.html.

## Model
- Supply: 12 V ideal
- Coil: L = 180 uH, R = 1.5 ohm (series lumped resistance)
- MOSFET: ideal switch, on-state drop ignored
- Turn-on: 0 V drain idealized
- Turn-off: ideal TVS clamp holds drain at an assumed constant Vclamp while coil current is positive
- TVS sweep: 36.7 V and 53.3 V (scenario values, **not** a fitted 5KP33A I-V model)
- Pulse widths: 50, 75, 100 us
- Repetition period not used in the single-pulse transient calculation.

During ON:
L di/dt = Vs - R i
During OFF while clamp conducts:
L di/dt = Vs - R i - Vclamp
The off integration stops when current reaches zero. TVS energy is integral((Vclamp - Vs)*i dt); copper off-loss is integral(R*i^2 dt).

## Results
| Ton (us) | Ipeak (A) | Coil energy at turn-off (mJ) | Vclamp scenario (V) | Decay to zero (us) | TVS energy (mJ) | Coil copper loss during decay (mJ) |
|---:|---:|---:|---:|---:|---:|---:|
| 50 | 2.7261 | 0.6688 | 36.7 | 18.383 | 0.6031 | 0.0657 |
| 50 | 2.7261 | 0.6688 | 53.3 | 11.329 | 0.6277 | 0.0411 |
| 75 | 3.7179 | 1.2441 | 36.7 | 24.430 | 1.0837 | 0.1604 |
| 75 | 3.7179 | 1.2441 | 53.3 | 15.199 | 1.1423 | 0.1018 |
| 100 | 4.5232 | 1.8414 | 36.7 | 29.124 | 1.5612 | 0.2802 |
| 100 | 4.5232 | 1.8414 | 53.3 | 18.253 | 1.6617 | 0.1797 |

Numerical energy balance closes to < 1e-8 mJ for each row: initial magnetic energy = TVS dissipation + copper loss during decay.

## Interpretation
1. The higher assumed clamp voltage shortens current decay, but increases the drain-voltage stress.
2. At 50 us, this ideal model predicts 2.73 A peak; at 100 us it predicts 4.52 A.
3. The 53.3 V scenario is below the 100 V nominal MOSFET rating on paper, but that is not a safe-operating conclusion: real TVS clamp voltage depends on current and temperature, and layout inductance adds overshoot. The MOSFET must be checked against measured VDS peak and repetitive avalanche/SOA limits.
4. The clamp energy is about 0.60–1.66 mJ per pulse in these scenarios. At 10 Hz this is low average power, but pulse current, package thermal impedance, and actual TVS dynamic resistance still require verification.

## What this model omits
- Real STP110N10F7 MOSFET gate charge, switching transitions, Coss, RDS(on), reverse recovery and SOA.
- Real 5KP33A vendor SPICE model and dynamic resistance.
- Coil self-capacitance, lead inductance, PCB loop inductance, parasitic ringing and EMI.
- Driver UCC27511A output impedance and gate resistors.
- Temperature dependence and component tolerances.
- RX protection, blanking, recovery and target response.

## Engineering disposition
Keep 50 us / 10 Hz / current-limited supply as the **first low-energy bench starting point only**, not as a final operating setting. Do not raise pulse width or repetition rate until VDS, VGS, coil current and component temperature are captured on the bench. Next simulation must use vendor models for the MOSFET and TVS, then include parasitic L/C and the shared-coil RX protection path.
