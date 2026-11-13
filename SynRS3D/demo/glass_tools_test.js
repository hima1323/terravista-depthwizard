// Browser test of the toolbar tools in the glass UI (React, served at /) against demo/tools_harness.py on port 8765:
//   python demo/tools_harness.py /tmp/dw     (keeps serving; then, in a second terminal)
//   node demo/glass_tools_test.js /tmp/dw     (add the port as a second argument if the harness is not on 8765)
// Known truth: model buildings = 0.75 × true height, trees 12 m vs 18 m, sun 45° from 135°, town_after has blocks 1 and 3
// collapsed and one new building; the observed flood mask is the ground below +2.5 m.
const { chromium } = require('playwright');
const fs = require('fs');
const SP = process.argv[2], B = `http://127.0.0.1:${process.argv[3] || 8765}`;
const results = [];
const check = (name, ok, info = '') => { results.push([ok ? 'PASS' : 'FAIL', name, info]); console.log(ok ? 'PASS' : 'FAIL', name, info); };
(async () => {
  const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'] });
  const p = await b.newPage({ viewport: { width: 1600, height: 950 }, deviceScaleFactor: 1, acceptDownloads: true });
  const errs = [];
  p.on('pageerror', e => errs.push(e.message + ' ' + (e.stack || '').split('\n')[1]));
  const ev = (f, a) => p.evaluate(f, a);
  const T = () => ev(() => __dw.tools.s);
  const go = async (page, scene = 'town_before') => {
    await p.goto(`${B}/#/${page}?scene=${scene}&view=2d&v2test=1`);
    await p.waitForFunction(() => window.__dw && __dw.data, null, { timeout: 30000 });
    if (await ev(() => __dw.s.current) !== scene) await p.selectOption('.scene-pick select', scene);   // the top bar's scene picker
    await p.waitForFunction(s => window.__dw && __dw.data && __dw.data.name === s && __dw.tools.T.los, scene, { timeout: 30000 });
    await p.waitForTimeout(400);
  };
  const on = async id => { if (!(await p.$eval(`#tool-${id} .switch`, e => e.checked))) await p.click(`#tool-${id} .switch`); await p.waitForTimeout(150); };
  const btn = (id, text) => p.locator(`#tool-${id} button`, { hasText: text }).first().click();
  const map = async () => p.$eval('.imgwrap', e => { const r = e.getBoundingClientRect(); return [r.x, r.y, r.width, r.height]; });
  const at = async (u, v) => { const m = await map(); await p.mouse.click(m[0] + u * m[2], m[1] + v * m[3]); };

  // ---------------- Explore ----------------
  await go('explore');
  const cards = await p.$$eval('.panel .card', cs => cs.map(c => c.id).filter(Boolean));
  check('Explore shows its tool cards, all switched off', ['tool-los', 'tool-vol', 'tool-drone', 'tool-solar', 'tool-wms', 'tool-mosaic'].every(id => cards.includes(id))
    && !(await ev(() => Object.values(__dw.tools.s.open).some(Boolean))), cards.join(','));

  await on('drone'); await btn('drone', 'Draw path');
  await at(0.1, 0.5); await at(0.5, 0.2); await at(0.9, 0.6);
  await btn('drone', 'Done');
  const dr = await ev(() => { const t = __dw.tools, D = t.T.drone, S = t.surfaceGrid(), W = __dw.data.meta.grid_w, H = __dw.data.meta.grid_h;
    const okAlt = D.wps.every(w => w.alt >= S[Math.min(H - 1, Math.floor(w.v * H)) * W + Math.min(W - 1, Math.floor(w.u * W))] + 30 - 1e-6);
    let plan = null; try { plan = JSON.parse(t.dronePlan()); } catch {}
    return { n: D.wps.length, okAlt, plan: plan && plan.mission.items.length, kml: t.droneKML().includes('<coordinates>') }; });
  check('drone plan drawn on the 2D map clears the surface', dr.n > 10 && dr.okAlt && dr.plan === dr.n + 2 && dr.kml, JSON.stringify(dr));
  const dl = p.waitForEvent('download'); await btn('drone', 'QGroundControl'); check('drone .plan download', (await dl).suggestedFilename().endsWith('.plan'));

  await on('los'); await at(0.5, 0.5); await p.waitForTimeout(200);
  const l1 = (await T()).los.seen;
  await p.locator('#tool-los label', { hasText: 'Observer height' }).locator('input').fill('200'); await p.waitForTimeout(500);
  const L = (await T()).los;
  check('line of sight: higher mast sees more', l1 > 0 && L.seen >= l1 && L.seen / L.inR > 0.95, `${l1}→${L.seen} of ${L.inR}`);

  await on('vol'); await p.locator('#tool-vol button', { hasText: 'Bare ground' }).click();
  for (const [u, v] of [[95, 95], [165, 95], [165, 145], [95, 145]]) await at(u / 800, v / 800);
  await btn('vol', 'Done');
  const V = (await T()).vol;
  check('volume of a 40×60 px, 18 m block ≈ 10 800 m³', V && Math.abs(V.above - 10800) / 10800 < 0.12, V && `${Math.round(V.above)} m³`);

  await on('solar'); await btn('solar', 'Calculate'); await p.waitForFunction(() => __dw.tools.s.solar, null, { timeout: 30000 });
  const so = await ev(() => { const r = __dw.tools.T.solar.res; return { n: r.length, ok: r.every(x => x.shade >= 0 && x.shade <= 1), max: Math.max(...r.map(x => x.kWh / (x.area * 0.7))) }; });
  check('rooftop solar: every roof, yield within physics', so.n === 8 && so.ok && so.max <= 285 + 1e-6, JSON.stringify(so));
  await on('mosaic');
  check('mosaic lists the georeferenced scenes', (await p.$$eval('#tool-mosaic input[type=checkbox]', e => e.length)) >= 3);
  await on('wms');
  check('map overlay ready for a GeoTIFF', await p.locator('#tool-wms button', { hasText: 'Load overlay' }).isEnabled());
  await p.screenshot({ path: `${SP}/glass_explore.png` });

  // ---------------- tool finder ----------------
  await p.keyboard.press('Control+k'); await p.waitForTimeout(150); await p.keyboard.type('shadow'); await p.keyboard.press('Enter');
  await p.waitForFunction(() => location.hash.startsWith('#/validate') && __dw.tools.s.open.shadow, null, { timeout: 10000 });
  check('Ctrl K finds "shadow", opens Validate with the tool on', true);
  check('leaving Explore switched its tools off', !(await ev(() => __dw.tools.s.open.los || __dw.tools.s.open.solar)));

  // ---------------- Validate ----------------
  await btn('shadow', 'Measure all buildings'); await p.waitForFunction(() => __dw.tools.s.shadow && __dw.tools.s.shadow.autoN != null, null, { timeout: 30000 });
  const sr = (await T()).shadow.ratio;
  check('shadow heights find the 0.75 under-estimate (×1.33)', sr && Math.abs(sr.k - 4 / 3) < 0.08, JSON.stringify(sr));
  await btn('shadow', 'Measure a shadow'); await at(230 / 800, 230 / 800); await at((230 - 12.7) / 800, (230 - 12.7) / 800); await btn('shadow', 'Done');
  const man = await ev(() => __dw.tools.T.shadow.meas[0]);
  check('manual shadow measure ≈ 9 m', man && Math.abs(man.H - 9) < 1.2, man && man.H.toFixed(2));

  await on('fix'); await btn('fix', 'Fit from ICESat-2'); await p.waitForFunction(() => __dw.tools.s.fixFit, null, { timeout: 30000 });
  check('ICESat-2 canopy fit ≈ ×1.5', Math.abs((await T()).fixFit.k - 1.5) < 0.05, JSON.stringify((await T()).fixFit));
  const before = await ev(() => __dw.data.buildings[0].height_m);
  await btn('shadow', 'for all buildings'); await p.waitForFunction(() => __dw.data.meta.class_scale, null, { timeout: 20000 }); await p.waitForTimeout(500);
  const fx = await ev(() => ({ h: __dw.data.buildings[0].height_m, k: __dw.data.meta.class_scale.buildings, t: __dw.data.meta.class_scale.trees }));
  check('applying the fix scales building heights (trees ×1.5 kept)', Math.abs(fx.h / before - fx.k) < 0.01 && Math.abs(fx.t - 1.5) < 0.05, JSON.stringify(fx));
  await btn('fix', 'Reset'); await p.waitForFunction(() => !__dw.data.meta.class_scale, null, { timeout: 20000 }); await p.waitForTimeout(300);
  check('reset restores model heights', Math.abs((await ev(() => __dw.data.buildings[0].height_m)) - before) < 1e-6);

  // GEDI check + canopy map (task 2): trees are 12 m in the model, 18 m in GEDI and in the canopy map
  await p.locator('.card button', { hasText: 'Check with GEDI' }).click(); await p.waitForFunction(() => __dw.s.val.gedi, null, { timeout: 30000 });
  const gd = await ev(() => __dw.s.val.gedi);
  check('GEDI check: ground right, model trees 6 m low, fit ×1.5', gd.ground.mae < 0.5 && Math.abs(gd.trees_model.bias + 6) < 0.5 && Math.abs(gd.tree_fit.k - 1.5) < 0.05,
    JSON.stringify({ shots: gd.shots, trees: gd.tree_shots, bias: gd.trees_model.bias, fit: gd.tree_fit }));
  check('GEDI results shown with map dots', (await p.textContent('.panel')).includes('model vs GEDI canopy top'));
  await p.locator('#tool-fix button', { hasText: 'Meta canopy map' }).click();
  await p.waitForFunction(() => __dw.data.meta.canopy && __dw.tools.s.fixTrees === 'canopy', null, { timeout: 30000 });
  const cpy = await ev(() => __dw.data.meta.canopy);
  check('canopy map loaded: trees 18 m vs model 12 m', cpy.canopy_median_m === 18 && cpy.model_median_m === 12, JSON.stringify(cpy));
  await btn('fix', 'Apply'); await p.waitForFunction(() => __dw.data.meta.class_scale && __dw.data.meta.class_scale.trees_source === 'canopy', null, { timeout: 20000 }); await p.waitForTimeout(400);
  const treeH = await ev(() => { const d = __dw.data, W = d.meta.grid_w, H = d.meta.grid_h; const i = Math.round(0.175 * H) * W + Math.round(0.64 * W); return [d.lc[i], d.grid[i]]; });
  check('trees take the canopy map heights in every view', treeH[0] === 4 && Math.abs(treeH[1] - 18) < 0.5, JSON.stringify(treeH));
  await p.locator('.card button', { hasText: 'Check with GEDI' }).click(); await p.waitForTimeout(300); await p.waitForFunction(() => !__dw.s.vbusy, null, { timeout: 30000 });
  check('after the canopy fix, trees match GEDI', Math.abs((await ev(() => __dw.s.val.gedi.trees_model.bias))) < 0.5, String(await ev(() => __dw.s.val.gedi.trees_model.bias)));
  await btn('fix', 'Reset'); await p.waitForFunction(() => !__dw.data.meta.class_scale, null, { timeout: 20000 }); await p.waitForTimeout(300);

  await p.locator('.card button', { hasText: 'Check with ICESat-2' }).click(); await p.waitForFunction(() => __dw.s.val.icesat2, null, { timeout: 30000 });
  await on('err'); await btn('err', 'Use these error bars'); await p.waitForFunction(() => __dw.data.meta.conformal, null, { timeout: 10000 });
  const chips = await p.textContent('.topbar .chips');
  check('calibrated error bars in read-outs and the top bar', (await ev(() => __dw.tools.pm(1))).includes('90%') && chips.includes('Error (90%)'), chips);
  await btn('err', 'Back to the consistency score'); await p.waitForFunction(() => !__dw.data.meta.conformal);

  fs.writeFileSync(`${SP}/gnss.csv`, 'name,lat,lon,alt\nP1,31.078,76.889,1043\nP2,31.0785,76.8895,1050\nFAR,10,70,5\n');
  await on('gnss'); await p.setInputFiles('#tool-gnss input[type=file]', `${SP}/gnss.csv`); await btn('gnss', 'Import file');
  await p.waitForFunction(() => __dw.data.gcpPts.length >= 2, null, { timeout: 10000 });
  const g = await ev(() => __dw.data.gcpPts.slice(-2).map(q => q.z));
  check('GNSS points become control points (ellipsoid → sea level)', g[0] === 1083 && g[1] === 1090, JSON.stringify(g));
  await ev(() => { __dw.data.gcpPts.length = 0; __dw.renderGcp(); });

  fs.writeFileSync(`${SP}/dem_test.tif`, Buffer.from(await (await fetch(`${B}/results/dem_test.tif`)).arrayBuffer()));
  await on('dem'); await p.setInputFiles('#tool-dem input[type=file]', `${SP}/dem_test.tif`); await btn('dem', 'Use this DEM');
  await p.waitForFunction(() => __dw.data && __dw.data.meta.terrain && __dw.data.meta.terrain.source.includes('dem_test'), null, { timeout: 30000 });
  check('uploaded DEM becomes the terrain source', true, await ev(() => __dw.data.meta.terrain.source));
  await p.waitForTimeout(500); await on('dem'); await btn('dem', 'Back to the default');
  await p.waitForFunction(() => __dw.data && __dw.data.meta.terrain && !__dw.data.meta.terrain.source.includes('dem_test'), null, { timeout: 30000 });
  check('"Back to the default" really restores the default terrain', true, await ev(() => __dw.data.meta.terrain.source));
  await p.screenshot({ path: `${SP}/glass_validate.png` });

  // ---------------- Prepare ----------------
  await go('prepare');
  await on('slide');
  const s1 = (await T()).slide;
  check('landslide risk classes every land cell', s1.total === await ev(() => __dw.data.grid.length - [...__dw.data.lc].filter(c => c === 5).length), JSON.stringify(s1.count));
  await p.locator('#tool-slide label', { hasText: 'Rain in 24 h' }).locator('input').fill('250'); await p.waitForTimeout(500);
  const s2 = (await T()).slide;
  check('heavier rain raises the risk', s2.count[2] + s2.count[3] >= s1.count[2] + s1.count[3] && s2.count[0] <= s1.count[0], JSON.stringify(s2.count));
  const pp = await ev(() => ({ t: __dw.tools.s.people.total, exp: __dw.data.buildings.reduce((a, b) => a + b.area_m2 * b.floors * 0.8 / 10, 0), groups: __dw.tools.s.people.groups.map(g => g.title) }));
  check('people at risk: residents formula, landslide group', Math.abs(pp.t - pp.exp) < 1e-6 && pp.groups.includes('Landslide risk'), JSON.stringify(pp));
  await p.screenshot({ path: `${SP}/glass_prepare.png` });

  // ---------------- Respond ----------------
  await go('respond');
  await p.locator('.card label.check', { hasText: 'Simulate flooding' }).locator('input').check();
  await ev(() => __dw.setDepth(14)); await p.waitForTimeout(300);
  check('flood card shows the people in flooded buildings', (await p.textContent('.panel')).includes('people live in buildings with water inside'));
  fs.writeFileSync(`${SP}/obsmask_test.tif`, Buffer.from(await (await fetch(`${B}/results/obsmask_test.tif`)).arrayBuffer()));
  await on('obs'); await p.setInputFiles('#tool-obs input[type=file]', `${SP}/obsmask_test.tif`); await btn('obs', 'Load & compare');
  await p.waitForFunction(() => __dw.tools.s.obs, null, { timeout: 20000 });
  await btn('obs', 'Fit the water level'); await p.waitForTimeout(500);
  const of = (await T()).obs.fit;
  check('observed flood: fitted level ≈ +2.5 m, CSI high', of && Math.abs(of.rise - 2.5) < 0.25 && of.csi > 0.9, JSON.stringify(of));
  const ob = (await T()).obs, exp = await ev(() => { const t = __dw.tools, d = __dw.data, c = t.blockCells(), r = t.blockRims(), g = t.T.obs.grid;
    return d.buildings.filter(b => c[b.id].some(i => g[i] > 0.5) || r[b.id].some(i => g[i] > 0.5)).length; });
  check('observed flood: buildings reached counted (card, people, report)', ob.hitB === exp && (await p.textContent('#tool-obs')).includes('Buildings the observed flood reached')
    && (await ev(() => __dw.tools.s.people.groups.some(g => g.title.startsWith('Observed flood')))), `${ob.hitB} buildings, ${Math.round(ob.hitPpl)} people`);
  await on('flow');
  check('flowing water switches the level flood off', !(await ev(() => __dw.s.flood)));
  await p.locator('#tool-flow label', { hasText: 'Simulate' }).locator('input').fill('0.25');
  await p.locator('#tool-flow label', { hasText: 'Inflow per point' }).locator('input').fill('20');
  await at(0.05, 0.5); await btn('flow', 'Done');
  await ev(() => __dw.tools.runFlow(true)); await p.waitForTimeout(300);
  const fl = await ev(() => { const F = __dw.tools.T.flow.sim, G = F.G, h = F.snaps.at(-1); let vol = 0; for (let c = 0; c < G.Nc; c++) vol += h[c] * G.dxc * G.dyc; return { vin: F.vin, vout: F.vout, vol, wet: h.filter(x => x > 0.1).length }; });
  check('flowing water conserves water (in = standing + out, ±5%)', fl.wet > 0 && Math.abs(fl.vin - fl.vol - fl.vout) / fl.vin < 0.05, JSON.stringify(fl));
  check('flowing water: time slider and 3D water surface', (await p.$$('#tool-flow input[type=range]')).length === 1 && await ev(() => __dw.water.visible));
  await p.screenshot({ path: `${SP}/glass_respond.png` });

  // ---------------- Relief ----------------
  await go('relief');
  await p.locator('.card label.check', { hasText: 'Simulate flooding' }).count();   // flood is off when entering a disaster page fresh
  await on('evac'); await p.locator('#tool-evac button', { hasText: 'Everyone' }).click(); await btn('evac', 'Make the plan');
  await p.waitForFunction(() => __dw.tools.s.evac && !__dw.tools.s.evac.busy, null, { timeout: 30000 });
  const E = (await T()).evac;
  check('evacuation: everyone placed, unreachable or over capacity', !E.error && E.n === 8 && Math.abs(E.load.reduce((a, b) => a + b, 0) + E.unreach + E.full - E.total) < 1e-6, JSON.stringify(E));
  await p.screenshot({ path: `${SP}/glass_relief.png` });

  // ---------------- Assess ----------------
  await go('assess', 'town_after');
  await on('dmg');
  check('damage picks the "before" scene by name', (await p.$eval('#tool-dmg select', e => e.value)) === 'town_before');
  await btn('dmg', 'Compare'); await p.waitForFunction(() => __dw.tools.s.dmg || __dw.tools.s.dmgMsg.startsWith('⚠'), null, { timeout: 30000 });
  const dm = (await T()).dmg;
  check('damage: 2 collapsed, 0 damaged, 1 new, canopy lost', dm && dm.col === 2 && dm.dam === 0 && dm.newN === 1 && dm.canopy.lost_m2 > 3000, JSON.stringify(dm && { col: dm.col, dam: dm.dam, newN: dm.newN }));
  const rep = await ev(() => __dw.tools.reportHTML());
  check('situation report includes the damage and people sections', rep.includes('Damage: before / after') && rep.includes('People at risk'));
  await p.screenshot({ path: `${SP}/glass_assess.png` });

  // ======================================== response tools ========================================
  // The test terrain rises 6 cm per metre to the east (plus a 25 m hill), so a +7 m flood covers the west 116 m.
  // Block near (cx, cy): the 8 test buildings by their centre in the image.
  const near = `(cx, cy) => __dw.data.buildings.reduce((a, b) => Math.hypot(b.cx - cx, b.cy - cy) < Math.hypot(a.cx - cx, a.cy - cy) ? b : a)`;
  const num = (id, label, v) => p.locator(`#tool-${id} label`, { hasText: label }).locator('input').fill(String(v));

  // ---------------- Respond: embankment, cut-off, ponding, boat ----------------
  await go('respond');
  await on('pond'); await p.waitForTimeout(300);
  check('ponding: the test terrain has no hollows', (await T()).pond.n === 0, JSON.stringify((await T()).pond));
  await ev(() => { __dw.setFlood(true); __dw.setFsrc('edges'); __dw.setDepth(7); }); await p.waitForTimeout(300);
  await on('bund'); await num('bund', 'Height above the ground', 8);
  for (const [u, v] of [[0.11, 0.26], [0.19, 0.26], [0.19, 0.365], [0.11, 0.365], [0.11, 0.26]]) await at(u, v);   // a ring round the block at (0.15, 0.31)
  await btn('bund', 'Done'); await p.waitForTimeout(600);
  const bd = (await T()).bund;
  check('embankment: a ring bund keeps its one building dry; overtops at ground + 8 m', bd && bd.nb === 1 && Math.abs(bd.hold - 10.6) < 0.4 && Math.abs(bd.len - 2 * (0.08 + 0.105) * 400) < 2 && bd.bags === null && Math.abs(bd.earth - bd.len * 8 * 17) < 1,
    bd && JSON.stringify({ nb: bd.nb, hold: bd.hold, len: bd.len, bags: bd.bags, still: bd.still }));
  await num('bund', 'Height above the ground', 1); await p.waitForTimeout(500);
  const b1 = (await T()).bund;   // US Army Corps of Engineers: 600 bags per 100 ft of wall 1 ft high, 4 500 at 3 ft -> about 175 per metre at 1 m
  check('embankment: a 1 m wall is overtopped by this flood; sandbags ≈ 175 per metre', b1.nb === 0 && Math.abs(b1.bags / b1.len - 175) < 3, JSON.stringify({ nb: b1.nb, perM: b1.bags / b1.len }));
  await num('bund', 'Height above the ground', 8); await p.waitForTimeout(500);
  await on('cut'); await p.waitForTimeout(500);
  const ct = (await T()).cut;
  check('cut-off: the ringed building is a dry island; 3 flooded ones are out of reach', ct && ct.nb === 1 && ct.n === 1 && ct.wetB === 3, ct && JSON.stringify({ nb: ct.nb, n: ct.n, wetB: ct.wetB, ppl: ct.ppl }));
  check('people at risk lists the cut-off group', await ev(() => __dw.tools.s.people.groups.some(g => g.title === 'Cut off by water')));
  await ev(() => __dw.setFlood(false)); await p.waitForTimeout(500);
  const pd = (await T()).pond;
  check('ponding: rain fills the ring to its brim (≈ 8 m at the low side), 1 building in it', pd.n === 1 && pd.nb === 1 && pd.list[0].maxd > 7 && pd.list[0].maxd < 8.3 && pd.list[0].hours > 0, JSON.stringify(pd.list));
  await ev(() => { __dw.tools.toggle('bund', false); __dw.setFsrc('all'); __dw.setFlood(true); __dw.setDepth(7); }); await p.waitForTimeout(400);
  check('closing the embankment gives the water its way back', await ev(n => { const b = eval(n)(0.15, 0.31); return __dw.blockState(b, __dw.waterLevel()) !== 'dry' && !__dw.data.reachBase; }, near));
  const boat = await ev(() => { const e = __dw; e.setRouteOpen(true); e.setRmode('boat'); e.data.route = { a: e.cellAt(0.02, 0.1), b: e.cellAt(0.05, 0.9), kind: 'ab', res: null, why: '' }; e.setPick(null); e.updateRoute();
    const boat = e.s.routeSum; e.setRmode('foot'); e.updateRoute(); const foot = e.s.routeSum; e.setRouteOpen(false); return { boat, foot }; });
  check('boat route through the deep water where nobody can walk', boat.boat && boat.boat.how === 'by boat' && boat.boat.len > 300 && Math.abs(boat.boat.minutes - boat.boat.len / 2.5 / 60) < 0.01 && !boat.foot, JSON.stringify(boat.boat));

  // ---------------- facilities: a district's own list ----------------
  const ll = await ev(() => [[0.1625, 0.15], [0.9, 0.5], [0.05, 0.5]].map(([u, v]) => __dw.tools.lonlatAt(u, v)));
  fs.writeFileSync(`${SP}/facilities.csv`, 'name,type,lat,lon\n' + [['PHC West', 'Primary health centre'], ['School East', 'school'], ['River bridge', 'bridge']].map(([n, t], k) => `${n},${t},${ll[k][1]},${ll[k][0]}`).join('\n') + '\nFar away,hospital,10,70\n');
  await p.setInputFiles('#tool-poi input[type=file]', `${SP}/facilities.csv`); await p.locator('#tool-poi button', { hasText: 'Use' }).click();
  await p.waitForFunction(() => __dw.tools.s.poi && __dw.tools.s.poiMsg.includes(' from '), null, { timeout: 15000 });
  const po = (await T()).poi;
  check('facilities: flooded health centre and bridge flagged, school fine, far point skipped', po.n === 3 && po.hit === 2 && po.rows.find(r => r.name === 'PHC West').st[0] === 'water inside'
    && po.rows.find(r => r.name === 'School East').st.length === 0 && po.rows.find(r => r.name === 'River bridge').st[0].includes('check the deck') && (await T()).poiMsg.includes('1 outside'), JSON.stringify(po.rows));
  await p.screenshot({ path: `${SP}/glass_respond2.png` });

  // ---------------- Assess: loss, alert file ----------------
  await go('assess');
  check('facilities are saved with the scene and reload', await p.waitForFunction(() => __dw.tools.s.poi && __dw.tools.s.poi.n === 3, null, { timeout: 10000 }).then(() => true, () => false));
  const ls = await ev(n => { const e = __dw, t = e.tools, b = eval(n)(0.2, 0.675); e.setFsrc('all'); e.setFlood(true); e.setDepth(e.blockGround(b) - e.data.gmin + 1);   // exactly 1 m of water at the small 2-storey block
    const r = t.T.loss.find(x => x.id === b.id); return { loss: r.loss, want: 25000 * b.area_m2 * 0.49, floors: b.floors, total: t.s.loss.total, sum: t.T.loss.reduce((a, x) => a + x.loss, 0) }; }, near);
  check('flood loss: 1 m of water costs 49% of the ground storey', Math.abs(ls.loss - ls.want) < 1 && ls.floors === 2 && Math.abs(ls.total - ls.sum) < 1, JSON.stringify(ls));
  await ev(() => __dw.setDepth(7)); await p.waitForTimeout(300);
  const cap = await ev(() => { const t = __dw.tools, x = t.capXML(), doc = new DOMParser().parseFromString(x, 'application/xml'), q = s => doc.getElementsByTagName(s)[0]?.textContent;
    const ring = q('polygon').split(' ').map(a => a.split(',').map(Number)), lons = ring.map(a => a[1]);
    return { ok: !doc.getElementsByTagName('parsererror').length && doc.documentElement.namespaceURI === 'urn:oasis:names:tc:emergency:cap:1.2', status: q('status'), event: q('event'), sent: q('sent'),
      closed: ring[0].join() === ring.at(-1).join(), n: ring.length, east: Math.max(...lons), want: t.lonlatAt((7 + __dw.data.gmin - 1000) / 0.06 / 400, 0.5)[0], span: t.lonlatAt(1, 0.5)[0] - t.lonlatAt(0, 0.5)[0], desc: q('description') }; });
  check('CAP alert: valid XML, an exercise, the polygon is the flood outline', cap.ok && cap.status === 'Exercise' && cap.event === 'Flood' && cap.closed && cap.n >= 5 && Math.abs(cap.east - cap.want) < 0.01 * cap.span
    && /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d$/.test(cap.sent), JSON.stringify(cap));
  const dl2 = p.waitForEvent('download'); await p.locator('#tool-cap button', { hasText: 'Download CAP' }).click(); check('CAP file download', (await dl2).suggestedFilename().endsWith('.cap.xml'));

  // ---------------- Relief: roofs, warning time, helipad approach, camp needs ----------------
  await ev(() => { __dw.setDepth(10); }); await go('relief'); await ev(() => { __dw.setFsrc('all'); __dw.setFlood(true); __dw.setDepth(10); }); await p.waitForTimeout(600);
  await on('roof'); await p.waitForTimeout(400);
  const rf = await ev(() => { const t = __dw.tools, R = t.s.roof, rows = [...t.T.roof.byId.values()]; return { R, subNoCap: rows.every(r => r.free >= 1 ? r.cap > 0 : r.cap === 0), sub: rows.filter(r => r.free <= 0).length }; });
  check('rooftop refuge: everyone is on a roof, moved or left; drowned roofs hold nobody', Math.abs(rf.R.own + rf.R.moved + rf.R.left - rf.R.people) < 1e-6 && rf.subNoCap && rf.sub >= 1 && rf.R.moved > 0, JSON.stringify({ ...rf.R, top: undefined, sub: rf.sub }));
  await num('roof', 'Neighbours within', 0); await p.waitForTimeout(500);
  check('rooftop refuge: with no neighbours in reach nobody moves', (await T()).roof.moved === 0 && (await T()).roof.left > rf.R.left, JSON.stringify({ left: (await T()).roof.left }));
  await ev(() => { const e = __dw; e.setFlood(true); e.setDepth(1); e.set({ trise: 2.4, train: 0, tdrain: 0 }); e.setTimeOpen(true); }); await p.waitForTimeout(800);
  await on('warn'); await p.waitForTimeout(800);
  const wn = await ev(() => { const t = __dw.tools, W = t.s.warn, tl = __dw.data.tl; return { W, want: __dw.data.buildings.filter(b => tl.bArr[b.id] < 65535).length, r0: t.T.warn.list[0], arr0: Math.min(...[...tl.bArr].slice(1).filter(a => a < 65535)) * 60 }; });
  check('warning time: every building the timeline floods, with its walk to a camp', wn.W && !wn.W.error && wn.W.src === 'timeline' && wn.W.n === wn.want && wn.W.n >= 3 && wn.W.camps >= 1 && wn.W.rows.reduce((a, r) => a + r.n, 0) === wn.W.n
    && wn.r0.arr === wn.arr0 && Math.abs(wn.r0.lead - (wn.r0.arr - 15 - wn.r0.travel)) < 1e-6 && wn.W.late.n === 0, JSON.stringify({ n: wn.W.n, want: wn.want, arr0: wn.arr0, src: wn.W.src, late: wn.W.late, camps: wn.W.camps, rows: wn.W.rows.map(r => r.n), r0: wn.r0 }));
  await num('warn', 'Time to get ready', 100000); await p.waitForTimeout(500);
  check('warning time: a hopeless delay makes everybody late', (await T()).warn.late.n === wn.W.n - wn.W.rows[0].n, JSON.stringify((await T()).warn.late));
  await ev(() => { __dw.setTimeOpen(false); __dw.setFlood(false); }); await p.waitForTimeout(500);
  await on('pad'); await num('pad', 'Approach slope', 3); await p.waitForTimeout(500);
  const p3 = (await T()).pad.pads; await num('pad', 'Approach slope', 12.5); await p.waitForTimeout(500);
  const p12 = (await T()).pad.pads, east = await ev(() => __dw.tools.T.pad.pads.map(q => ({ top: q.dirs[4].top, at: q.dirs[4].at, clear: q.dirs[4].clear }))), west = await ev(() => __dw.tools.T.pad.pads.map(q => q.dirs[12].worst));
  // east of the pads stands the wood: 12 m trees (as the model sees them) on ground that has risen 6 cm per metre
  check('helipad approach: the wood to the east blocks it (12 m trees + the rising ground); downhill to the west is clear', p3.length >= 1 && p3.length === await ev(() => __dw.data.sites.pads.length)
    && p3.every(q => q.clear.includes('W')) && west.every(w => w === 0) && p12.every((q, k) => q.nClear >= p3[k].nClear) && east.some(q => q.top > 5) && east.filter(q => q.top > 5).every(q => !q.clear && Math.abs(q.top - 12 - 0.06 * q.at) < 1.2),
    JSON.stringify({ at3: p3.map(q => q.nClear), at12: p12.map(q => q.nClear), east }));
  await on('evac'); await p.locator('#tool-evac button', { hasText: 'Everyone' }).click(); await btn('evac', 'Make the plan');
  await p.waitForFunction(() => __dw.tools.s.evac && __dw.tools.s.evac.load, null, { timeout: 30000 });
  const nd = await ev(() => ({ N: __dw.tools.campNeeds(), load: __dw.tools.s.evac.load }));
  check('camp needs follow the evacuation plan (15 L, 1 toilet per 20, 5 per tent)', nd.N.planned && Math.abs(nd.N.p - nd.load.reduce((a, b) => a + b, 0)) < 1e-6 && Math.abs(nd.N.water - 15 * nd.N.p) < 1e-6
    && nd.N.rows.every(r => r.toilets === Math.ceil(r.p / 20) && r.tents === Math.ceil(r.p / 5)) && (await p.textContent('#tool-needs')).includes('tanker loads'), JSON.stringify(nd.N.rows));
  await p.screenshot({ path: `${SP}/glass_relief2.png` });

  // ---------------- Prepare: runout, earthquake, fire, cyclone ----------------
  await go('prepare');
  await on('runout'); await p.locator('#tool-runout button', { hasText: 'High and very high' }).click(); await num('runout', 'Reach angle', 45); await p.waitForTimeout(600);
  const r45 = (await T()).runout; await num('runout', 'Reach angle', 25); await p.waitForTimeout(600);
  const r25 = (await T()).runout; await num('runout', 'Reach angle', 10); await p.waitForTimeout(600);
  const r10 = (await T()).runout, relief = await ev(() => __dw.data.gmax - __dw.data.gmin);
  check('landslide runout: nothing moves on slopes flatter than the reach angle; a lower angle runs further, never past its energy', r45.nSrc > 0 && r45.m2 === 0 && r10.m2 > 0 && r10.m2 >= r25.m2
    && r10.maxRun > r25.maxRun && r10.maxRun <= relief / Math.tan(10 * Math.PI / 180) + 2, JSON.stringify({ src: r45.nSrc, m45: r45.m2, m25: r25.m2, m10: r10.m2, run10: r10.maxRun, nb: r10.nb }));
  await ev(() => __dw.tools.toggle('runout', false));
  await on('quake'); await num('quake', 'Floors at least', 8); await num('quake', 'Share that collapses', 100); await p.waitForTimeout(600);
  const q1 = (await T()).quake, big = await ev(n => { const b = eval(n)(0.15, 0.3125); return { h: b.height_m, floors: b.floors }; }, near), rr = big.h * 0.5;
  check('earthquake: only the 8-storey block falls; rubble covers perimeter × reach + the corners', q1.nCol === 1 && big.floors === 8 && Math.abs(q1.debrisM2 - (100 * rr + 2.83 * rr * rr)) / (100 * rr + 2.83 * rr * rr) < 0.12 && q1.cutB === 0,
    JSON.stringify({ nCol: q1.nCol, debrisM2: q1.debrisM2, want: 100 * rr + 2.83 * rr * rr, cutB: q1.cutB }));
  await num('quake', 'Floors at least', 1); await p.waitForTimeout(600);
  const q2 = (await T()).quake;
  check('earthquake: every block down, people counted, nothing left to cut off', q2.nCol === 8 && Math.abs(q2.pCol - 1651.2) < 1e-6 && q2.cutB === 0 && q2.debris > 0, JSON.stringify({ nCol: q2.nCol, pCol: q2.pCol }));
  await ev(() => __dw.tools.toggle('quake', false));
  await on('fire'); await ev(() => __dw.tools.set({ fiWind: 0 })); await at(0.75, 0.85); await btn('fire', 'Done'); await p.waitForTimeout(600);
  const f3 = (await T()).fire;
  check('fire: burns the whole 100 × 75 m wood, stops at the bare ground, reaches no building', f3 && Math.abs(f3.m2 - 7500) / 7500 < 0.06 && f3.nb === 0, f3 && JSON.stringify(f3));
  await ev(() => __dw.tools.setFireTime(0.1)); const f6 = (await T()).fire;
  check('fire: 6 min at 3 m/min ≈ an 18 m radius', f6.m2 > 650 && f6.m2 < 1300, String(f6.m2));
  await ev(() => { const t = __dw.tools; t.T.fire.brk = [[0.70, 0.74], [0.70, 0.95]]; t.set({ fiT: 3 }); t.computeFire(); }); await p.waitForTimeout(300);
  const fb = (await T()).fire;
  check('firebreak: the 30 m strip behind it is saved, the fire does not slip through', fb.base && Math.abs(fb.base.m2 - f3.m2) < 1 && Math.abs((fb.base.m2 - fb.m2) - 2250) / 2250 < 0.15, JSON.stringify({ with: fb.m2, without: fb.base && fb.base.m2 }));
  const fw = await ev(() => { const t = __dw.tools; t.T.fire.brk = []; t.set({ fiWind: 30, fiDir: 270 }); t.computeFire(); const a = t.T.fire.arr; return [a[t.cellOfUV(0.80, 0.85)], a[t.cellOfUV(0.70, 0.85)]]; });
  check('fire: a west wind drives it east faster than west', fw[0] < fw[1] / 3, JSON.stringify(fw));
  await ev(() => __dw.tools.toggle('fire', false));
  await on('surge'); await p.locator('#tool-surge button', { hasText: 'W' }).click(); await num('surge', 'Surge + tide', 5);
  await p.locator('#tool-surge select').selectOption('270'); await p.waitForTimeout(700);
  const sg = await ev(n => { const e = __dw, t = e.tools, X = t.T.surge.exposed; return { s: t.s.surge, flood: e.s.flood, fsrc: e.s.fsrc, rise: e.s.depth, wet: e.s.floodSum.wetPct, west: X.has(eval(n)(0.1625, 0.15).id), lee: X.has(eval(n)(0.306, 0.156).id) }; }, near);
  check('cyclone: a 5 m surge from the west floods the low fifth of the scene', sg.flood && sg.fsrc === 'edges' && Math.abs(sg.rise - 5) < 0.05 && Math.abs(sg.wet - 100 * 5 / 0.06 / 400) < 1.5, JSON.stringify({ rise: sg.rise, wet: sg.wet, level: sg.s.level }));
  check('cyclone: the seaward block is wind-exposed, the low one in its lee is sheltered', sg.west && !sg.lee && sg.s.exposed >= 1, JSON.stringify({ exposed: sg.s.exposed, west: sg.west, lee: sg.lee }));
  await p.screenshot({ path: `${SP}/glass_prepare2.png` });
  const rep2 = await ev(() => __dw.tools.reportHTML());
  check('situation report has the new sections', ['Cyclone: surge and wind', 'Fire spread', 'Earthquake scenario', 'Landslide runout', 'Critical facilities'].every(x => rep2.includes(x)), ['Cyclone: surge and wind', 'Fire spread', 'Earthquake scenario', 'Landslide runout', 'Critical facilities'].filter(x => !rep2.includes(x)).join());

  // ---------------- Explore: search pattern, mast coverage; the finder knows the new tools ----------------
  await go('explore');
  const sw = await ev(() => __dw.tools.constructor.sweep([[0, 0], [200, 0], [200, 100], [0, 100]], 20));
  check('search pattern: 5 legs 20 m apart along the long side, turning at each end', sw.length === 10 && sw[0].join() === '0,10' && sw[1].join() === '200,10' && sw[2].join() === '200,30' && sw[9][1] === 90, JSON.stringify(sw));
  await on('drone'); await p.locator('#tool-drone button', { hasText: 'Search an area' }).click(); await btn('drone', 'Draw the area');
  for (const [u, v] of [[0.25, 0.25], [0.75, 0.25], [0.75, 0.5], [0.25, 0.5]]) await at(u, v);
  await btn('drone', 'Done'); await p.waitForTimeout(300);
  const da = (await T()).drone;
  check('drone search plan over a 200 × 100 m outline', da && da.legs === 3 && Math.abs(da.area - 20000) < 300 && Math.abs(da.len - (3 * 200 + 2 * 40)) < 12, da && JSON.stringify({ legs: da.legs, area: da.area, len: da.len, n: da.n }));
  await on('los'); await num('los', 'Observer height', 30); await num('los', 'At most', 1); await btn('los', 'Suggest mast positions');
  await p.waitForFunction(() => __dw.tools.s.cover && !__dw.tools.s.cvBusy, null, { timeout: 60000 });
  const c1 = (await T()).cover; await num('los', 'At most', 4); await btn('los', 'Suggest mast positions'); await p.waitForTimeout(200);
  await p.waitForFunction(() => __dw.tools.s.cover && !__dw.tools.s.cvBusy, null, { timeout: 60000 });
  const c4 = (await T()).cover, nObs = await ev(() => __dw.tools.T.los.obs.length);
  check('mast coverage: one mast sees most roofs, more masts never see less', c1.n === 1 && c1.pct > 60 && c4.pct >= c1.pct && c4.n === nObs && c4.n <= 4, JSON.stringify({ c1, c4 }));
  await p.keyboard.press('Control+k'); await p.waitForTimeout(150); await p.keyboard.type('sandbag'); await p.keyboard.press('Enter');
  await p.waitForFunction(() => location.hash.startsWith('#/respond') && __dw.tools.s.open.bund, null, { timeout: 10000 });
  check('Ctrl K finds "sandbag": Respond, embankment tool on', true);

  check('no page errors', errs.length === 0, errs.slice(0, 5).join(' | '));
  console.log(`\n${results.filter(r => r[0] === 'PASS').length}/${results.length} passed`);
  await b.close();
})().catch(e => { console.log('CRASH', e.message.split('\n').slice(0, 6).join('\n')); process.exit(1); });
