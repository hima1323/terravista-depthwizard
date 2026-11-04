"""Build TerraVista_DepthWizard_SIH2026_v4.pptx from v3 (v3 stays untouched): align the deck with the system that is
built and measured (plan step 1). Same shapes, new text; every number is read from the JSON named in docs/CLAIMS.md
(claim IDs in the comments), the four charts get measured data, and the speaker notes are rewritten.

What changes: model = RS3DAda with released weights (no fine-tuning); DINOv3/CHMv2 challenger, ONNX, Tauri, Sat3DGen are
'planned, not built'; DFC2019 is not shown as zero-shot; the flood CSI is a scenario test; one 'not yet validated' line.
usage: ../SynRS3D/.venv/bin/python build_v4.py [--selftest]
"""
import copy, json, os, sys

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.join(HERE, '..', 'SynRS3D', 'demo', 'benchmark')
V2 = os.path.join(B, 'v2')
SRC, OUT = os.path.join(HERE, 'TerraVista_DepthWizard_SIH2026_v3.pptx'), os.path.join(HERE, 'TerraVista_DepthWizard_SIH2026_v4.pptx')
BLUE, TEAL, GREEN, ORANGE, GREY, INK = '2068AA', '228989', '45885C', 'D2742D', '5C6878', '17273A'
MAX_BULLETS, MAX_CHARS = 5, 90          # DepthWizard_Deck_Spec.md section 0, rule 5
rgb = RGBColor.from_string
J = lambda *p: json.load(open(os.path.join(*p)))


def numbers():
    """Every number the deck shows, straight from the JSON files (docs/CLAIMS.md ids)."""
    g, geo = J(V2, 'gamus_v2.json')['v2'], J(V2, 'geopose_v2.json')
    ind, unc = J(V2, 'india_v2.json')['aggregate']['all_scenes'], J(V2, 'uncertainty_calibration.json')
    guard, e2e, recal = J(V2, 'dtm_guard_summary.json'), J(V2, 'integrate_e2e.json'), J(V2, 'recal_gamus.json')
    m = lambda d: d['mae']['mean']
    n = dict(
        g_mae=g['overall']['tta']['mae'], g_zero=m(g['overall']['zero_baseline']),                       # G1, G2
        g_bld=g['buildings']['tta']['mae'], g_bld_zero=m(g['buildings']['zero_baseline']),               # G8
        g_cls={k: (m(g['per_group'][f'class: {k}']['tta']), m(g['per_group'][f'class: {k}']['zero_baseline']))
               for k in ('buildings', 'trees', 'road', 'ground')},                                        # G10
        g_bias1020=g['height_bins']['10-20 m']['tta']['bias']['mean'],                                  # G7
        g_sp=g['uncertainty_spearman'], tta_gain=g['tta_minus_single_mae']['mean'],                      # U1, M2
        geo={c: dict(ours=geo['cities'][c]['official_exact_fp32']['whole_mae'], **geo['published_fig7'][c])
             for c in ('ATL', 'ARG')},                                                                    # A1, A2
        geo_ci={c: geo['cities'][c]['official_exact_fp32']['ci95'] for c in ('ATL', 'ARG')},
        ind={k: m(ind[k]) for k in ('b.is2_seg.ours.fp98', 'b.is2_seg.zero.fp98', 'b.gedi.ours.fp98', 'b.gedi.zero.fp98',
                                    'c.gedi_top.ours_none.fp98', 'c.gedi_top.glo30.fp98', 'c.is2_all.ours_none.fp',
                                    'c.is2_all.glo30.fp')},                                               # I1, I2, I8, I9
        ind_units={k: ind[k]['units'] for k in ('b.is2_seg.ours.fp98', 'b.gedi.ours.fp98')},
        cov={c: {b: unc['building']['symmetric'][c]['test']['0.9']['by']['reference height bin'][b]['coverage'] * 100
                 for b in ('3-10 m', '10-20 m', '20-inf m')} for c in ('DC', 'NYC', 'PHL')},              # U5
        cov_all={c: unc['building']['symmetric'][c]['test']['0.9']['coverage'] * 100 for c in ('DC', 'NYC', 'PHL')},  # U4
        india_cov=recal['india']['interval_coverage'],                                                    # U6
        guard_is2=guard['sets']['dtm.is2val']['all']['after']['mean'],                                    # I5
        e2e_s=e2e['process_s'], recal_ship=recal['ship'],                                                 # M4, R1
    )
    n['flood'] = flood_csi()                                                                              # F1
    return n


