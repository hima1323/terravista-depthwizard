"""Build the HS202 project report (A4 PDF) from report_template.html.

  python report/build_report.py            (needs weasyprint + pillow; fonts are fetched from Google Fonts)

Images come from DepthWizard_Report_Pack/images (not in git: it holds third-party imagery). They are downscaled into
report/build/img. Charts and diagrams are drawn here as SVG from the numbers in docs/CLAIMS.md (row IDs in comments).
The body word count (sections 2-14: headings, paragraphs and list items; tables, captions and figures excluded) is
written into the report itself.
"""
import html, math, os, re, sys
from html.parser import HTMLParser

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.join(HERE, '..', 'DepthWizard_Report_Pack', 'images')
BUILD = os.path.join(HERE, 'build')
OUT = os.path.join(HERE, 'DepthWizard_HS202_Report.pdf')

SAND, SAND_L, BLUE, INK, QUIET, GRID = '#8a6a4a', '#d9c7b2', '#3f6f94', '#2b2622', '#6f655c', '#e4dcd2'
SANS = "font-family='Montserrat, sans-serif'"


# ---------- images ----------
def prep_images():
    os.makedirs(os.path.join(BUILD, 'img'), exist_ok=True)
    for root, _, files in os.walk(PACK):
        for f in files:
            src = os.path.join(root, f)
            name, ext = os.path.splitext(f)
            charts = os.path.basename(root) == '3_results_charts' and f.startswith(('icesat2', 'uncertainty'))
            dst = os.path.join(BUILD, 'img', name + ('.png' if charts else '.jpg'))
            if os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src):
                continue
            im = Image.open(src)
            im.thumbnail((1800, 6000))
            if charts:
                im.save(dst, optimize=True)        # line plots stay PNG: sharp and small
            else:
                im.convert('RGB').save(dst, quality=84, optimize=True)


# ---------- charts (numbers from docs/CLAIMS.md) ----------
def chart_accuracy():
    # G1/G2, G8, A1, A2, I1, I5: MAE per tile or scene [95% CI] vs the baseline measured at the same points
    rows = [('GAMUS, all pixels', '150 aerial tiles vs airborne LiDAR', 3.90, 3.24, 4.66, 5.65, 'flat ground'),
            ('GAMUS, buildings', '1,450 buildings, 90th-percentile height', 3.57, 3.08, 4.06, 10.54, 'flat ground'),
            ('Overhead Geopose, Atlanta', '300 satellite tiles', 5.99, 5.57, 6.43, 5.67, 'published RS3DAda'),
            ('Overhead Geopose, Buenos Aires', '300 satellite tiles', 1.94, 1.86, 2.03, 2.01, 'published RS3DAda'),
            ('India, heights vs ICESat-2', '8 scenes, 2 per landscape', 4.85, 3.04, 6.69, 8.25, 'height 0'),
            ('India, terrain vs held-out ICESat-2', '5 scenes with 2+ laser passes', 3.73, 1.44, 6.69, 3.86, 'no levelling')]
    x0, w, vmax, rh, y0 = 236, 356, 11.0, 58, 46
    X = lambda v: x0 + v / vmax * w
    s = [f"<svg viewBox='0 0 700 {y0 + rh * len(rows) + 34}' xmlns='http://www.w3.org/2000/svg' {SANS} font-size='11'>"]
    s.append(f"<rect x='{x0}' y='8' width='12' height='10' fill='{BLUE}'/><text x='{x0 + 18}' y='17' fill='{INK}'>DepthWizard (95% CI)</text>")
    s.append(f"<rect x='{x0 + 170}' y='8' width='12' height='10' fill='{SAND_L}'/><text x='{x0 + 188}' y='17' fill='{INK}'>baseline at the same points</text>")
    for v in range(0, 12, 2):
        s.append(f"<line x1='{X(v):.1f}' x2='{X(v):.1f}' y1='{y0 - 8}' y2='{y0 + rh * len(rows)}' stroke='{GRID}'/>"
                 f"<text x='{X(v):.1f}' y='{y0 + rh * len(rows) + 16}' text-anchor='middle' fill='{QUIET}' font-size='10'>{v}</text>")
    s.append(f"<text x='{x0 + w / 2}' y='{y0 + rh * len(rows) + 30}' text-anchor='middle' fill='{QUIET}' font-size='10'>mean absolute error (m), lower is better</text>")
    for i, (name, sub, v, lo, hi, b, bname) in enumerate(rows):
        y = y0 + i * rh
        s.append(f"<text x='0' y='{y + 14}' fill='{INK}' font-weight='600'>{name}</text><text x='0' y='{y + 29}' fill='{QUIET}' font-size='9.5'>{sub}</text>")
        s.append(f"<rect x='{x0}' y='{y + 4}' width='{X(v) - x0:.1f}' height='14' fill='{BLUE}'/>"
                 f"<line x1='{X(lo):.1f}' x2='{X(hi):.1f}' y1='{y + 11}' y2='{y + 11}' stroke='{INK}' stroke-width='1.2'/>"
                 f"<line x1='{X(lo):.1f}' x2='{X(lo):.1f}' y1='{y + 6}' y2='{y + 16}' stroke='{INK}' stroke-width='1.2'/>"
                 f"<line x1='{X(hi):.1f}' x2='{X(hi):.1f}' y1='{y + 6}' y2='{y + 16}' stroke='{INK}' stroke-width='1.2'/>"
                 f"<text x='{max(X(hi), X(v)) + 6:.1f}' y='{y + 15}' fill='{INK}' font-weight='600'>{v:.2f}</text>")
        s.append(f"<rect x='{x0}' y='{y + 22}' width='{X(b) - x0:.1f}' height='12' fill='{SAND_L}'/>"
                 f"<text x='{X(b) + 6:.1f}' y='{y + 32}' fill='{QUIET}' font-size='10'>{b:.2f} {bname}</text>")
    s.append('</svg>')
    return ''.join(s)


