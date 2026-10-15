"""Build TerraVista_DepthWizard_SIH2026_v2.pptx from v1.pptx following DepthWizard_Deck_Spec.md.

If ../SynRS3D/demo/benchmark/results.json exists, slide 6's TARGET chart becomes the measured DFC19 result.
usage: ../SynRS3D/.venv/bin/python build_v2.py
"""
import copy, json, math, os

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

HERE = os.path.dirname(os.path.abspath(__file__))
BENCH = os.path.join(HERE, '..', 'SynRS3D', 'demo', 'benchmark', 'results.json')
CORR = os.path.join(HERE, '..', 'SynRS3D', 'demo', 'benchmark', 'correction.json')
CHOSEN = os.path.join(HERE, '..', 'SynRS3D', 'demo', 'benchmark', 'height_correction_chosen.json')
BLUE, TEAL, GREEN, ORANGE, GREY, INK = '2068AA', '228989', '45885C', 'D2742D', '5C6878', '17273A'
rgb = RGBColor.from_string

prs = Presentation(os.path.join(HERE, 'v1.pptx'))
S = list(prs.slides)


def pick_correction():
    """The shipped correction (demo/height_correction.py decides: it must help in every split), or None."""
    if not (os.path.exists(CORR) and os.path.exists(CHOSEN)):
        return None
    res = json.load(open(CORR))['results']
    m = json.load(open(CHOSEN))['variant']
    cross = '; '.join(f"{k.split(' (')[0]} {r['raw']['whole_mae']:.2f}→{r[m]['whole_mae']:.2f} m"
                      for k, r in res.items() if 'other city' in k)
    return {'method': m, 'result': res['both cities -> both cities'], 'cross': cross}

def shape(slide, sid):
    return next(s for s in slide.shapes if s.shape_id == sid)


def set_lines(sh, lines, size=None, italic_idx=()):
    """Replace a text frame's paragraphs, keeping the first run's formatting (font, bold, colour)."""
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
        if size:
            rpr.set('sz', str(int(size * 100)))
        if i in italic_idx:
            rpr.set('i', '1')
            rpr.set('b', '0')
        body.append(p)
    sh.text_frame.word_wrap = True


def txt(slide, sid, *lines, size=None, italic_idx=()):
    set_lines(shape(slide, sid), list(lines), size, italic_idx)


def move(sh, x=None, y=None, w=None, h=None):
    if x is not None: sh.left = Inches(x)
    if y is not None: sh.top = Inches(y)
    if w is not None: sh.width = Inches(w)
    if h is not None: sh.height = Inches(h)


def clone(sh):
    el = copy.deepcopy(sh._element)
    ids = [int(e.get('id')) for e in sh._element.getparent().iter() if e.tag == qn('p:cNvPr')]
    el.find('.//' + qn('p:cNvPr')).set('id', str(max(ids) + 1))
    sh._element.addnext(el)
    return next(s for s in sh._parent if s._element is el)


def remove(slide, sh):
    rids = sh._element.xpath('.//c:chart/@r:id')
    sh._element.getparent().remove(sh._element)
    for rid in rids:
        slide.part.drop_rel(rid)


def source_line(slide, x, y, w, text):
    lines = math.ceil(len(text) / (w * 20))  # ~17.5 chars per inch at 8 pt
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(0.14 * lines + 0.04))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    r = tf.paragraphs[0].add_run()
    r.text = text
    r.font.size, r.font.name, r.font.color.rgb = Pt(8), 'Aptos', rgb(GREY)
    return 0.14 * lines + 0.06


