# Laser check: DepthWizard heights vs NASA ICESat-2

High-confidence ICESat-2 photons (ATL03, classified by ATL08) inside each scene, all passes since 2018, via the public SlideRule service. Heights converted to metres above mean sea level (EGM2008). Error = our value − laser. Median = bias, NMAD = robust spread.

| Scene | Photons (ground) | Passes | Terrain error before laser shift: ours, median / NMAD | Terrain error: raw GLO-30, median / NMAD | Laser shift applied by the app | Surface (DSM, after shift) error: median / NMAD | DSM within ±2 m |
|---|---|---|---|---|---|---|---|
| bengaluru electronic city | 2644 (850) | 4 | +0.08 / 0.74 m | +1.24 / 1.39 m | -0.08 m | +0.16 / 4.31 m | 40% |
| brazil poa edge p01-23 before | 1357 (347) | 2 | +4.02 / 0.28 m | +4.70 / 1.95 m | -4.02 m | -1.01 / 6.03 m | 29% |
| brazil poa edge p07-09 before | 1112 (396) | 3 | +2.19 / 0.44 m | +2.85 / 1.67 m | -2.19 m | +0.24 / 3.81 m | 42% |
| brazil porto alegre centre before | 1982 (831) | 8 | +3.48 / 3.38 m | +2.78 / 9.23 m | -3.48 m | +2.73 / 11.86 m | 19% |
| brazil sarandi before | 2872 (1342) | 7 | +1.03 / 0.92 m | +1.51 / 0.72 m | -1.03 m | +1.32 / 2.78 m | 46% |
| chandigarh sector17 | 576 (155) | 2 | +1.86 / 0.59 m | +2.81 / 3.30 m | -1.86 m | -2.80 / 4.34 m | 17% |
| delhi central | 886 (253) | 4 | +1.50 / 0.71 m | +2.18 / 1.37 m | -1.50 m | +1.74 / 4.69 m | 28% |
| iit ropar | 690 (487) | 1 | -1.61 / 0.39 m | -0.91 / 0.65 m | +1.61 m | +0.64 / 1.10 m | 79% |
| mumbai highrise | 978 (398) | 4 | +0.15 / 0.41 m | +4.82 / 3.71 m | -0.15 m | +0.74 / 6.68 m | 23% |
| shimla hill town | 182 (36) | 1 | -6.73 / 6.67 m | -1.73 / 3.98 m | – | -7.71 / 3.61 m | 13% |

No ICESat-2 photons inside: brazil canoas before, brazil poa edge p11-13 before, brazil poa edge p18-20 before, guwahati riverside (scenes are ~0.3–0.6 km wide; laser tracks are kilometres apart).

Footprints are ~11 m wide, so photons at roof edges and in trees mix heights; the median and NMAD are robust to that. ATL08 ground labels can be wrong in dense cities.