def chart_flood():
    # F1: CSI of a bathtub flood from the pre-flood image vs the observed extent, 4 windows with ICESat-2 photons
    rows = [('Raw GLO-30 terrain', 0.20, False), ('Our cleaned terrain', 0.30, False),
            ('FABDEM', 0.32, False), ('Ours + ICESat-2 levelling', 0.79, True)]
    x0, w, rh, y0 = 190, 420, 30, 10
    s = [f"<svg viewBox='0 0 700 {y0 + rh * len(rows) + 30}' xmlns='http://www.w3.org/2000/svg' {SANS} font-size='11'>"]
    for v in (0, 0.25, 0.5, 0.75, 1.0):
        x = x0 + v * w
        s.append(f"<line x1='{x}' x2='{x}' y1='{y0 - 4}' y2='{y0 + rh * len(rows)}' stroke='{GRID}'/>"
                 f"<text x='{x}' y='{y0 + rh * len(rows) + 14}' text-anchor='middle' fill='{QUIET}' font-size='10'>{v:g}</text>")
    s.append(f"<text x='{x0 + w / 2}' y='{y0 + rh * len(rows) + 28}' text-anchor='middle' fill='{QUIET}' font-size='10'>critical success index (CSI), higher is better</text>")
    for i, (name, v, hot) in enumerate(rows):
        y = y0 + i * rh
        s.append(f"<text x='{x0 - 10}' y='{y + 15}' text-anchor='end' fill='{INK}'{' font-weight=\"600\"' if hot else ''}>{name}</text>"
                 f"<rect x='{x0}' y='{y + 4}' width='{v * w:.1f}' height='16' fill='{BLUE if hot else SAND_L}'/>"
                 f"<text x='{x0 + v * w + 6:.1f}' y='{y + 16}' fill='{INK}' font-weight='600'>{v:.2f}</text>")
    s.append('</svg>')
    return ''.join(s)