def flood_csi():
    """Pooled CSI per terrain over the flood-test windows with ICESat-2 ground photons (as demo/flood_test.py reports)."""
    firsts = [next(iter(v['layers'].items())) for v in J(B, 'flood_test.json').values()]
    rs = [e for lab, e in firsts if lab.startswith('IPH flood extent') and 'ours + ICESat-2' in e]
    csi = lambda t: (lambda tp, fp, fn: tp / (tp + fp + fn))(*(sum(e[t][k] for e in rs) for k in ('tp', 'fp', 'fn')))
    return {'scenes': len(rs), **{t: csi(t) for t in ('raw GLO-30', 'ours', 'FABDEM', 'ours + ICESat-2')}}


def shape(slide, sid):
    return next(s for s in slide.shapes if s.shape_id == sid)


def set_lines(sh, lines, italic_idx=()):
    """Replace a text frame's paragraphs, keeping the first run's formatting (font, size, bold, colour)."""
    body = sh.text_frame._txBody
    paras = body.findall(qn('a:p'))
    tmpl = next((p for p in paras if p.findall(qn('a:r'))), paras[0])
    for p in paras:
        body.remove(p)
    for i, line in enumerate(lines):
        p = copy.deepcopy(tmpl)
        for tag in ('a:br', 'a:fld'):
            for e in p.findall(qn(tag)):
                p.remove(e)
        runs = p.findall(qn('a:r'))
        for r in runs[1:]:
            p.remove(r)
        runs[0].find(qn('a:t')).text = line
        rpr = runs[0].get_or_add_rPr()
        if i in italic_idx:
            rpr.set('i', '1')
        elif rpr.get('i') == '1':
            rpr.set('i', '0')
        body.append(p)
    sh.text_frame.word_wrap = True


def txt(slide, sid, *lines, italic_idx=(), limit=MAX_CHARS):
    """Card text: at most 5 bullets of at most 90 chars; full-width strips (footer lines) pass a larger limit."""
    assert len(lines) <= MAX_BULLETS, (sid, len(lines))
    for l in lines:
        assert len(l) <= limit, (sid, len(l), l)
    set_lines(shape(slide, sid), list(lines), italic_idx)


def notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text


def rechart(slide, sid, title, cats, series, colors, fmt='0.0', vmax=None, major=None, point_colors=()):
    """New data in an existing chart shape (keeps its place and size); title, colours, labels and axis set explicitly.
    No legend: Keynote draws legends over the axis labels, so the title names the series colours instead."""
    ch = shape(slide, sid).chart
    cd = CategoryChartData(number_format=fmt)
    cd.categories = cats
    for name, vals in series:
        cd.add_series(name, [round(v, 2) for v in vals])
    ch.replace_data(cd)
    ch.chart_title.text_frame.text = title
    f = ch.chart_title.text_frame.paragraphs[0].runs[0].font
    f.size, f.bold, f.color.rgb = Pt(10), True, rgb(INK)
    plot = ch.plots[0]
    for i, (s, col) in enumerate(zip(plot.series, colors)):
        s.format.fill.solid()
        s.format.fill.fore_color.rgb = rgb(col)
        if i == 0:   # per-point colours from v3 would survive replace_data; clear them
            for dpt in s._element.findall(qn('c:dPt')):
                s._element.remove(dpt)
    plot.has_data_labels = True
    dl = plot.data_labels
    dl.font.size, dl.number_format, dl.number_format_is_linked = Pt(8), fmt, False
    va = ch.value_axis
    va.minimum_scale = 0
    if vmax:
        va.maximum_scale = vmax
    if major:
        va.major_unit = major
    va.tick_labels.number_format, va.tick_labels.number_format_is_linked = '0' if (major or 1) >= 1 else '0.0', False
    va.tick_labels.font.size = ch.category_axis.tick_labels.font.size = Pt(8)
    for i, col in enumerate(point_colors):
        pt = plot.series[0].points[i]
        pt.format.fill.solid()
        pt.format.fill.fore_color.rgb = rgb(col)
    ch.has_legend = False
    return ch