def chart(slide, old, ctype, cats, series, title, colors, source, legend=False, point_colors=None,
          fmt='0.0', reverse=False, vmax=None, box=None, hide_axis=False):
    x, y, w, h = box or (old.left / 914400, old.top / 914400, old.width / 914400, old.height / 914400)
    if old is not None:
        remove(slide, old)
    src_h = math.ceil(len(source) / (w * 20)) * 0.14 + 0.06
    cd = CategoryChartData()
    cd.categories = cats
    for name, vals in series:
        cd.add_series(name, vals)
    ch = slide.shapes.add_chart(ctype, Inches(x), Inches(y), Inches(w), Inches(h - src_h), cd).chart
    ch.font.size, ch.font.name = Pt(8), 'Aptos'
    ch.has_title = True
    tf = ch.chart_title.text_frame
    tf.text = title
    f = tf.paragraphs[0].runs[0].font
    f.size, f.bold, f.color.rgb = Pt(10), True, rgb(INK)
    ch.has_legend = legend
    if legend:
        ch.legend.position, ch.legend.include_in_layout = XL_LEGEND_POSITION.TOP, False
        ch.legend.font.size = Pt(8)
    plot = ch.plots[0]
    plot.gap_width = 70
    plot.has_data_labels = True
    dl = plot.data_labels
    dl.font.size, dl.number_format, dl.number_format_is_linked = Pt(8), fmt, False
    dl.position = XL_LABEL_POSITION.OUTSIDE_END
    for s, col in zip(plot.series, colors):
        s.format.fill.solid()
        s.format.fill.fore_color.rgb = rgb(col)
    for i, col in enumerate(point_colors or []):
        pt = plot.series[0].points[i]
        pt.format.fill.solid()
        pt.format.fill.fore_color.rgb = rgb(col)
    va, ca = ch.value_axis, ch.category_axis
    va.tick_labels.font.size = ca.tick_labels.font.size = Pt(8)
    va.has_major_gridlines = True
    va.major_gridlines.format.line.color.rgb = rgb('D5DCE7')
    va.format.line.fill.background()
    if vmax:
        va.maximum_scale = vmax
    va.minimum_scale = 0
    ca.reverse_order = reverse
    if hide_axis:  # small charts: data labels carry the values
        va.visible = False
        va.has_major_gridlines = False
    source_line(slide, x, y + h - src_h + 0.02, w, source)


# ---------------------------------------------------------------- slide 2
s = S[1]
txt(s, 15362, 'DepthWizard: One Satellite Image → Measured 3D Heights You Can Fly Through and Verify')
for hid, bid, head, body in [(15365, 15366, 'INPUT', 'PNG / JPG / TIFF / GeoTIFF'),
                             (15370, 15371, 'AI HEIGHT', 'Height above ground, every pixel'),
                             (15375, 15376, 'CALIBRATE', 'CartoDEM-guided real metres'),
                             (15380, 15381, 'VERIFY', 'ICESat-2 laser check + click-to-measure'),
                             (15385, 15386, 'FLY & ACT', '3D flythrough + flood / slope tools')]:
    txt(s, hid, head)
    txt(s, bid, body)
txt(s, 15388, 'HOW IT MEETS THE PROBLEM STATEMENT')
txt(s, 15390, '✓ One optical image in: no stereo pair, LiDAR or InSAR needed',
    '✓ PNG/JPG → relative DSM · GeoTIFF → absolute DSM in metres',
    '✓ Upload → auto-process → fly through the reconstructed 3D terrain',
    '✓ Click any building: estimated height ± uncertainty vs reference',
    '✓ Complete suite: web app + offline desktop app, source code, docs')
txt(s, 15392, 'WHY DEPTHWIZARD IS DIFFERENT')
txt(s, 15394, '• Satellite-trained height model; generic depth AI fails on top-down images',
    '• Two accuracy boosters: CartoDEM calibration + ICESat-2 laser correction',
    '• Trust layer: per-pixel uncertainty + live error report in the viewer',
    "• Bird's-eye → street-level view in one click (Sat3DGen)",
    '• Disaster tools on top: flood depth, landslide slopes, affected buildings')
for sid, t in [(15398, 'Satellite-native height AI'), (15400, 'Real metres from CartoDEM'),
               (15402, 'Laser-verified (ICESat-2)'), (15404, "Bird's-eye → street flythrough")]:
    txt(s, sid, t)