def chart_bias():
    # G7: bias per tile by LiDAR height bin, GAMUS 150
    rows = [('0–3 m', 0.65), ('3–10 m', -1.86), ('10–20 m', -7.62), ('above 20 m', -16.26)]
    x0, bw, gap, top, H = 110, 90, 50, 30, 220
    Y = lambda v: top + (2 - v) / 20 * H
    s = [f"<svg viewBox='0 0 700 {top + H + 40}' xmlns='http://www.w3.org/2000/svg' {SANS} font-size='11'>"]
    for v in (2, 0, -5, -10, -15, -18):
        s.append(f"<line x1='{x0 - 10}' x2='{x0 + 4 * (bw + gap)}' y1='{Y(v):.1f}' y2='{Y(v):.1f}' stroke='{INK if v == 0 else GRID}'/>"
                 f"<text x='{x0 - 16}' y='{Y(v) + 4:.1f}' text-anchor='end' fill='{QUIET}' font-size='10'>{v:+d} m</text>".replace('+0 m', '0 m'))
    s.append(f"<text x='{x0 - 60}' y='14' fill='{QUIET}' font-size='10'>bias (ours − LiDAR), per tile</text>")
    for i, (name, v) in enumerate(rows):
        x = x0 + 20 + i * (bw + gap)
        y1, y2 = sorted((Y(0), Y(v)))
        s.append(f"<rect x='{x}' y='{y1:.1f}' width='{bw}' height='{y2 - y1:.1f}' fill='{BLUE if v < -5 else SAND_L}'/>"
                 f"<text x='{x + bw / 2}' y='{(Y(v) + 14) if v < 0 else (Y(v) - 6):.1f}' text-anchor='middle' fill='{INK}' font-weight='600'>{v:+.2f}</text>"
                 f"<text x='{x + bw / 2}' y='{top + H + 30}' text-anchor='middle' fill='{INK}'>{name}</text>")
    s.append('</svg>')
    return ''.join(s)


# ---------- diagrams ----------
def _box(x, y, w, h, title, lines, hot=False, num=None):
    s = [f"<rect x='{x}' y='{y}' width='{w}' height='{h}' rx='8' fill='{'#e7eef4' if hot else '#ffffff'}' stroke='{BLUE if hot else SAND}' stroke-width='{1.8 if hot else 1.2}'/>"]
    if num is not None:
        s.append(f"<circle cx='{x + 16}' cy='{y + 17}' r='9' fill='{SAND}'/><text x='{x + 16}' y='{y + 21}' text-anchor='middle' fill='#fff' font-size='10' font-weight='600'>{num}</text>")
    tx = x + (32 if num is not None else w / 2)
    anchor = 'start' if num is not None else 'middle'
    s.append(f"<text x='{tx}' y='{y + 21}' text-anchor='{anchor}' fill='{INK}' font-weight='600' font-size='12.5'>{title}</text>")
    for k, ln in enumerate(lines):
        s.append(f"<text x='{x + 12}' y='{y + 40 + 14 * k}' fill='{QUIET}' font-size='10.5'>{html.escape(ln)}</text>")
    return ''.join(s)


def _arrow_defs():
    return (f"<defs><marker id='ah' viewBox='0 0 10 10' refX='9' refY='5' markerWidth='7' markerHeight='7' orient='auto'>"
            f"<path d='M0 0L10 5L0 10z' fill='{SAND}'/></marker></defs>")