def build(n):
    prs = Presentation(SRC)
    s1, s2, s3, s4, s5, s6 = prs.slides
    G, geo, ind, fl, cov = n['g_mae'], n['geo'], n['ind'], n['flood'], n['cov']
    ci = lambda d: f"{d['mean']:.2f} m [{d['ci95'][0]:.2f}, {d['ci95'][1]:.2f}]"

    # ---- slide 2: idea
    txt(s2, 15362, 'DepthWizard: One Satellite Image → 3D Heights You Can Fly Through and Check')
    txt(s2, 15376, 'Cleaned 30 m DEM + ICESat-2 → metres')
    txt(s2, 15381, 'Held-out laser check + click-to-measure')
    txt(s2, 15390,
        '✓ One optical image in: no stereo pair, LiDAR or InSAR needed',
        '✓ PNG/JPG → relative DSM · GeoTIFF → absolute DSM in metres',
        '✓ Upload → auto-process → fly through the reconstructed 3D terrain',
        '✓ Click any building: height with a 90% interval (too narrow above 10 m)',
        '✓ Working prototype: runs offline on an 8 GB laptop; GeoTIFF + GLB export')
    txt(s2, 15394,
        '• Published RS3DAda model: zero-shot on GAMUS, paper reproduced on ATL / ARG',
        f"• Numbers with a baseline or 95% CI: GAMUS MAE {G['mean']:.2f} m vs {n['g_zero']:.2f} m flat ground",
        '• Laser check that is not circular: ICESat-2 passes split into levelling / checking',
        '• Trust layer: 90% building interval (misses tall blocks) + consistency score',
        '• Disaster scenarios on top: flood depth, routes, relief sites, slope classes')
    for sid, t in [(15398, 'Remote-sensing height AI'), (15400, 'Real metres, laser-levelled'),
                   (15402, 'Checked vs LiDAR + 2 lasers'), (15404, "Bird's-eye → street flythrough")]:
        txt(s2, sid, t)
    notes(s2, 'One satellite image goes in and heights come out, and this works in our prototype today. The height model is '
              'RS3DAda, published at NeurIPS 2024; we run the released weights and have not fine-tuned it. For a GeoTIFF, '
              'the terrain comes from the free 30 m Copernicus model with buildings and trees removed using our heights, and '
              'it is levelled with NASA ICESat-2 laser points when at least two laser passes cross the scene. The user flies '
              'through the town and clicks a building to see its height with a 90% interval; we say on screen that the '
              'interval is too narrow for buildings over 10 m. Every accuracy number we show is listed in docs/CLAIMS.md with '
              'a baseline or published reference, and with a 95% confidence interval where it averages several tiles or '
              'scenes. GAMUS is our only zero-shot test; the Overhead Geopose cities were in the model\'s unlabelled '
              'adaptation data, so there we only check that we reproduce the paper.')

    # ---- slide 3: technical approach
    txt(s3, 17410, 'Pipeline: Pixels → Height → Metres → Checked 3D')
    txt(s3, 17424, 'RS3DAda (DINOv2 ViT-L + DPT), released weights')
    txt(s3, 17429, 'Height above ground + consistency score')
    txt(s3, 17434, 'GLO-30 terrain, buildings removed, laser-levelled')
    txt(s3, 17461, 'Held-out laser check + error report')
    narrow = dict(limit=54)   # slide 3 cards are 3.7 in wide: one line each at this font
    txt(s3, 17441,
        '✓ RS3DAda (NeurIPS 2024): released weights, no tuning',
        '✓ 4-flip TTA · blended 518 px tiles · 8 GB laptop',
        '✓ 90% building interval (split-conformal, GAMUS)',
        '✓ Zero-shot: GAMUS · paper reproduced: ATL / ARG',
        '• Planned: DINOv3 / CHMv2 challenger, ONNX CPU model', **narrow)
    txt(s3, 17445,
        '✓ Rasterio · PyProj; GeoTIFF in / out; EGM2008',
        '✓ DSM = terrain (GLO-30; CartoDEM drop-in) + height',
        '✓ ICESat-2 levelling needs 2+ passes; GEDI checks',
        '✓ Validate: raster, survey points, held-out laser',
        '• Planned: Cartosat + CartoDEM (data requested)', **narrow)
    txt(s3, 17449,
        '✓ Three.js viewer; GLB + GeoTIFF export',
        '✓ Free-fly (WASD), draw-a-path auto-fly, video export',
        '✓ Street-level camera · • Sat3DGen mesh (planned)',
        '✓ Click-to-measure; flood, route, relief-site tools',
        '✓ Offline laptop app (.bat) · • Tauri app (planned)', **narrow)
    txt(s3, 17450, '✓ working in our prototype today   • planned, not built   |   '
                   'every number: docs/CLAIMS.md, with its baseline or 95% CI', limit=130)
    rechart(s3, 17463, 'SCENARIO TEST: Porto Alegre 2024 flood (CSI)',
            ['Raw 30 m DEM\n(GLO-30)', '+ our building\nremoval', '+ ICESat-2\nlaser levelling', 'FABDEM\n(reference)'],
            [('CSI', [fl[t] for t in ('raw GLO-30', 'ours', 'ours + ICESat-2', 'FABDEM')])], [TEAL], fmt='0.00',
            vmax=1.0, major=0.5)
    txt(s3, 17464, f"Scenario test, not a forecast: pre-flood image, {fl['scenes']} windows (320 m) vs IPH-UFRGS "
                   'extent; levelled before the 2-pass rule.', limit=150)
    c = n['g_cls']
    rechart(s3, 17468, 'GAMUS MAE per tile (m): ours blue, flat ground grey', ['Buildings', 'Trees', 'Road', 'Ground'],
            [('Ours', [c[k][0] for k in ('buildings', 'trees', 'road', 'ground')]),
             ('Flat ground (0 m)', [c[k][1] for k in ('buildings', 'trees', 'road', 'ground')])],
            [BLUE, GREY], fmt='0.00', vmax=12, major=4)
    txt(s3, 17469, f"150 GAMUS tiles (aerial 0.33 m, zero-shot): MAE {ci(G)} vs {n['g_zero']:.2f} flat ground. "
                   'Leafless trees; tall objects too low.', limit=150)
    notes(s3, 'Ticks mark what works in our prototype; bullets are planned and not built. The model is RS3DAda with its '
              'released weights: we did not fine-tune it, and the DINOv3 / CHMv2 challenger, the ONNX model and the Tauri '
              'app are plans. Left chart: a scenario test on the May 2024 Porto Alegre flood. From the pre-flood image we '
              f"flooded the terrain to the gauge level in {fl['scenes']} small windows that have laser data and compared "
              f"with the IPH-UFRGS flood extent: raw 30 m DEM CSI {fl['raw GLO-30']:.2f}, with our building removal "
              f"{fl['ours']:.2f}, after ICESat-2 levelling {fl['ours + ICESat-2']:.2f}; FABDEM scores {fl['FABDEM']:.2f}. "
              'It is a spot check, not a forecast, and it was run before we stopped levelling from a single laser pass, '
              'which would now skip one of the four windows. Right chart: GAMUS, the dataset the PS recommends; it is '
              f"aerial imagery at 0.33 m, not satellite. On 150 tiles our mean MAE is {ci(G)}, against "
              f"{n['g_zero']:.2f} m for predicting flat ground everywhere. On open ground predicting zero is still better; "
              f"trees, mostly leafless in these photos, and tall buildings read too low (bias {n['g_bias1020']:.1f} m for "
              '10 to 20 m objects).')

    # ---- slide 4: feasibility
    txt(s4, 17410, 'Built on a Released Model, Free Data and Offline-Ready Software')
    txt(s4, 17414,
        f"• Working today: released RS3DAda end to end, {n['e2e_s']:.0f} s for a test scene on an 8 GB laptop",
        '• Test data in hand: GAMUS, Overhead Geopose ATL / ARG, 8 Indian laser scenes',
        '• Free terrain + truth data: Copernicus GLO-30, ICESat-2, GEDI, OpenStreetMap',
        '• Not yet: Cartosat + CartoDEM (login-gated; request drafted to PS owner / NRSC)')
    txt(s4, 17418,
        '• Modular: swap the height model without touching calibration or the viewer',
        '• Standard outputs: GeoTIFF DSM with the input CRS, GLB 3D mesh, building JSON',
        '• Offline today on a laptop (.bat launcher); ONNX model + Tauri app planned',
        '• Licences: code MIT / Apache; weights trained on CC BY-NC data; FABDEM checks only')
    txt(s4, 17431, 'Read GSD from metadata · resampling tested (no gain): kept native')
    txt(s4, 17437, 'Remove buildings from terrain · ICESat-2 levelling only from 2+ passes')
    txt(s4, 17443, f"Report bias by height ({n['g_bias1020']:.1f} m at 10–20 m) · recalibration tried, not shipped")
    txt(s4, 17449, 'Planned: off-nadir test set + warning in UI (not built)')
    txt(s4, 17455, 'Offline laptop app with CPU fallback (built) · ONNX model planned')
    bars = [(f'{c}: {lab}', geo[c][k]) for c in ('ATL', 'ARG') for lab, k in
            (('source-only', 'source_only'), ('paper', 'RS3DAda'), ('ours', 'ours'))]
    for sid in (17460, 17461):   # Keynote draws bar-chart category labels left of the frame: keep them off the table
        sh = shape(s4, sid)
        sh.left, sh.width = Inches(9.1), Inches(3.55)
    rechart(s4, 17460, 'MEASURED: published RS3DAda reproduced (MAE, m)', [b[0] for b in bars],
            [('MAE', [b[1] for b in bars])], [BLUE], fmt='0.00', vmax=9, major=3,
            point_colors=[GREY, BLUE, GREEN] * 2)
    a, r = n['geo_ci']['ATL'], n['geo_ci']['ARG']
    txt(s4, 17461, f"Geopose satellite tiles, 300 per city; adaptation domain, not zero-shot. 95% CI: ATL [{a[0]:.2f}, {a[1]:.2f}], "
                   f"ARG [{r[0]:.2f}, {r[1]:.2f}] m. Source-only, paper: published.", limit=150)
    notes(s4, 'Everything we depend on is public: the model weights, GAMUS, Overhead Geopose, the Copernicus elevation model, '
              'ICESat-2 and GEDI. The chart checks that we run the model correctly: on 300 satellite test tiles per city '
              'from the Overhead Geopose challenge (cities whose unlabelled images the model adapted to, so this is a '
              f"reproduction, not a zero-shot test) our MAE is {geo['ATL']['ours']:.2f} m in Atlanta and "
              f"{geo['ARG']['ours']:.2f} m in Buenos Aires, against {geo['ATL']['RS3DAda']:.2f} and "
              f"{geo['ARG']['RS3DAda']:.2f} published; both published values are inside our 95% intervals. The risks we "
              'measured: tall buildings read too low on every test set, and an isotonic correction made one held-out city '
              'worse, so we did not ship it. Resampling the input to another resolution gave no gain. We have not yet run '
              'on Cartosat or compared with CartoDEM; both need a login, and we have drafted a data request.')

    # ---- slide 5: impact
    txt(s5, 17413, 'Checked 3D from one image')
    txt(s5, 17417, 'Flood-depth scenarios · slope classes · affected buildings · routes, relief sites',
        f"Scenario test, Porto Alegre 2024: CSI {fl['ours + ICESat-2']:.2f} in {fl['scenes']} laser-levelled windows",
        italic_idx=(1,))
    txt(s5, 17421, f"Building heights (GAMUS: MAE {n['g_bld']['mean']:.2f} m on 1,450 buildings) · 3D base maps")
    txt(s5, 17425, 'More value from optical archives · next: test on Cartosat + CartoDEM')
    txt(s5, 17429, 'Fly-through + street-level view for briefings · offline routes and relief sites')
    txt(s5, 17442, 'Terrain and slope context for flood and landslide planning')
    txt(s5, 17443, 'ONE SATELLITE IMAGE → CHECKED 3D → FASTER DECISIONS')
    txt(s5, 17455, 'CHECKED 3D')
    notes(s5, 'In our Porto Alegre scenario test, starting from pre-flood images, the flood map matched the IPH-UFRGS flood '
              f"extent with CSI {fl['ours + ICESat-2']:.2f} in the {fl['scenes']} small windows that had laser data; it is "
              'a scenario check, not a forecast, and the levelling predates our two-pass rule. Planners get building heights where no LiDAR exists: on GAMUS, building '
              f"heights are off by {n['g_bld']['mean']:.2f} m on average, against {n['g_bld_zero']:.2f} m for "
              'assuming flat ground. ISRO would get more value from existing optical images; the next step is to run on '
              'Cartosat, which we have requested.')

    # ---- slide 6: research and references
    txt(s6, 17410, 'Research Foundation: Published Model, Open Data, Independent Laser Checks')
    txt(s6, 17414,
        '• RS3DAda: Song et al., NeurIPS 2024 (the model we run, released weights)',
        '• Split-conformal: Angelopoulos & Bates 2021 (90% building interval)',
        '• FABDEM: Hawker et al. 2022 (bare-earth DEM, used for checks)',
        '• Roof photons in ICESat-2: Cai et al. 2024 (OSM footprints mask roofs)',
        '• Reviewed, not built: DINOv3 / CHMv2, Prompt2DEM, Sat3DGen')
    txt(s6, 17418,
        '• GAMUS (PS-recommended; aerial 0.33 m) · Overhead Geopose ATL / ARG',
        '• Copernicus GLO-30 · FABDEM · CartoDEM (requested from NRSC)',
        '• NASA ICESat-2 ATL03 / ATL08 · GEDI L2A · OpenStreetMap buildings',
        '• IPH-UFRGS 2024 flood map · DFC2019 (adaptation domain, not zero-shot)',
        '• Metrics: MAE, RMSE, bias, NMAD, r on nDSM; 95% CI over tiles / scenes')
    txt(s6, 17419, 'Not yet validated: Cartosat / CartoDEM, leaf-on canopy, intervals for tall buildings, '
                   'floor counts, GCP accuracy, processing time', limit=130)
    for sid, t in [(17427, 'RS3DAda (DINOv2)'), (17430, 'GAMUS + Geopose'), (17433, 'GLO-30 / FABDEM'),
                   (17436, 'ICESat-2 + GEDI')]:
        txt(s6, sid, t)
    keys = [('b.is2_seg.ours.fp98', 'b.is2_seg.zero.fp98'), ('b.gedi.ours.fp98', 'b.gedi.zero.fp98'),
            ('c.gedi_top.ours_none.fp98', 'c.gedi_top.glo30.fp98'), ('c.is2_all.ours_none.fp', 'c.is2_all.glo30.fp')]
    rechart(s6, 17440, 'MEASURED: Indian scenes vs NASA lasers (8; GEDI 7), MAE (m): ours blue, baseline grey',
            ['Height vs\nICESat-2', 'Height vs\nGEDI', 'DSM vs\nGEDI tops', 'DSM vs\nICESat-2'],
            [('Ours', [ind[o] for o, _ in keys]), ('Baseline', [ind[b] for _, b in keys])],
            [BLUE, GREY], fmt='0.00', vmax=20, major=5)
    txt(s6, 17441, 'Baseline: height 0 (left two) or raw Copernicus DSM (right two). Ours loses on the last one.', limit=115)
    rechart(s6, 17442, 'MEASURED: 90% interval coverage, held-out city (%): DC blue, NYC teal, PHL orange',
            ['LiDAR 3–10 m', 'LiDAR 10–20 m', 'LiDAR > 20 m'],
            [(c, [cov[c][b] for b in ('3-10 m', '10-20 m', '20-inf m')]) for c in ('DC', 'NYC', 'PHL')],
            [BLUE, TEAL, ORANGE], fmt='0.0', vmax=100, major=50)
    txt(s6, 17443, 'GAMUS LiDAR, leave-one-city-out, 959 blocks. Target 90%: met for low blocks, missed for tall ones.', limit=115)
    nd = n['ind_units']
    notes(s6, 'Every method here is published and cited, and both charts are our own measurements. Left: eight Indian scenes '
              'against NASA lasers, with laser passes split so that nothing is checked on the photons used for levelling. '
              f"Our heights above ground are off by {ind['b.is2_seg.ours.fp98']:.2f} m against ICESat-2 "
              f"({nd['b.is2_seg.ours.fp98']} scenes) where assuming no height gives {ind['b.is2_seg.zero.fp98']:.2f} m, "
              f"and {ind['b.gedi.ours.fp98']:.2f} against {ind['b.gedi.zero.fp98']:.2f} m with GEDI ({nd['b.gedi.ours.fp98']} scenes). Our absolute DSM beats "
              f"the raw Copernicus DSM against GEDI canopy and roof tops ({ind['c.gedi_top.ours_none.fp98']:.2f} vs "
              f"{ind['c.gedi_top.glo30.fp98']:.2f} m) but not against all ICESat-2 photons "
              f"({ind['c.is2_all.ours_none.fp']:.2f} vs {ind['c.is2_all.glo30.fp']:.2f} m). Right: the 90% interval we "
              'show on each building, tested on a city it was not calibrated on. It covers low buildings almost always, but '
              f"only {cov['NYC']['10-20 m']:.0f} to {cov['DC']['10-20 m']:.0f}% of 10 to 20 m blocks in New York and "
              'Washington and fewer above 20 m, which is why the viewer warns about tall buildings. Not yet validated: '
              'Cartosat and CartoDEM, leaf-on canopy, floor counts, ground-control-point accuracy and processing time.')
    prs.save(OUT)
    return prs