# ---------------------------------------------------------------- slide 3
s = S[2]
txt(s, 17410, 'Pipeline: Pixels → Height → Metres → Verified 3D')
boxes = [[shape(s, i) for i in ids] for ids in
         [(17411, 17412, 17413, 17414), (17416, 17417, 17418, 17419), (17421, 17422, 17423, 17424),
          (17426, 17427, 17428, 17429), (17431, 17432, 17433, 17434)]]
boxes.append([clone(sh) for sh in boxes[-1]])  # 6th box: VERIFY
boxes[-1][1].fill.solid()
boxes[-1][1].fill.fore_color.rgb = rgb(ORANGE)
arrows = [shape(s, i) for i in (17415, 17420, 17425, 17430)]
arrows.append(clone(arrows[-1]))
BW, GAP, X0 = 1.64, 0.24, 0.65
content = [('INPUT', 'RGB image (PNG / JPG / TIFF)'),
           ('PREPROCESS', 'Read GSD + CRS · overlapping 518 px tiles'),
           ('AI MODEL', 'RS3DAda (ViT-L + DPT) · challenger: DINOv3-SAT'),
           ('HEIGHT', 'Height above ground + uncertainty map'),
           ('CALIBRATE', 'CartoDEM / SRTM prior → metres (Prompt2DEM)'),
           ('VERIFY', 'ICESat-2 correction + error report')]
for i, ((bg, hdr, htb, btb), (head, body)) in enumerate(zip(boxes, content)):
    x = X0 + i * (BW + GAP)
    move(bg, x, 1.75, BW, 1.0)
    move(hdr, x, 1.75, BW, 0.29)
    move(htb, x + 0.05, 1.78, BW - 0.1, 0.23)
    move(btb, x + 0.05, 2.08, BW - 0.1, 0.62)
    set_lines(htb, [head])
    set_lines(btb, [body], size=10)
    if i < 5:
        move(arrows[i], x + BW + 0.01, 2.11, GAP - 0.02, 0.26)
move(shape(s, 17437), 11.70, 2.11, 0.24, 0.26)
move(shape(s, 17435), 11.95, 1.75, 0.68, 1.0)
move(shape(s, 17436), 11.98, 2.05, 0.62, 0.4)

for (bg, hr, ht, bd), x, w in [((17438, 17439, 17440, 17441), 0.65, 3.90),
                                ((17442, 17443, 17444, 17445), 4.82, 3.90),
                                ((17446, 17447, 17448, 17449), 8.99, 3.64)]:
    move(shape(s, bg), x, 2.88, w, 1.52)
    move(shape(s, hr), x, 2.88, w, 0.33)
    move(shape(s, ht), x + 0.1, 2.91, w - 0.2, 0.27)
    b = shape(s, bd)
    move(b, x + 0.12, 3.27, w - 0.24, 1.10)
    b.text_frame.auto_size = MSO_AUTO_SIZE.NONE
    b.text_frame.vertical_anchor = MSO_ANCHOR.TOP
txt(s, 17441, '• RS3DAda (NeurIPS 2024, MIT): released weights',
    '• Challenger: DINOv3-SAT + DPT (CHMv2 init), GAMUS-tuned',
    '• Keep the winner on the GAMUS test set (MAE / RMSE)',
    '• TTA → uncertainty map · Gaussian tile blending',
    '• Distilled small model → ONNX Runtime on CPU', size=10)
txt(s, 17445, '• GDAL · Rasterio · PyProj; GeoTIFF float32 in / out',
    '• DSM = terrain (CartoDEM / SRTM / GLO-30) + height',
    '• Prompt2DEM (2025): 30 m DEM + RGB → 30 cm heights',
    '• ICESat-2 ATL03 / ATL08: correct bias + report RMSE',
    '• One vertical datum (ICESat-2 is ellipsoidal)', size=10)