def diagram_pipeline():
    W, H, gx = 154, 82, 22
    xs = [10 + i * (W + gx) for i in range(4)]
    rowA, rowB = 10, 140
    a = [('Input', ['PNG, JPG or GeoTIFF', 'one optical image']),
         ('Preprocess', ['518 px tiles, 50% overlap', 'Gaussian blending']),
         ('AI model', ['RS3DAda (DINOv2 + DPT)', '4-flip test-time aug.']),
         ('Height', ['height above ground', '+ 8-class land cover'])]
    b = [('Calibrate', ['GLO-30 minus roofs, ICESat-2', 'levelling, optional GCPs']),
         ('Verify', ['LiDAR, DSM, points or', 'ICESat-2: MAE, RMSE, r']),
         ('DSM + 3D', ['GeoTIFF and GLB export', 'three.js flythrough'])]
    s = [f"<svg viewBox='0 0 720 240' xmlns='http://www.w3.org/2000/svg' {SANS}>", _arrow_defs()]
    for i, (t, ln) in enumerate(a):
        s.append(_box(xs[i], rowA, W, H, t, ln, hot=(t == 'AI model'), num=i + 1))
        if i < 3:
            s.append(f"<line x1='{xs[i] + W}' y1='{rowA + H / 2}' x2='{xs[i + 1] - 2}' y2='{rowA + H / 2}' stroke='{SAND}' stroke-width='1.4' marker-end='url(#ah)'/>")
    order = [3, 2, 1]                       # row B runs right to left under boxes 4, 3, 2
    for k, (t, ln) in enumerate(b):
        x = xs[order[k]]
        s.append(_box(x, rowB, W, H, t, ln, hot=(t == 'DSM + 3D'), num=5 + k))
        if k < 2:
            s.append(f"<line x1='{x}' y1='{rowB + H / 2}' x2='{xs[order[k + 1]] + W + 2}' y2='{rowB + H / 2}' stroke='{SAND}' stroke-width='1.4' marker-end='url(#ah)'/>")
    s.append(f"<line x1='{xs[3] + W / 2}' y1='{rowA + H}' x2='{xs[3] + W / 2}' y2='{rowB - 2}' stroke='{SAND}' stroke-width='1.4' marker-end='url(#ah)'/>")
    s.append(f"<text x='{xs[3] + W / 2 - 8}' y='{rowA + H + 28}' text-anchor='end' fill='{QUIET}' font-size='10'>GeoTIFF, or PNG/JPG with GCPs</text>")
    s.append(f"<text x='{xs[0]}' y='{rowB + 30}' fill='{QUIET}' font-size='10.5'>PNG / JPG without control</text>"
             f"<text x='{xs[0]}' y='{rowB + 44}' fill='{QUIET}' font-size='10.5'>points stay relative:</text>"
             f"<text x='{xs[0]}' y='{rowB + 58}' fill='{QUIET}' font-size='10.5'>height above ground only.</text>")
    s.append('</svg>')
    return ''.join(s)


def diagram_cycle():
    cx, cy, r = 360, 170, 112
    nodes = [('Prepare', 'Before', ['landslide-prone slopes,', 'water-rise exposure'], cx, cy - r),
             ('Respond', 'During', ['flood scenario, rain and', 'river timeline, dry routes'], cx + r * 1.9, cy),
             ('Relief', 'Shelter', ['helipad and relief-camp', 'sites, capacity, access'], cx, cy + r),
             ('Assess', 'After', ['block-by-block', 'impact report'], cx - r * 1.9, cy)]
    W, H = 176, 74
    s = [f"<svg viewBox='0 0 720 340' xmlns='http://www.w3.org/2000/svg' {SANS}>", _arrow_defs()]
    s.append(f"<ellipse cx='{cx}' cy='{cy}' rx='{r * 1.9}' ry='{r}' fill='none' stroke='{SAND_L}' stroke-width='2' stroke-dasharray='5 5'/>")
    for t in (-math.pi / 4, math.pi / 4, 3 * math.pi / 4, 5 * math.pi / 4):   # arrowheads between nodes, clockwise
        px, py = cx + r * 1.9 * math.cos(t), cy + r * math.sin(t)
        dx, dy = -r * 1.9 * math.sin(t), r * math.cos(t)
        n = (dx * dx + dy * dy) ** 0.5
        s.append(f"<line x1='{px - dx / n * 6:.1f}' y1='{py - dy / n * 6:.1f}' x2='{px + dx / n * 6:.1f}' y2='{py + dy / n * 6:.1f}' stroke='{SAND}' stroke-width='2' marker-end='url(#ah)'/>")
    for name, phase, ln, x, y in nodes:
        s.append(f"<rect x='{x - W / 2:.1f}' y='{y - H / 2:.1f}' width='{W}' height='{H}' rx='10' fill='#fff' stroke='{SAND}' stroke-width='1.4'/>"
                 f"<text x='{x:.1f}' y='{y - H / 2 + 20:.1f}' text-anchor='middle' fill='{INK}' font-weight='600' font-size='13'>{name} <tspan fill='{QUIET}' font-weight='500' font-size='10.5'>({phase})</tspan></text>"
                 f"<text x='{x:.1f}' y='{y - H / 2 + 40:.1f}' text-anchor='middle' fill='{QUIET}' font-size='10.5'>{ln[0]}</text>"
                 f"<text x='{x:.1f}' y='{y - H / 2 + 54:.1f}' text-anchor='middle' fill='{QUIET}' font-size='10.5'>{ln[1]}</text>")
    s.append(f"<text x='{cx}' y='{cy - 4}' text-anchor='middle' fill='{SAND}' font-weight='600' font-size='14'>Disaster cycle</text>"
             f"<text x='{cx}' y='{cy + 14}' text-anchor='middle' fill='{QUIET}' font-size='10.5'>all four run on any processed scene</text>")
    s.append('</svg>')
    return ''.join(s)


