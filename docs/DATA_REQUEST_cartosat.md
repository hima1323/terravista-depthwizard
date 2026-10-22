# Data request: Cartosat sample scene and CartoDEM for SIH26175 evaluation

**Status: draft, not sent.** Fill in the `[...]` placeholders and send it from the team leader's institute e-mail.

**To:**
- the SIH26175 problem-statement owner (ISRO), via the SIH portal query channel / SPOC contact `[PS owner contact]`;
- copy to NRSC Bhoonidhi user support `[Bhoonidhi support e-mail, from https://bhoonidhi.nrsc.gov.in contact page]`.

**Subject:** SIH 2026, PS SIH26175 (team TerraVista_iitrpr, `[Team ID]`): request for one Cartosat sample scene +
CartoDEM v3 R1 tile for evaluation

---

Dear Sir / Madam,

We are team **TerraVista_iitrpr** (`[Team ID]`) from IIT Ropar, working on Smart India Hackathon 2026 problem statement
**SIH26175, "Single-View Height Estimation and 3D Flythrough"** (Disaster Management).

**What we have built.** Our prototype, DepthWizard, estimates the height of every pixel from one optical image. It
builds an absolute DSM on a 30 m DEM and checks the result against NASA ICESat-2 and GEDI laser data. So far we have
tested it on airborne imagery (GAMUS, USA), on high-resolution satellite tiles (Overhead Geopose Challenge, Atlanta / Buenos Aires),
and on commercial basemap imagery of eight Indian sites.

**What we have not been able to test.** We have not yet run it on ISRO imagery, or compared it with CartoDEM. Both
need a login that we do not have for this purpose.

**Our request.** We would be grateful for one sample scene for the evaluation, over an area where we already have
results: **Karol Bagh, New Delhi** (scene centre about 28.6484° N, 77.1789° E, extent about 0.6 × 0.6 km). This site
has 7 ICESat-2 laser passes and OpenStreetMap building footprints, so the evaluation can keep its levelling and
validation laser data separate.

We will use the data **only for evaluation within SIH 2026**. We will not redistribute it or commit it to any public
repository, and we will delete it after the hackathon if you ask. Results will be reported with credit to NRSC / ISRO.

If this request should go through a different channel, we would be thankful if you could point us to it.

Thank you for your time.

Yours sincerely,
`[Name]`, Team Leader, TerraVista_iitrpr (`[Team ID]`)
`[Department]`, Indian Institute of Technology Ropar
`[e-mail]` · `[phone]`
Faculty mentor: `[Name, e-mail]`

---

## Specifics (for the e-mail or the request form)

- **Imagery.** One Cartosat-3 PAN + MX scene, or if that is not possible a Cartosat-2 series (2S/2E/2F) PAN + MX
  scene, covering 28.6460–28.6508° N, 77.1762–77.1817° E (Karol Bagh, New Delhi).
  - **Product:** standard orthorectified or georeferenced product, the bundle with PAN and MX bands. A pan-sharpened
    product is also fine.
  - **Date:** cloud-free, ideally 2024–2026, to stay close to our laser data (2019–2026).
- **CartoDEM.** CartoDEM v3 R1, the 1-degree tile N28E077, with the vertical datum stated (we assume EGM96).
- **Format.** GeoTIFF, with the RPC or metadata file, the sensor and acquisition date-time, and the sun and view
  angles.
- **Use.** Accuracy evaluation for SIH26175 only, non-commercial, no redistribution. Credit to NRSC / ISRO in all
  results.
- **What we will report back.** Height-above-ground and DSM error against ICESat-2 / GEDI on held-out laser passes, and
  CartoDEM against Copernicus GLO-30 and FABDEM at the same laser points. We will share the report with the PS owner.

## After the data arrives (for the team)

- **CartoDEM tile:** unzip it into `SynRS3D/demo/benchmark/v2/scenes/cartodem/`, then rerun
  `demo/india_eval_v2.py evaluate` and `demo/dtm_compare.py evaluate`. It is picked up as baseline `cartodem`, and
  EGM96 is shifted to EGM2008 automatically.
- **Cartosat scene:** process it in the app as a GeoTIFF. Then add it as a scene in `demo/india_eval_v2.py`, next to
  `delhi_karol_bagh`, so both images are checked against the same laser points.
- **Licence:** do not commit either file (NRSC data policy).