txt(s, 17448, 'APPLICATION & 3D VIEWER')
txt(s, 17449, '• React + Three.js viewer; GLB mesh + terrain tiles',
    '• Free-fly (WASD), draw-a-path auto-fly, MP4 export',
    '• Street mode: Sat3DGen (ICLR 2026) street mesh',
    '• Click-to-measure: height ± uncertainty anywhere',
    '• FastAPI + CLI; Tauri desktop app, fully offline', size=10)
txt(s, 17450, 'Built for both halves of the score: DSM accuracy (RMSE / MAE by terrain) + Rendering & UX '
              '(flythrough, measuring, offline)')

chart(s, shape(s, 17455), XL_CHART_TYPE.COLUMN_CLUSTERED,
      ['Prompt2DEM vs SRTM\n(vegetated, up to)', 'ICESat-2 fix\non RS3DAda', 'ICESat-2 fix on\nDepth Anything V2'],
      [('MAE reduction (%)', (18, 30.9, 24.1))], 'Published: calibration cuts error (MAE %)', [TEAL],
      'Rafaeli et al., arXiv 2507.09681 (2025) · Song et al., ISPRS J. P&RS vol. 232 (2026)', vmax=36,
      box=(0.65, 4.50, 3.85, 1.88), hide_axis=True)
chart(s, shape(s, 17456), XL_CHART_TYPE.COLUMN_CLUSTERED,
      ['Depth Anything V2\n(zero-shot)', 'VGGT', 'Satellite-fine-tuned\n(Sat3R)'],
      [('MAE (m)', (4.59, 4.11, 2.82))], 'Published: generic AI vs satellite AI (MAE, m)',
      [ORANGE], 'Sat3R, arXiv 2605.07264 (2026): DFC2019 multi-view benchmark', point_colors=[ORANGE, ORANGE, GREEN],
      fmt='0.00', vmax=5.3, box=(4.72, 4.50, 3.85, 1.88), hide_axis=True)
chart(s, shape(s, 17457), XL_CHART_TYPE.COLUMN_CLUSTERED, ['Bare', 'Urban', 'Vegetated'],
      [('MAE', (2.13, 2.38, 4.65)), ('RMSE', (2.70, 3.26, 5.93))], 'Published: error depends on terrain (m)',
      [BLUE, ORANGE], 'Prompt2DEM, arXiv 2507.09681 (2025) → we report accuracy per terrain type', legend=True,
      fmt='0.00', vmax=6.9, box=(8.79, 4.50, 3.85, 1.88), hide_axis=True)

# ---------------------------------------------------------------- slide 4
s = S[3]
txt(s, 17410, 'Built on Released Models, Free Data and Offline-Ready Software')
txt(s, 17414, '• Working baseline on day 1: RS3DAda weights + inference script are public (MIT)',
    '• Training data ready: GAMUS (PS-recommended), DFC2019/US3D, SynRS3D (69k synthetic images)',
    '• Free terrain + truth data: CartoDEM (Bhuvan), SRTM, Copernicus GLO-30, ICESat-2',
    '• Fine-tuning fits one cloud GPU; frozen-backbone option for low budgets')
txt(s, 17418, '• Modular: swap the height model without touching calibration or the viewer',
    '• Standard outputs (GeoTIFF DSM, GLB) open in QGIS, ArcGIS and Bhuvan workflows',
    '• Offline: distilled ONNX model + Tauri desktop app + bundled demo data',
    '• License-clean: MIT / Apache / DINOv3 license; no non-commercial weights')
rows = [('New image resolution (GSD)', 'Wrong height scale', 'Read GSD from metadata · resample · multi-resolution fine-tuning'),
        ("One image can't see ground level", 'Heights off in metres', 'CartoDEM-guided calibration + ICESat-2 correction'),
        ('Few tall buildings in training data', 'Tall buildings under-estimated', 'Oversample tall buildings · report error by height band'),
        ('Tilted (off-nadir) images', 'Leaning buildings, shifted roofs', 'Off-nadir training data (US3D) · warning in UI'),
        ('No GPU / no internet in the field', 'Tool unusable', 'ONNX CPU model · offline desktop app')]