def diagram_timeline():
    items = [('Before 15 Oct', 'Problem study, model shortlist, first decks (v1–v3), RS3DAda inference set up'),
             ('15 Oct', 'In-app height validation, GCP calibration, one-click installer, disaster tools'),
             ('18 Oct', 'Evaluation protocol v2 with 95% CIs, claims register, building intervals, single-pass guard, deck v4'),
             ('22–23 Oct', 'New interface (Home, Scenes, six tools) and the N5 ICESat-2 roof-photon filter'),
             ('25 Oct', 'Landing page and workspace redesign'),
             ('27 Oct', 'App screenshots, report pack and this report')]
    rh, x0 = 44, 120
    s = [f"<svg viewBox='0 0 720 {rh * len(items) + 10}' xmlns='http://www.w3.org/2000/svg' {SANS} font-size='11'>"]
    s.append(f"<line x1='{x0}' x2='{x0}' y1='14' y2='{rh * (len(items) - 1) + 14}' stroke='{SAND_L}' stroke-width='3'/>")
    for i, (d, t) in enumerate(items):
        y = 14 + i * rh
        last = i == len(items) - 1
        s.append(f"<circle cx='{x0}' cy='{y}' r='7' fill='{BLUE if last else SAND}'/>"
                 f"<text x='{x0 - 16}' y='{y + 4}' text-anchor='end' fill='{INK}' font-weight='600'>{d}</text>"
                 f"<text x='{x0 + 18}' y='{y + 4}' fill='{INK}'>{html.escape(t)}</text>")
    s.append('</svg>')
    return ''.join(s)


# ---------- word count ----------
class Counter(HTMLParser):
    """Words in h2/h3/h4/p/li inside #body-text, skipping tables, figures and placeholders' brackets."""
    COUNT = {'h2', 'h3', 'h4', 'p', 'li'}
    SKIP = {'table', 'figure', 'svg', 'figcaption'}

    def __init__(self):
        super().__init__()
        self.inbody = 0
        self.stack, self.words = [], 0

    def handle_starttag(self, tag, attrs):
        if dict(attrs).get('id') == 'body-text':
            self.inbody = 1
        elif self.inbody:
            self.inbody += 1 if tag not in ('img', 'br') else 0
        self.stack.append(tag) if tag not in ('img', 'br') else None

    def handle_endtag(self, tag):
        if self.inbody and tag not in ('img', 'br'):
            self.inbody -= 1
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()

    def handle_data(self, data):
        if self.inbody and any(t in self.COUNT for t in self.stack) and not any(t in self.SKIP for t in self.stack):
            self.words += len(re.findall(r"[\w’'\-–.,%°±×/]+", data))


def main():
    prep_images()
    with open(os.path.join(HERE, 'report_template.html'), encoding='utf-8') as f:
        doc = f.read()
    for key, fn in {'CHART_ACCURACY': chart_accuracy, 'CHART_FLOOD': chart_flood, 'CHART_BIAS': chart_bias,
                    'DIAGRAM_PIPELINE': diagram_pipeline, 'DIAGRAM_CYCLE': diagram_cycle,
                    'DIAGRAM_TIMELINE': diagram_timeline}.items():
        doc = doc.replace('{{' + key + '}}', fn())
    c = Counter()
    c.feed(doc)
    doc = doc.replace('{{WORDCOUNT}}', f'{c.words:,}')
    with open(os.path.join(BUILD, 'report.html'), 'w', encoding='utf-8') as f:
        f.write(doc)
    print(f'body word count: {c.words}', flush=True)
    import weasyprint
    weasyprint.HTML(os.path.join(BUILD, 'report.html'), base_url=BUILD).write_pdf(OUT)
    print(f'wrote {OUT} ({os.path.getsize(OUT) / 1e6:.1f} MB)')


if __name__ == '__main__':
    sys.exit(main())
