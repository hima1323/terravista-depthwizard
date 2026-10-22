# Flood test: May 2024 floods, Porto Alegre / Canoas (Brazil)

Flood = ground below the water level (bathtub, as in the web viewer), predicted from the **pre-flood** image (Maxar, 2 Feb 2024). Reference = IPH/UFRGS flood maps on 2010 LiDAR terrain. Everything ignores the flood walls and dikes (most failed or were overtopped). CSI = both wet / either wet (1 = perfect). Terrains: **raw GLO-30** (no model), **ours** = GLO-30 cleaned with our heights (what the app uses), **FABDEM** (GLO-30 with buildings/forest removed by a LiDAR-trained model; Hawker et al. 2022).

**Pooled over the Porto Alegre scenes (IPH 6 May extent, level 5.30 m) — CSI:** raw GLO-30 0.18, ours 0.47, FABDEM 0.48

**With the ICESat-2 bias correction** (the 4 of those scenes that have laser ground photons) — CSI: raw GLO-30 0.20, ours 0.30, FABDEM 0.32, ours + ICESat-2 0.79

| Scene | Reference | Level | Ref wet | Wet: raw / ours / FABDEM | CSI raw GLO-30 | CSI ours | CSI FABDEM | CSI ours + ICESat-2 | Best-fit level: ours / FABDEM | Our mean depth | Blocks sub/partly/dry |
|---|---|---|---|---|---|---|---|---|---|---|---|
| porto_alegre_centre | IPH flood extent, 6 May 2024 | 5.30 m | 100% | 5% / 8% / 7% | 0.05 | 0.08 | 0.07 | 0.54 | – / – m | 0.7 m | 0/5/4 |
| porto_alegre_centre | IPH LiDAR simulation, 5.0 m | 5.00 m | 98% | 4% / 5% / 6% | 0.04 | 0.05 | 0.06 | 0.50 | – / – m | 0.6 m | 0/5/4 |
| porto_alegre_centre | IPH LiDAR simulation, 5.5 m | 5.50 m | 100% | 7% / 10% / 8% | 0.07 | 0.10 | 0.08 | 0.55 | – / – m | 0.7 m | 1/4/4 |
| sarandi | IPH flood extent, 6 May 2024 | 5.30 m | 100% | 66% / 100% / 100% | 0.66 | 1.00 | 1.00 | 1.00 | – / – m | 0.9 m | 0/11/0 |
| sarandi | IPH LiDAR simulation, 5.0 m | 5.00 m | 100% | 53% / 98% / 100% | 0.53 | 0.98 | 1.00 | 1.00 | – / – m | 0.6 m | 0/11/0 |
| sarandi | IPH LiDAR simulation, 5.5 m | 5.50 m | 100% | 75% / 100% / 100% | 0.75 | 1.00 | 1.00 | 1.00 | – / – m | 1.1 m | 0/11/0 |
| poa_edge_p01-23 | IPH flood extent, 6 May 2024 | 5.30 m | 71% | 0% / 0% / 2% | 0.00 | 0.00 | 0.03 | 0.71 | 9.25 / 7.90 m | 0.0 m | 0/10/0 |
| poa_edge_p01-23 | IPH LiDAR simulation, 5.0 m | 5.00 m | 61% | 0% / 0% / 0% | 0.00 | 0.00 | 0.00 | 0.62 | 8.85 / 7.50 m | 0.0 m | 0/10/0 |
| poa_edge_p01-23 | IPH LiDAR simulation, 5.5 m | 5.50 m | 71% | 1% / 0% / 8% | 0.01 | 0.00 | 0.12 | 0.71 | 9.25 / 7.90 m | 0.0 m | 0/10/0 |
| poa_edge_p07-09 | IPH flood extent, 6 May 2024 | 5.30 m | 94% | 0% / 2% / 6% | 0.01 | 0.02 | 0.07 | 0.92 | 8.00 / 7.70 m | 0.2 m | 0/11/4 |
| poa_edge_p07-09 | IPH LiDAR simulation, 5.0 m | 5.00 m | 88% | 0% / 1% / 0% | 0.00 | 0.01 | 0.00 | 0.93 | 7.75 / 7.10 m | 0.1 m | 0/10/5 |
| poa_edge_p07-09 | IPH LiDAR simulation, 5.5 m | 5.50 m | 94% | 1% / 3% / 23% | 0.01 | 0.03 | 0.25 | 0.95 | 8.00 / 7.70 m | 0.3 m | 0/11/4 |
| poa_edge_p11-13 | IPH flood extent, 6 May 2024 | 5.30 m | 69% | 11% / 42% / 52% | 0.16 | 0.61 | 0.73 | – | 7.45 / 7.65 m | 0.6 m | 0/6/7 |
| poa_edge_p11-13 | IPH LiDAR simulation, 5.0 m | 5.00 m | 62% | 8% / 36% / 43% | 0.12 | 0.57 | 0.69 | – | 7.35 / 6.50 m | 0.4 m | 0/5/8 |
| poa_edge_p11-13 | IPH LiDAR simulation, 5.5 m | 5.50 m | 70% | 13% / 46% / 55% | 0.19 | 0.66 | 0.77 | – | 7.45 / 7.65 m | 0.8 m | 0/6/7 |
| poa_edge_p18-20 | IPH flood extent, 6 May 2024 | 5.30 m | 100% | 16% / 100% / 92% | 0.16 | 1.00 | 0.92 | – | – / – m | 1.9 m | 0/14/0 |
| poa_edge_p18-20 | IPH LiDAR simulation, 5.0 m | 5.00 m | 100% | 12% / 100% / 75% | 0.12 | 1.00 | 0.75 | – | – / – m | 1.6 m | 0/14/0 |
| poa_edge_p18-20 | IPH LiDAR simulation, 5.5 m | 5.50 m | 100% | 19% / 100% / 95% | 0.19 | 1.00 | 0.95 | – | – / – m | 2.1 m | 0/14/0 |
| canoas | IPH simulation, 5.0 m (metro, simplified) | 5.00 m | 100% | 98% / 100% / 100% | 0.98 | 1.00 | 1.00 | – | – / – m | 2.9 m | 0/16/0 |