row_ids = [(17427, 17429, 17431), (17433, 17435, 17437), (17439, 17441, 17443), (17445, 17447, 17449), (17451, 17453, 17455)]
for ids, texts in zip(row_ids, rows):
    for sid, t in zip(ids, texts):
        sh = shape(s, sid)
        set_lines(sh, [t], size=9.5)
        sh.top -= Inches(0.03)
chart(s, shape(s, 17460), XL_CHART_TYPE.BAR_CLUSTERED,
      ['RS3DAda', 'DINOv3-SAT + GAMUS fine-tune', 'TerraHeight-S', 'BuildMamba (no weights yet)',
       'Depth2Elevation (no code)', 'HTC-DC Net', 'CHMv2 as-is (trees only)'],
      [('Score', (9, 8.5, 7.5, 6.5, 6, 5.5, 3))], 'Model shortlist (team assessment, /10)', [BLUE],
      'Score = fit to PS + public weights + reported accuracy + effort. Multi-view models (need several images) excluded.',
      reverse=True, vmax=10)

# ---------------------------------------------------------------- slide 5
s = S[4]
txt(s, 17410, 'From One Image to Faster, Verifiable Disaster Decisions')
txt(s, 17412, 'DEPTHWIZARD')
txt(s, 17413, 'Measured 3D from one image')
txt(s, 17417, 'Flood-depth simulation · landslide-prone slopes · affected-building counts',
    'Example: raise water to 3 m → see which buildings go under', italic_idx=(1,))
txt(s, 17421, 'Building heights and volumes · 3D base maps where no LiDAR exists')
txt(s, 17424, 'REMOTE SENSING (ISRO)')
txt(s, 17425, 'More value from existing optical archives · fresh 3D from every new image, no stereo tasking')
txt(s, 17428, 'FIELD RESPONSE')
txt(s, 17429, 'Fly-through + street view for team briefings · line-of-sight / viewshed for relief staging')
for a, b, c in [(17451, 17452, ('HEIGHT MAP', 'per pixel')), (17455, 17456, ('VERIFIED 3D', 'metres + ICESat-2')),
                (17459, 17460, ('DECISION', 'flood / slope'))]:
    txt(s, a, c[0])
    txt(s, b, c[1])
txt(s, 17464, 'One optical image → measured, checked terrain context')
txt(s, 17436, 'Reuse existing images instead of new LiDAR/stereo surveys for every event')
txt(s, 17439, 'Faster 3D damage picture; works offline in the field')
txt(s, 17442, 'Terrain, slope and canopy context for flood, landslide and forest monitoring')
txt(s, 17443, 'ONE SATELLITE IMAGE → VERIFIED 3D → FASTER DECISIONS')

# ---------------------------------------------------------------- slide 6
s = S[5]
txt(s, 17410, 'Research Foundation: 2024–2026 Models, Open Data, Independent Validation')
txt(s, 17414, '• RS3DAda / SynRS3D: Song et al., NeurIPS 2024 (primary model)',
    '• DINOv3 (Meta, 2025) + CHMv2 (Scientific Data, 2026): satellite backbone',
    '• Prompt2DEM: Rafaeli et al., 2025, SRTM-prior metric heights (30 m → 30 cm)',
    '• ICESat-2-guided correction: Song, Chen & Yokoya, ISPRS J. 2026',
    '• Sat3DGen (ICLR 2026) · Benchmarks: BuildMamba 2026, Depth2Elevation (TGRS 2025), HTC-DC Net')