def check(prs):
    """No banned claim left anywhere on the slides or in the notes; bullet rules hold on every edited card."""
    banned = ['DINOv3-SAT +', 'GAMUS-tuned', 'GAMUS fine-tun', 'Fine-tuning fits', 'no non-commercial', 'DFC2019 test tiles',
              'Measured 3D', 'Rank correlation', 'zero-shot on 3', 'per city, zero-shot', 'uncertainty map', 'viewshed', 'Distilled', 'Tauri desktop app']
    for i, s in enumerate(prs.slides, 1):
        text = ' '.join(sh.text_frame.text for sh in s.shapes if sh.has_text_frame) + ' ' + s.notes_slide.notes_text_frame.text
        text += ' '.join(sh.chart.chart_title.text_frame.text for sh in s.shapes if sh.has_chart)
        for b in banned:
            assert b not in text, (i, b)
    return True


if __name__ == '__main__':
    if '--selftest' in sys.argv:   # offline: helpers on a synthetic slide, then the banned-phrase check on v3 must fail
        p = Presentation()
        sl = p.slides.add_slide(p.slide_layouts[5])
        tb = sl.shapes.add_textbox(0, 0, 100, 100)
        tb.text_frame.text = 'old'
        set_lines(tb, ['a', 'b'], italic_idx=(1,))
        assert [q.text for q in tb.text_frame.paragraphs] == ['a', 'b'] and tb.text_frame.paragraphs[1].runs[0].font.italic
        try:
            txt(sl, tb.shape_id, 'x' * (MAX_CHARS + 1)); raise SystemExit('length rule not enforced')
        except AssertionError:
            pass
        try:
            check(Presentation(SRC)); raise SystemExit('banned-claim check passed on v3')
        except AssertionError:
            pass
        assert abs(flood_csi()['ours + ICESat-2'] - 0.79) < 0.005
        print('selftest ok')
    else:
        n = numbers()
        check(build(n))
        print('wrote', OUT)