**Surveyed flood-edge points** (IPH note, 5 May 2024, Guaíba 5.29 m): the ground there should equal the water level. Error = terrain − water level.

| Scene | Point | raw GLO-30 | ours | FABDEM | ours + ICESat-2 |
|---|---|---|---|---|---|
| porto_alegre_centre | 28 | +22.35 m | +2.78 m | +17.69 m | -0.70 m |
| poa_edge_p01-23 | 1 | +3.87 m | +2.73 m | +1.35 m | -1.28 m |
| poa_edge_p01-23 | 2 | +3.29 m | +2.31 m | +1.62 m | -1.71 m |
| poa_edge_p01-23 | 22 | +4.20 m | +2.02 m | +2.18 m | -1.99 m |
| poa_edge_p01-23 | 23 | +3.89 m | +2.71 m | +1.46 m | -1.31 m |
| poa_edge_p07-09 | 7 | +1.74 m | +0.23 m | +0.37 m | -1.96 m |
| poa_edge_p07-09 | 8 | +2.81 m | +0.67 m | +0.76 m | -1.52 m |
| poa_edge_p07-09 | 9 | +0.73 m | +1.29 m | +0.57 m | -0.90 m |
| poa_edge_p11-13 | 11 | +3.93 m | +1.86 m | +1.61 m | – |
| poa_edge_p11-13 | 12 | -0.61 m | -0.95 m | -0.53 m | – |
| poa_edge_p11-13 | 13 | -0.22 m | -0.74 m | -0.54 m | – |
| poa_edge_p18-20 | 18 | +2.17 m | -1.87 m | +0.12 m | – |
| poa_edge_p18-20 | 19 | +0.99 m | -1.37 m | -0.46 m | – |
| poa_edge_p18-20 | 20 | -1.45 m | -2.77 m | -0.56 m | – |
| **mean (mean abs), all 14 points** | | **+3.41 (3.73) m** | **+0.64 (1.74) m** | **+1.83 (2.13) m** | – |
| **mean (mean abs), the 8 points with laser data** | | **+5.36 (5.36) m** | **+1.84 (1.84) m** | **+3.25 (3.25) m** | **-1.42 (1.42) m** |

Scenes are 320 m × 320 m windows (four centred on surveyed edge points), so this is a spot check, not a city-wide score. Water levels are gauge readings, terrains are EGM2008; datums may differ by a few decimetres. The Canoas reference is IPH's simplified metro estimate.