txt(s, 17418, '• GAMUS (recommended in PS) · DFC2019 / US3D · SynRS3D',
    '• CartoDEM (ISRO Bhuvan) · SRTM 30 m · Copernicus DEM GLO-30',
    '• ICESat-2 ATL03 / ATL08 (NASA Earthdata)',
    '• ISRO Bhoonidhi / Bhuvan imagery · ISPRS Potsdam / Vaihingen',
    '• Metrics: RMSE and MAE per terrain type and per height band')
for sid, t in [(17427, 'RS3DAda + DINOv3'), (17430, 'GAMUS + SynRS3D'),
               (17433, 'CartoDEM / SRTM / GLO-30'), (17436, 'RMSE / MAE + ICESat-2')]:
    txt(s, sid, t)
old6 = shape(s, 17440)
box6 = (0.65, 3.72, 11.98, 1.45)
measured = json.load(open(BENCH)) if os.path.exists(BENCH) else None
corr = pick_correction()
if measured:
    a = measured['ALL']
    off = a['tta']['whole']
    remove(s, old6)  # two measured charts share the old chart's area
    remove(s, shape(s, 17424))  # decorative 'EVIDENCE → DATA → …' header; the chain boxes say the same
    if corr:
        r = corr['result']
        bands = ['0-3 m', '3-10 m', '10-20 m', '20-inf m']
        chart(s, None, XL_CHART_TYPE.COLUMN_CLUSTERED, ['0–3 m', '3–10 m', '10–20 m', '> 20 m'],
              [('Raw model', [r['raw']['bands'][b]['mae'] for b in bands]),
               ('With learned correction', [r[corr['method']]['bands'][b]['mae'] for b in bands])],
              'MEASURED: error by true height (MAE, m), raw vs corrected', [BLUE, TEAL],
              f"Our run, {measured['tiles']} DFC2019 test tiles vs LiDAR. Official MAE {r['raw']['whole_mae']:.2f} → "
              f"{r[corr['method']]['whole_mae']:.2f} m; correction learned on separate training tiles "
              f"(other-city test: {corr['cross']}).",
              legend=True, fmt='0.0', box=(0.65, 3.70, 5.9, 1.85), hide_axis=True)
    else:
        lc = a['by_land_cover']
        groups = [('Buildings', lc['buildings']), ('Trees', lc['trees']), ('Ground', lc['ground']), ('Water', lc['water'])]
        chart(s, None, XL_CHART_TYPE.COLUMN_CLUSTERED, [g for g, _ in groups],
              [('MAE (m)', [v['mae'] for _, v in groups]), ('RMSE (m)', [v['rmse'] for _, v in groups])],
              'MEASURED: RS3DAda error vs LiDAR by land cover (m)', [BLUE, ORANGE],
              f"Our run: released RS3DAda, {measured['tiles']} DFC2019 test tiles (Jacksonville + Omaha). "
              f"Official metric MAE {off['mae']:.2f} m / RMSE {off['rmse']:.2f} m.",
              legend=True, fmt='0.00', box=(0.65, 3.70, 5.9, 1.85), hide_axis=True)
    q = a['error_by_uncertainty']
    labels = ['Lowest ±', 'Low ±', 'Middle ±', 'High ±', 'Highest ±']
    chart(s, None, XL_CHART_TYPE.COLUMN_CLUSTERED, [f"{l}\n{b['mean_unc']:.2f} m" for l, b in zip(labels, q)],
          [('Real MAE (m)', [b['mae'] for b in q])],
          'MEASURED: where our ± is high, real error is high (MAE, m)', [ORANGE],
          f"Same {measured['tiles']} test tiles; pixels split into 5 equal groups by predicted ± (spread of 4 "
          f"flipped predictions). Rank correlation {a['spearman_unc_vs_error']:.2f}.",
          fmt='0.00', box=(6.73, 3.70, 5.9, 1.85), hide_axis=True)
else:
    chart(s, old6, XL_CHART_TYPE.COLUMN_CLUSTERED, ['Flat urban', 'Dense urban', 'Vegetated', 'Hilly / mixed'],
          [('RMSE (m)', (1.9, 3.2, 4.1, 3.6)), ('MAE (m)', (1.2, 2.1, 2.8, 2.4))],
          'Our accuracy TARGETS by terrain (m), to be measured on GAMUS + ICESat-2', [ORANGE, BLUE],
          'Targets, not results. Published reference on GAMUS: Depth2Elevation MAE 1.99 m / RMSE 3.49 m',
          legend=True, box=box6)

# ---------------------------------------------------------------- notes
notes = [
    'We are TerraVista from IIT Ropar. Our idea, DepthWizard, answers SIH26175: single-view height estimation and 3D flythrough for disaster management.',
    'One satellite image goes in and measured heights come out. Example: we upload a GeoTIFF of a flooded town. The model estimates every building\'s height above ground. CartoDEM turns that into real elevation in metres, and ICESat-2 laser points check it. The user flies through the town, clicks a building and sees its height with an uncertainty range. PNG/JPG inputs give relative heights; GeoTIFF inputs give metres, as the PS asks.',
    'RS3DAda is our main model because it is released, trained for buildings and terrain, and a 2026 ISPRS study cut its error by about 31% with ICESat-2 correction. In parallel we fine-tune a DINOv3 satellite backbone on GAMUS and keep whichever scores better. Chart A: published gains from our two calibration stages. Prompt2DEM shows a coarse 30 m DEM plus a single image beats the DEM alone, by up to 18% MAE on vegetated terrain, which is the same idea as our CartoDEM step. Chart B: generic depth models do poorly on satellite images, which is why we use satellite-trained ones. Chart C: error changes with terrain, so we report accuracy per terrain type.',
    'Everything we depend on is already public: model weights, GAMUS, CartoDEM, ICESat-2. Our biggest risks are wrong scale and wrong ground level; calibration plus laser correction handles both. The desktop app runs offline on a CPU for field teams.',
    'Example: in the flood tool, raise the water to 3 m and the viewer highlights buildings below that level. Planners get building heights where no LiDAR exists, and ISRO gets more value from existing optical images.',
    (('Every method here is published and cited, and the charts are our own measurements. We ran the released RS3DAda '
      f"model on {measured['tiles']} DFC2019 test tiles and compared every pixel with LiDAR: MAE "
      f"{measured['ALL']['tta']['whole']['mae']:.2f} m, RMSE {measured['ALL']['tta']['whole']['rmse']:.2f} m. "
      'The right chart shows our uncertainty map is useful: where the ± is highest, the real error is about '
      f"{measured['ALL']['error_by_uncertainty'][-1]['mae'] / measured['ALL']['error_by_uncertainty'][0]['mae']:.0f}"
      ' times larger than where it is lowest, so the viewer can flag heights not to trust. '
      + (f"Tall buildings were under-estimated, so we learned a height correction on separate training tiles: MAE "
         f"{corr['result']['raw']['whole_mae']:.2f} to {corr['result'][corr['method']]['whole_mae']:.2f} m, and it also "
         f"helped when learned in one city and tested in the other ({corr['cross']}). "
         if corr else 'Tall buildings are under-estimated, by about 8 m above 20 m. A simple global correction learned on '
         'separate tiles did not fix that in our tests, so we will correct heights with local ICESat-2 laser measurements, '
         'as the 2026 ISPRS study did. ')
      + 'We will also repeat the measurement on GAMUS.')
     if measured else
     'Every method here is published and cited. The chart shows our targets, not results. We will replace it with measured GAMUS and ICESat-2 numbers once the benchmark runs.'),
]
for sl, n in zip(S, notes):
    sl.notes_slide.notes_text_frame.text = n

out = os.path.join(HERE, 'TerraVista_DepthWizard_SIH2026_v2.pptx')
prs.save(out)
print('saved', out, '| slide 6 chart:', 'MEASURED' if measured else 'TARGET')
